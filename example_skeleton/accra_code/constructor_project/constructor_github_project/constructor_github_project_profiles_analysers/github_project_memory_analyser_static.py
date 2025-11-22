import os
import re
import subprocess
import sys
import traceback

from langgraph.graph import StateGraph
from .github_project_memory_analyser import GitHubProjectMemoryAnalyser
from ..github_input_guesser import InputGuesser
from ..github_project_helper import *  # noqa: F403
from ..temporary_package_manager import TemporaryPackageManager
from ...constructor_project_analyser import ProjectAnalyser
from ...constructor_project import Project
from accra_code.constructor_project.constructor_github_project.constructor_github_project_errors_analysers.error_manager import ErrorManager

class GitHubProjectMemoryAnalyserStatic(GitHubProjectMemoryAnalyser):

    def __init__(self,project:Project):
        ProjectAnalyser.__init__(self,project) # We could just pass self.project

        self.memray_package_manager = TemporaryPackageManager(destination_folder=os.path.dirname(self.project.project_data["path"]))
        self.memray_package_manager.initialize_existing_packages()
        self._ensure_memray_runtime_dependencies()
        self.memray_package_manager.ensure_packages(["memray"])
        self.err_mng = ErrorManager()
        self.graph = StateGraph(dict)
        self._build_graph()
        self.compiled_graph = self.graph.compile()

    def _ensure_memray_runtime_dependencies(self):
        # Adding temporary packages for memray
        memray_required_packages = ["jinja2", "markupsafe"]
        self.memray_package_manager.ensure_packages(memray_required_packages)

    def _remove_memray_specific_runtime_dependencies(self):
        self.memray_package_manager.cleanup()

    def finalize(self):
        self._remove_memray_specific_runtime_dependencies()

    def _build_graph(self):
        """
        Analyze memory usage of Python scripts in the repository and store results.
        """
        self.memray_package_manager.ensure_packages(["memray"])
        def prepare_input_guesser(state):
            state["input_guesser"] = InputGuesser(self.project.project_data["path"], self.project.project_data["project_details"]["standard_packages"])
            return state

        def analyze_files(state):
            print("\n[Memory Analyzer Static] Running Memory Profile Analysis...")
            memory_profile = {}
            input_guesser = state["input_guesser"]
            # List Python files in the cloned repository
            for root, _, files in os.walk(self.project.project_data["path"]):
                for file in files:
                    if file.endswith(".py"):
                        file_path = os.path.join(root, file)
                        if _should_skip_file(file_path):  # noqa: F405
                            continue

                        print(f"[Memory Analyzer Static] Profiling memory for: {file_path}", file=sys.stderr)
                        # _prepend_sys_path_to_script(file_path, self.project.project_data["path"])

                        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                            script_content = f.read()
                            has_main_block = re.search(r'^\s*if\s+__name__\s*==\s*["\']__main__["\']\s*:',
                                                       script_content,
                                                       re.MULTILINE) is not None
                            if has_main_block:
                                print(f"[Memory Analyzer Static] [Info] Found main block in {file_path}: {has_main_block}")
                            # else:
                            #     print(f"[Error] Found main block in {file_path}: {has_main_block}", file=sys.stderr)

                        if not has_main_block:
                            # print(f"Skipping {file_path}: No '__main__' block.", file=sys.stderr)
                            # memory_profile[file] = {"status": "skipped", "reason": "No '__main__' block"}
                            continue
                        print(f"[Memory Analyzer Static] Analysing {file_path}: with '__main__' block.")

                        try:
                            # determine the executable to use
                            required = _extract_imports_from_file(file_path)  # noqa: F405
                            self.memray_package_manager.ensure_packages(required)
                            output_bin = f"{file_path}.bin"

                            if os.path.exists(output_bin):
                                os.remove(output_bin)
                            command = [self.memray_package_manager.py_venv_exe, "-m", "memray", "run", "--output", output_bin, file_path]
                            print(f"[Memory Analyzer Static] Running {file_path}: {' '.join(command)}", file=sys.stderr)

                            info_inputs = input_guesser.run_python_analysis(str(file_path))
                            print("[Memory Analyzer Static] POSSIBLE INPUTS", info_inputs, "-" * 8)
                            possible_inputs = input_guesser.get_arguments(info_inputs["llm_analysis"])
                            command += possible_inputs

                            try:
                                with self.change_dir(os.path.dirname(file_path)):
                                    subprocess.run(
                                        command,
                                        capture_output=True, text=True, check=True, timeout=self.project.accra_timeout,
                                        env=self.memray_package_manager.local_env_vars
                                    )

                            except subprocess.TimeoutExpired as e:
                                print(f"[Memory Analyzer Static] Memray timed out: {e.stderr}", file=sys.stderr)
                                self.err_mng.handle_error(e, command)
                                continue

                            except subprocess.CalledProcessError as e:
                                print(f"[Memory Analyzer Static] [Error] Memray process failed: {e.stderr}", file=sys.stderr)
                                self.err_mng.handle_error(e, command)
                                continue

                            except Exception as e:
                                print(f"[Memory Analyzer Static] [Unknown Error] {file_path}: {str(e)}")
                                self.err_mng.handle_error(e, command)
                                continue

                            # Try to generate a human-readable summary
                            command = []
                            try:
                                with self.change_dir(os.path.dirname(file_path)):
                                    new_env = os.environ.copy()
                                    new_env["COLUMNS"] = "200"
                                    command = [self.memray_package_manager.py_venv_exe, "-m", "memray", "summary", output_bin]
                                    summary_result = subprocess.run(
                                        command,capture_output=True, text=True, check=True, timeout=self.project.accra_timeout,
                                        env=new_env
                                    )

                            except subprocess.TimeoutExpired as e:
                                print(f"[Memory Analyzer Static] [Timeout] Memray summary timed out for: {file_path}: {e}")
                                self.err_mng.handle_error(e, command)
                                continue

                            except subprocess.CalledProcessError as e:
                                print(f"[Memory Analyzer Static] [Error] Memray summary failed for {file_path} with return code {e.returncode}")
                                print(f"[Memory Analyzer Static] [stdout]\n{e.stdout}")
                                self.err_mng.handle_error(e, command)
                                continue

                            except Exception as e:
                                print(f"[Memory Analyzer Static] [Unknown Error] {file_path}: {str(e)}")
                                self.err_mng.handle_error(e, command)
                                continue

                            print("******* " + summary_result.stdout, file=sys.stderr)
                            # Extract important insights
                            summary_lines = summary_result.stdout.split("\n")

                            # Get total memory allocated and peak memory usage
                            total_memory = "Unknown"
                            peak_memory = "Unknown"

                            # Regex pattern to extract memory values
                            memory_pattern = re.compile(r"(\d+(\.\d+)?)\s*([KMGT]?B)", re.IGNORECASE)
                            max_own: float = 0.0

                            # Loop through lines to find memory values
                            for line in summary_lines:
                                print(line)
                                matches = memory_pattern.findall(line)

                                if matches:
                                    value, _, unit = matches[0]
                                    own, _, own_unit = matches[1]

                                    # Assume the **first memory value** is total memory allocated
                                    if total_memory == "Unknown":
                                        total_memory = f"{value} {unit}"

                                    # Assume the **largest memory value** is peak memory usage
                                    unit_conversion = { unit: 10**(3*i) for i, unit in enumerate(["B", "KB", "MB", "GB", "TB"]) }
                                    own_as_number = float(own) * unit_conversion[own_unit.upper()]
                                    if own_as_number > max_own:
                                        max_own = own_as_number
                                        peak_memory = f"{value} {unit}"

                            memory_profile[file_path] = {"peak_memory": peak_memory, "total_memory": total_memory}

                        except subprocess.CalledProcessError as e:
                            print(f"Error profiling {file_path}: {e}", file=sys.stderr)
                            traceback.print_exc()
                            self.err_mng.handle_error(e)
                            continue
            state["memory_profile"] = memory_profile
            return state
                # Store memory profile in project_data
        def save_results(state):
            if "project_details" not in self.project.project_data:
                    self.project.project_data["project_details"] = {}
            self.project.project_data["project_details"]["memory_profile"] = state.get("memory_profile", {})
            return state

        self.graph.add_node("PrepareGuesser",prepare_input_guesser)
        self.graph.add_node("AnalyzeFiles",analyze_files)
        self.graph.add_node("SaveResults",save_results)
        self.graph.add_edge("PrepareGuesser", "AnalyzeFiles")
        self.graph.add_edge("AnalyzeFiles", "SaveResults")
        self.graph.set_entry_point("PrepareGuesser")
        self.graph.set_finish_point("SaveResults")

    def analyze(self):
        result_state = self.compiled_graph.invoke({})
        print("\n[Memory Analyzer Static] Memory Profile Analysis Complete!\n")
        print(f"[Memory Analyzer Static] {result_state.get('memory_profile', {})}")