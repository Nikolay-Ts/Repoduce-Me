import os
import re
import shutil
import glob
import subprocess
import sys
import traceback
import textwrap
from typing import TypedDict, Optional
from enum import StrEnum

from accra_code.constructor_project.constructor_github_project.temporary_package_manager import TemporaryPackageManager
from accra_code.constructor_project.constructor_project_analyser import ProjectAnalyser
from accra_code.constructor_project.constructor_github_project.constructor_github_project_errors_analysers.error_manager import ErrorManager
from accra_code.lc_integration.constructor_chat_model import ConstructorModel

from langgraph.graph import StateGraph, START, END

class FinderStatus(StrEnum):
    NO_EXAMPLE   = "NO_EXAMPLE"
    EXAMPLE_FND  = "EXAMPLE_FND"
    EXAMPLE_ERR  = "EXAMPLE_ERR"


class _FinderState(TypedDict, total=False):
    """This is the State schema for the subgraph.

    It exists mostly for future scalability - additional fields can be added 
    (logs, error info, paths, ...) when the graph is integrated 
    with the main pipeline
    """
    status: FinderStatus             # Indicates whether a valid example was found
    last_error:   str | None  # Last error message (e.g. from README example), or None
    last_finder:  str | None

class GithubProjectExampleFinder(ProjectAnalyser):
    def __init__(self, project):
        super().__init__(project)

        self.package_manager = TemporaryPackageManager(
            destination_folder=os.path.dirname(project.project_data["path"])
        )
        self.err_mng = ErrorManager()

        self.root = self.project.project_data["path"]
        self.main_filename = self.root + '/accra_main_example.py'

    def _run_file(self):
        command = [
            self.package_manager.py_venv_exe,
            self.main_filename
        ]
        with self.change_dir(self.root):
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.project.accra_timeout,
                env=self.package_manager.local_env_vars,
                check=True
            )

    def _try_execution(
        self,
        cleanup: bool = False
    ) -> tuple[bool, Optional[str]]:
        result = None
        error_output: str | None = None
        
        try:
            result = self._run_file()
            return True,error_output
        except subprocess.TimeoutExpired as e:
            print(f"[Timeout] Example running timeout {e}", file=sys.stderr)
            error_output = f"TimeoutExpired: {e}"
        except subprocess.CalledProcessError as e:
            print(f"[Execution Error] Example running error: {e}.\nSTDERR:\n{e.stderr}\nSTDOUT:{e.stdout}")
            error_output = f"STDERR:\n{e.stderr}\n\nSTDOUT:\n{e.stdout}"
        except Exception as e:
            print(f"[Unknown Error] Example running error: {e}")
            print(traceback.format_exc())
            if result:
                print("STDOUT:")
                print(result.stdout)
                print("STDERR:")
                print(result.stderr)
            error_output = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

        if cleanup:
            # At this point, main_filename *must* exist if the logic is correct.
            if os.path.exists(self.main_filename):
                os.remove(self.main_filename)
            
        return False,error_output

    def llm_fixer(self, state: _FinderState) -> _FinderState:
        print(f"LLM_FIXER Called by {state['last_finder']}")
        update = {}
        update["status"] = FinderStatus.NO_EXAMPLE

        last_error = state["last_error"]
            
        with open(self.main_filename, "r", encoding="utf-8") as f:
            broken_code = f.read()

        prompt = textwrap.dedent(f"""
            You are a helpful developer assistant.
            The code from self.main_filename failed to run. Fix it so that it executes successfully, preserving its intent.
            No placeholders - must run as-is. Output only the complete fixed code of the whole file.
                                 
            --- ERROR LOG ---
            {last_error}

            --- BROKEN CODE ---
            {broken_code}             
        """).strip()

        answer = ConstructorModel().invoke(prompt).content or ""
        blocks = self._markdown_blocks(answer.splitlines(keepends=True), "python")
        if not blocks:
            return update
        
        fixed_code = "".join(blocks[0]).strip()
        if not fixed_code:
            return update
            
        with open(self.main_filename, "w", encoding="utf-8") as f:
            f.write(fixed_code)

        # cleanup=True is fine here
        success, error_output = self._try_execution(cleanup=True)
        if success:
            self.project.project_data["example_filename"] = self.main_filename
            update["status"] = FinderStatus.EXAMPLE_FND
            return update
        
        return update

    def find_in_examples_folder(self, update: dict) -> _FinderState:
        update["status"] = FinderStatus.NO_EXAMPLE
        for f in glob.glob(self.root + "/examples/*.py"):
            shutil.copy(f, self.main_filename)
            success, error_output = self._try_execution()
            if success:
                # Example finished successfully, so keep it and don't try other examples
                self.project.project_data["example_filename"] = self.main_filename
                update["status"] = FinderStatus.EXAMPLE_FND
                return update
            update["status"] = FinderStatus.EXAMPLE_ERR
            update["last_error"] = error_output
        return update

    def _readme_lines(self):
        path = self.root + "/README.md"
        if not os.path.isfile(path):
            return False
        with open(path) as f:
            text = f.readlines()

        return text

    def _markdown_blocks(self, lines, lang):
        blocks = []
        current_block = []
        in_block = False
        block_indent = None
        for line in lines:
            if not in_block:
                if line.strip().startswith("```" + lang):
                    in_block = True
                    block_indent = line.index('`')
            else:
                if line.strip() == "```":
                    in_block = False
                    blocks.append(current_block)
                    current_block = []
                else:
                    current_block.append(line[block_indent:])

        return blocks
    
    def _rst_blocks(self, lines, lang):
        blocks = []
        current_block = []
        in_block = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith(".. code-block:: " + lang):
                if in_block and current_block:
                    blocks.append(current_block)
                in_block = True
                current_block = []
                continue
            if in_block:
                if line.startswith("    ") or line.startswith("\t"):
                    current_block.append(line)
                else:
                    if current_block:
                        blocks.append(current_block)
                    in_block = False
                    current_block = []
        
        if in_block and current_block:
            blocks.append(current_block)

        return blocks

    def find_in_readme_simple(
        self,
        update: dict
    ) -> _FinderState:
        """
        Try to extract a working Python example directly from the README.
        If none of the blocks run successfully, we leave the *last* broken
        block on disk as accra_main_example.py so the LLM fixer can patch it.
        """
        lines = self._readme_lines()
        update["status"] = FinderStatus.NO_EXAMPLE
        if not lines:
            return update

        blocks = self._markdown_blocks(lines, "python")
        if not blocks:
            return update

        for block in blocks:
            with open(self.main_filename, "w", encoding="utf-8") as f:
                f.write(''.join(block))
            success, error_output = self._try_execution()
            if success:
                self.project.project_data["example_filename"] = self.main_filename
                update["status"] = FinderStatus.EXAMPLE_FND
                return update
            update["status"] = FinderStatus.EXAMPLE_ERR
            update["last_error"] = error_output
        return update
    
    def find_in_readme_cli_usage(self, update: dict) -> _FinderState:
        lines = self._readme_lines()
        update["status"] = FinderStatus.NO_EXAMPLE
        if not lines:
            return update
        blocks = self._markdown_blocks(lines, "")
        exes = set()
        for block in blocks:
            for line in block:
                # executable name
                line = line.split()
                if not line:
                    continue
                name = line[0]
                exes.add(name)

        main_modules = set()
        for exe in exes:
            # Main modules are often located in lib/lib.py
            path = self.root + "/" + exe + "/" + exe + ".py"
            if os.path.isfile(path):
                main_modules.add(exe)

        for module in main_modules:
            with open(self.main_filename, "w") as f:
                f.write(f"from {module} import {module}\n{module}.main(['-h'])")
            success,_ = self._try_execution()
            if not success:
                continue

            result = self._run_file()
            help_message = result.stdout

            positional_arguments = re.search(r"positional arguments:\n(.*)\n\n", help_message)
            if not positional_arguments:
                continue
            argument = positional_arguments.group(1)

            formats = {
                'PDF': '*.pdf'
            }
            try_globs = set()
            for k in formats:
                if k in argument:
                    try_globs.add(formats[k])

            for g in try_globs:
                for file in glob.glob(self.root + "/test/**/" + g):
                    with open(self.main_filename, "w") as f:
                        f.write(f"from {module} import {module}\n{module}.main(['{file}'])\n")
                        success, error_output = self._try_execution()
                        if success:
                            update["status"] = FinderStatus.EXAMPLE_FND
                            self.project.project_data["example_filename"] = self.main_filename
                            return update
                    update["status"] = FinderStatus.EXAMPLE_ERR
                    update["last_error"] = error_output
        return update
                
    def find_in_readme_with_llm(self,update: dict) -> _FinderState:
        lines = self._readme_lines()
        update["status"] = FinderStatus.NO_EXAMPLE
        if not lines:
            return update
        readme_text = "".join(lines)

        prompt = textwrap.dedent(f"""
                You are a helpful developer assistant.
                You are given the README of a GitHub repository. From the README, extract a demo Python script which shows how to use the code.
                Do not leave any placeholders. The code should run.
                
                Output only the code wrapped in the python code block like this:
                ```python
                <This is the code>
                ```

                README:
                ---
                {readme_text}
                ---
            """).strip()
        model = ConstructorModel()
        answer = model.invoke(prompt).content
        
        if not answer:
            return update

        lines = answer.splitlines(keepends=True)
        blocks = self._markdown_blocks(lines, "python")
        if not blocks:
            return update
        code = "".join(blocks[0]).strip()

        if not code:
            return update

        with open(self.main_filename, "w", encoding="utf-8") as f:
            f.write(code)

        success, error_output = self._try_execution()
        if success:
            update["status"] = FinderStatus.EXAMPLE_FND
            self.project.project_data["example_filename"] = self.main_filename
            return update
        update["status"] = FinderStatus.EXAMPLE_ERR
        update["last_error"] = error_output
        return update

    def find_in_readme_with_db(self, update: dict) -> _FinderState:
        lines = self._readme_lines()
        update["status"] = FinderStatus.NO_EXAMPLE
        if not lines:
            return update
        
        blocks = self._markdown_blocks(lines, "python")
        
        for block in blocks:
            if not block:
                continue
                
            block_text = "".join(block).strip()
            
            parts = block_text.split()
            if len(parts) < 2:    #so if it's only python, we discard it
                continue
            
            py = parts[0].lower()
            if not (py.startswith("python")):
                continue
            file = parts[1]  
            if not file.endswith(".py"):       # checking if it's something like python main.py
                continue
            
            argv_list = parts[1:]
            
            main_path = os.path.join(self.root, file)    #path to main fail
            if not os.path.isfile(main_path):
                continue
            
            argv = f"""\
                    import sys, atexit
                    __OLD_ARGV = sys.argv[:]
                    atexit.register(lambda: sys.__setattr__('argv', __OLD_ARGV))
                    sys.argv = {argv_list!r}
                """

            with open(main_path, "r", encoding="utf-8") as main:
                main = main.read()                         #copying main file
                
            with open(self.main_filename, "w", encoding="utf-8") as f:
                f.write(argv)
                f.write(main)                                #writing +argv list and main

            success, error_output = self._try_execution()
            if success:
                    self.project.project_data["example_filename"] = self.main_filename
                    update["status"] = FinderStatus.EXAMPLE_FND
                    return update
            update["status"] = FinderStatus.EXAMPLE_ERR
            update["last_error"] = error_output
        return update
        
    
    def find_in_docs(self, update: dict,) -> _FinderState:
        blocks = []
        update["status"] = FinderStatus.NO_EXAMPLE
        
        for folder in ("doc", "docs"):
            base = os.path.join(self.root, folder)
            if not os.path.isdir(base):
                continue

            for root, _, files in os.walk(base):
                for name in files:
                    file = os.path.splitext(name)[1].lower()
                    if file not in (".md", ".rst"):
                        continue

                    path = os.path.join(root, name)
                    with open(path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        
                    if not lines:
                        continue
        
                    if file == ".md":
                        blocks += self._markdown_blocks(lines, "python")
                    elif file == ".rst":
                        blocks += self._rst_blocks(lines, "python")

        for block in blocks:
            if not block:
                continue

            block_text = "".join(block).strip()
            parts = block_text.split()
            if len(parts) < 2:
                continue
            if not parts[0].lower().startswith("python"):
                continue

            file = parts[1]
            if not file.endswith(".py"):
                continue

            argv_list = parts[1:]
            main_path = os.path.join(self.root, file)
            if not os.path.isfile(main_path):
                continue
            

            argv = (
           "import sys, atexit\n"
            "__OLD_ARGV = sys.argv[:]\n"
            "atexit.register(lambda: sys.__setattr__('argv', __OLD_ARGV))\n"
            f"sys.argv = {argv_list!r}\n"
        )

            with open(main_path, "r", encoding="utf-8") as main:
                main = main.read()

            with open(self.main_filename, "w", encoding="utf-8") as f:
                f.write(argv)
                f.write(main)
            
            success, error_output = self._try_execution()
            if success:
                self.project.project_data["example_filename"] = self.main_filename
                update["status"] = FinderStatus.EXAMPLE_FND
                return update
            update["status"] = FinderStatus.EXAMPLE_ERR
            update["last_error"] = error_output
        return update
    def analyze(self):
        """
        The analyze function now simply invoke the already built graph.
        Returns True if something's been found.
        """
        print("[Example Finder] Initializing temporary package manager...")
        self.package_manager.initialize_existing_packages()

        app = build_example_finder_graph(self)
        final_state = app.invoke({"status": FinderStatus.NO_EXAMPLE})
        print("[Example Finder] Example finder finished.")
        return final_state["status"] == FinderStatus.EXAMPLE_FND
    
def build_example_finder_graph(finder: GithubProjectExampleFinder):
        """
        This is the workflow of the finders but driven by LangGraph.
        Returns the compiled graph.
        """
        print("[Example Finder] Building example finder graph...")
        g = StateGraph(_FinderState)

        def _set_entry(fn):
            def _node(state: _FinderState) -> _FinderState:
                update = {}
                update["last_finder"] = fn.__name__
                print(f"We are in {fn.__name__}")
                update["last_error"] = None
                return  fn(update)
            return _node

        def _route(state: _FinderState):
            return str(state["last_finder"] if state["status"] is FinderStatus.NO_EXAMPLE else state["status"])

        finders = [
            finder.find_in_examples_folder,
            finder.find_in_readme_simple,
            finder.find_in_readme_cli_usage,
            finder.find_in_readme_with_llm,
            finder.find_in_readme_with_db,
            finder.find_in_docs,
            finder.llm_fixer,
        ]

        for method in finders[:-1]:
            g.add_node(method.__name__, _set_entry(method))
        
        g.add_node(finder.llm_fixer.__name__, finder.llm_fixer)

        print("[Example Finder] Wiring example finder graph...")

        next_node = {
            finder.find_in_examples_folder.__name__ : finder.find_in_readme_simple.__name__,
            finder.find_in_readme_simple.__name__   : finder.find_in_readme_cli_usage.__name__,
            finder.find_in_readme_cli_usage.__name__: finder.find_in_readme_with_llm.__name__,
            finder.find_in_readme_with_llm.__name__ : finder.find_in_readme_with_db.__name__,
            finder.find_in_readme_with_db.__name__  : finder.find_in_docs.__name__,
            finder.find_in_docs.__name__            : END,
            "EXAMPLE_FND"                           : END,
            "EXAMPLE_ERR"                           : finder.llm_fixer.__name__,
        }

        # Wiring
    
        g.add_edge(START, finders[0].__name__)
        
        for method in finders:
            g.add_conditional_edges(method.__name__, _route, next_node)
        
        
        print("[Example Finder] Compiling example finder graph...")

        return g.compile()
