import os
import re
import subprocess
import sys
import platform
import json
from langgraph.graph import StateGraph
from .github_project_load_analyser import GitHubProjectLoadAnalyser
from ..github_input_guesser import InputGuesser
from ..github_project_helper import * # noqa: F403
from ..temporary_package_manager import TemporaryPackageManager
from ...constructor_project_analyser import ProjectAnalyser
from ...constructor_project import Project
from accra_code.constructor_project.constructor_github_project.constructor_github_project_errors_analysers.error_manager import ErrorManager

class GitHubProjectLoadAnalyserStatic(GitHubProjectLoadAnalyser):
    def __init__(self, project:Project):
        ProjectAnalyser.__init__(self,project)
        if platform.system() not in {"Linux", "Darwin"}:
            print("[Warning] Scalene is only supported on Linux and macOS. Memory analysis will be skipped.")
            self.scalene_supported = False
            return
        else:
            self.scalene_supported = True
        self.scalene_package_manager = TemporaryPackageManager(destination_folder=os.path.dirname(project.project_data["path"]))
        self.scalene_package_manager.initialize_existing_packages()
        self._ensure_scalene_runtime_dependencies()
        self.err_mng = ErrorManager()
        self.graph = StateGraph(dict)
        self._build_graph()
        self.compiled_graph = self.graph.compile()

    def _ensure_scalene_runtime_dependencies(self):
        # Adding temporary packages for scalene
        scalene_required_packages = ["jinja2", "markupsafe"]
        self.scalene_package_manager.ensure_packages(scalene_required_packages)

    def _remove_scalene_specific_runtime_dependencies(self):
        self.scalene_package_manager.cleanup()

    @staticmethod
    def _parse_scalene_json_metrics(file_path):
        """
        Parse Scalene JSON output and return CPU and GPU utilization summary.
        Parameters:
            file_path (str): Path to the Scalene-generated .json file
        Returns:
            dict: Dictionary with status and extracted metrics
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            files_data = data.get("files", {})

            cpu_python = 0.0
            cpu_c = 0.0
            cpu_sys = 0.0
            gpu_percent = 0.0
            has_functions = False
            for file_entry in files_data.values():
                functions = file_entry.get("functions", [])
                for func in functions:
                    has_functions = True
                    cpu_python = max(cpu_python, func.get("n_cpu_percent_python", 0.0))
                    cpu_c = max(cpu_c, func.get("n_cpu_percent_c", 0.0))
                    cpu_sys = max(cpu_sys, func.get("n_sys_percent", 0.0))
                    gpu_percent = max(gpu_percent, func.get("n_gpu_percent", 0.0))
            if not has_functions:
                return {
                    "status": "error",
                    "error_message": "No functions found in any file section"
                }
            total_cpu = round(cpu_python + cpu_c + cpu_sys, 2)
            total_gpu = round(gpu_percent, 2)
            return {
                "status": "success",
                "percent_cpu": total_cpu,
                "percent_gpu": total_gpu,
            }
        except Exception as e:
            print(f"[Load Analyzer Static] [Error] Failed to parse Scalene JSON file: {file_path} with {e}")
            return {
                "status": "error",
                "error_message": str(e)
            }

    def finalize(self):
        self._remove_scalene_specific_runtime_dependencies()

    def _build_graph(self):
        def check_scalene_support(state):
            if not self.scalene_supported:
                return {"status": "unsupported"}
            return {"status": "supported"}

        def prepare_input_guesser(state):
            state["input_guesser"] = InputGuesser(self.project.project_data["path"], self.project.project_data["project_details"]["standard_packages"])
            return state

        def analyze_files(state):
            print("\n[Load Analyzer Static] Running Load Analysis...")
            load_profile = {}
            input_guesser = state["input_guesser"]
            for root, _, files in os.walk(self.project.project_data["path"]):
                print("\n[Load Analyzer Static] Looping through project data")
                for file in files:
                    if not file.endswith(".py"):
                        print("\n[Load Analyzer Static] File analysis: Not a .py")
                        continue
                    file_path = os.path.join(root, file)
                    if _should_skip_file(file_path): # noqa: F405
                        print("\n[Load Analyzer Static] File analysis: Skip file")
                        continue
                    # print(f"Profiling load for: {file_path}", file=sys.stderr)
                    # _prepend_sys_path_to_script(file_path, self.project.project_data["path"])
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        script_content = f.read()
                        has_main_block = re.search(r'^\s*if\s+__name__\s*==\s*["\']__main__["\']\s*:', script_content, re.MULTILINE) is not None
                    if not has_main_block:
                        print("\n[Load Analyzer Static] File analysis: Didn't find __main__")
                        continue
                    print(f"[Load Analyzer Static] Analyzing {file_path} with '__main__' block")
                    required = _extract_imports_from_file(file_path) # noqa: F405
                    self.scalene_package_manager.ensure_packages(required)
                    output_file = f"{file_path}.scalene.json"
                    command = [
                        self.scalene_package_manager.py_venv_exe, # use the python executable in the venv created
                        "-m", "scalene",
                        "--cli", "--json",
                        "--outfile", output_file,
                        file_path
                    ]
                    info_inputs = input_guesser.run_python_analysis(str(file_path))
                    print("[Load Analyzer Static] POSSIBLE INPUTS", info_inputs, "-"*8)
                    possible_inputs = input_guesser.get_arguments(info_inputs["llm_analysis"])
                    command += possible_inputs
                    try:
                        with self.change_dir(os.path.dirname(file_path)):
                            subprocess.run(
                                command, capture_output=True, text=True, timeout=self.project.accra_timeout,
                                env=self.scalene_package_manager.local_env_vars, check=True
                            )
                    except subprocess.TimeoutExpired as e:
                        print(f"[Load Analyzer Static] [Timeout] Scalene profiling timed out for {file_path}: {e.stderr}", file=sys.stderr)
                        self.err_mng.handle_error(e, command)
                        continue
                    except subprocess.CalledProcessError as e:
                        print(f"[Load Analyzer Static] [Error] Scalene failed for {file_path}: {e.stderr}", file=sys.stderr)
                        self.err_mng.handle_error(e, command)
                        continue
                    except Exception as e:
                        print(f"[Load Analyzer Static] [Unknown Error] {file_path}: {str(e)}", file=sys.stderr)
                        self.err_mng.handle_error(e, command)
                        continue
                    if not os.path.exists(output_file):
                        print(f"[Load Analyzer Static] [Warning] Scalene output file missing for {file_path}")
                        continue
                    try:
                        with open(output_file, "r", encoding="utf-8", errors="replace") as f:
                            summary_lines = f.readlines()  # noqa: F841
                    except Exception as e:
                        print(f"[Load Analyzer Static] [Warning] Failed to read Scalene output: {e}")
                        self.err_mng.handle_error(e)
                        continue
                    result_from_scalene = self._parse_scalene_json_metrics(output_file)
                    if result_from_scalene["status"] == "error":
                        print(f"[Load Analyzer Static] [Error] in {file_path}: {result_from_scalene["error_message"]}")
                        continue
                    load_profile[file_path] = result_from_scalene
            state["load_profile"] = load_profile
            return state

        def save_results(state):
            if "project_details" not in self.project.project_data:
                self.project.project_data["project_details"] = {}
            self.project.project_data["project_details"]["load_profile"] = state.get("load_profile", {})
            return state

        self.graph.add_node("CheckSupport", check_scalene_support)
        self.graph.add_node("PrepareGuesser", prepare_input_guesser)
        self.graph.add_node("AnalyzeFiles", analyze_files)
        self.graph.add_node("SaveResults", save_results)
        self.graph.add_conditional_edges("CheckSupport", lambda s: s["status"] == "supported", {True: "PrepareGuesser", False: "SaveResults"})
        self.graph.add_edge("PrepareGuesser", "AnalyzeFiles")
        self.graph.add_edge("AnalyzeFiles", "SaveResults")
        self.graph.set_entry_point("CheckSupport")
        self.graph.set_finish_point("SaveResults")

    def analyze(self):
        result_state = self.compiled_graph.invoke({})
        print("\n[Load Analyzer Static] Load Profile Analysis Complete!")
        print(f"[Load Analyzer Static] {result_state.get("load_profile", {})}")
