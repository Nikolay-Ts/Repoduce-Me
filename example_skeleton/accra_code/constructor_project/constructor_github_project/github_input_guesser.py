import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union  # noqa: F401
import os
from constructor_adapter import StatefulConstructorAdapter


class InputGuesser:
    """ Guess possible inputs for a Python project entry point """

    def __init__(self, repo_path: str, required_packages):
        """ Initialize with a StatelessConstructorAdapter instance. """
        self.adapter = StatefulConstructorAdapter()
        if os.path.exists(repo_path):
            self.repo_path = Path(repo_path)
        else:
            raise FileNotFoundError(f"Repository path does not exist: {repo_path}")
        print(f"Scanning Python repository: {repo_path}")
        self.repo_info = self.scan_python_repository(required_packages)


    def scan_python_repository(self, required_packages) -> Dict[str, Any]:
        """Scan the Python repository and collect relevant information."""
        requirements = required_packages if required_packages else self._analyze_requirements()
        repo_info = {
            "path": str(self.repo_path),
            "python_files": self._find_python_files(),
            "structure": self._get_python_structure(self.repo_path),
            "readme": self._find_readme(),
            "requirements": requirements,
            "setup_py": self._analyze_setup_py(),
            "pyproject_toml": self._analyze_pyproject_toml(),
            "imports": self._analyze_imports(),
            "main_patterns": self._find_main_patterns(),
        }

        return repo_info

    def _find_python_files(self) -> List[str]:
        """Find all Python files in the repository."""
        python_files = []
        for py_file in self.repo_path.rglob("*.py"):
            if not any(part.startswith(".") for part in py_file.parts):
                python_files.append(str(py_file.relative_to(self.repo_path)))
        return python_files

    def _get_python_structure(
            self, path: Path, max_depth: int = 4, current_depth: int = 0
    ) -> Dict:
        """Get Python-specific directory structure."""
        if current_depth >= max_depth:
            return {}

        structure = {}
        try:
            for item in path.iterdir():
                if item.name.startswith(".") or item.name == "__pycache__":
                    continue

                if item.is_dir():
                    # Check if it's a Python package
                    if (item / "__init__.py").exists():
                        structure[f"{item.name}/"] = {
                            "type": "python_package",
                            "contents": self._get_python_structure(
                                item, max_depth, current_depth + 1
                            ),
                        }
                    else:
                        structure[f"{item.name}/"] = self._get_python_structure(
                            item, max_depth, current_depth + 1
                        )
                elif item.suffix == ".py":
                    structure[item.name] = {
                        "type": "python_file",
                        "size": item.stat().st_size,
                        "functions": self._extract_functions(item),
                        "classes": self._extract_classes(item),
                    }
                elif item.name in [
                    "requirements.txt",
                    "setup.py",
                    "pyproject.toml",
                    "Pipfile",
                ]:
                    structure[item.name] = {"type": "config_file"}
        except PermissionError:
            pass

        return structure

    @staticmethod
    def _extract_functions(py_file: Path) -> List[str]:
        """Extract function names from Python file."""
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
            functions = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(node.name)
            return functions
        except:  # noqa: E722
            return []

    @staticmethod
    def _extract_classes(py_file: Path) -> List[str]:
        """Extract class names from Python file."""
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
            classes = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append(node.name)
            return classes
        except:  # noqa: E722
            return []

    def _find_readme(self) -> Optional[str]:
        """Find and read README file."""
        readme_files = ["README.md", "README.txt", "README.rst", "README"]

        for readme_file in readme_files:
            readme_path = self.repo_path / readme_file
            if readme_path.exists():
                try:
                    return readme_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    try:
                        return readme_path.read_text(encoding="latin-1")
                    except:  # noqa: E722
                        continue
        return None

    def _analyze_requirements(self) -> Dict[str, Any]:
        """Analyze Python requirements files."""
        requirements_info = {}

        # requirements.txt
        req_path = self.repo_path / "requirements.txt"
        if req_path.exists():
            try:
                content = req_path.read_text(encoding="utf-8")
                requirements_info["requirements.txt"] = {
                    "content": content,
                    "packages": [
                        line.strip()
                        for line in content.split("\n")
                        if line.strip() and not line.startswith("#")
                    ],
                }
            except:  # noqa: E722
                requirements_info["requirements.txt"] = {"error": "Could not read file"}

        # requirements-dev.txt, requirements-test.txt, etc.
        for req_file in self.repo_path.glob("requirements*.txt"):
            if req_file.name != "requirements.txt":
                try:
                    content = req_file.read_text(encoding="utf-8")
                    requirements_info[req_file.name] = {
                        "content": content,
                        "packages": [
                            line.strip()
                            for line in content.split("\n")
                            if line.strip() and not line.startswith("#")
                        ],
                    }
                except:  # noqa: E722
                    requirements_info[req_file.name] = {"error": "Could not read file"}

        return requirements_info

    def _analyze_setup_py(self) -> Optional[Dict[str, Any]]:
        """Analyze setup.py file."""
        setup_path = self.repo_path / "setup.py"
        if not setup_path.exists():
            return None

        try:
            content = setup_path.read_text(encoding="utf-8")

            # Extract basic info using regex
            info = {"content": content}

            # Extract name
            name_match = re.search(r'name\s*=\s*[\'"]([^\'"]+)[\'"]', content)
            if name_match:
                info["name"] = name_match.group(1)

            # Extract entry points
            entry_match = re.search(r"entry_points\s*=\s*{([^}]+)}", content, re.DOTALL)
            if entry_match:
                info["entry_points"] = entry_match.group(1).strip()

            # Extract console scripts
            console_match = re.search(
                r'console_scripts[\'"]:\s*\[([^\]]+)\]', content, re.DOTALL
            )
            if console_match:
                info["console_scripts"] = console_match.group(1).strip()

            return info
        except:  # noqa: E722
            return {"error": "Could not analyze setup.py"}

    def _analyze_pyproject_toml(self) -> Optional[Dict[str, Any]]:
        """Analyze pyproject.toml file."""
        pyproject_path = self.repo_path / "pyproject.toml"
        if not pyproject_path.exists():
            return None

        try:
            content = pyproject_path.read_text(encoding="utf-8")
            return {"content": content}
        except:  # noqa: E722
            return {"error": "Could not read pyproject.toml"}

    def _analyze_imports(self) -> Dict[str, Set[str]]:
        """Analyze imports across all Python files."""
        imports = {}

        for py_file in self.repo_path.rglob("*.py"):
            if any(part.startswith(".") for part in py_file.parts):
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content)

                file_imports = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            file_imports.add(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            file_imports.add(node.module)

                imports[str(py_file.relative_to(self.repo_path))] = file_imports
            except:  # noqa: E722
                continue

        return imports

    def _find_main_patterns(self) -> List[Dict[str, Any]]:
        """Find main execution patterns in Python files."""
        main_patterns = []

        for py_file in self.repo_path.rglob("*.py"):
            if any(part.startswith(".") for part in py_file.parts):
                continue

            try:
                content = py_file.read_text(encoding="utf-8")

                # Check for if __name__ == "__main__":
                if 'if __name__ == "__main__"' in content:
                    main_patterns.append({
                        "file": str(py_file.relative_to(self.repo_path)),
                        "type": "main_guard",
                        "content": self._extract_main_block(content),
                    })

                # Check for argparse usage
                if "argparse" in content:
                    main_patterns.append({
                        "file": str(py_file.relative_to(self.repo_path)),
                        "type": "argparse",
                        "content": self._extract_argparse_usage(content),
                    })

                # Check for sys.argv usage
                if "sys.argv" in content:
                    main_patterns.append({
                        "file": str(py_file.relative_to(self.repo_path)),
                        "type": "sys_argv",
                        "content": content[:500],  # First 500 chars
                    })

            except:  # noqa: E722
                continue

        return main_patterns

    @staticmethod
    def _extract_main_block(content: str) -> str:
        """Extract the main execution block."""
        lines = content.split("\n")
        main_start = -1

        for i, line in enumerate(lines):
            if 'if __name__ == "__main__"' in line:
                main_start = i
                break

        if main_start == -1:
            return ""

        # Extract the main block (with proper indentation handling)
        main_lines = []
        base_indent = len(lines[main_start]) - len(lines[main_start].lstrip())

        for i in range(main_start, len(lines)):
            line = lines[i]
            if line.strip() == "":
                main_lines.append("")
                continue

            current_indent = len(line) - len(line.lstrip())
            if i > main_start and current_indent <= base_indent and line.strip():
                break

            main_lines.append(line)

        return "\n".join(main_lines)

    @staticmethod
    def _extract_argparse_usage(content: str) -> str:
        """Extract argparse usage patterns."""
        lines = content.split("\n")
        argparse_lines = []

        for line in lines:
            if "argparse" in line or "add_argument" in line or "parse_args" in line:
                argparse_lines.append(line.strip())

        return "\n".join(argparse_lines)

    def analyze_python_entry_point(self, entry_point_path: str) -> Dict[str, Any]:
        """Analyze the Python entry point file in detail."""
        entry_path = Path(entry_point_path)

        if not entry_path.exists():
            raise FileNotFoundError(f"Entry point does not exist: {entry_path}")

        try:
            content = entry_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = entry_path.read_text(encoding="latin-1")

        # Parse AST for detailed analysis
        analysis = {
            "path": str(entry_path),
            "content": content,
            "size": len(content),
            "lines": content.count("\n") + 1,
            "functions": [],
            "classes": [],
            "imports": [],
            "main_execution": None,
            "argparse_usage": None,
            "input_methods": [],
        }

        try:
            tree = ast.parse(content)

            # Extract functions and classes
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    analysis["functions"].append({
                        "name": node.name,
                        "args": [arg.arg for arg in node.args.args],
                        "line": node.lineno,
                    })
                elif isinstance(node, ast.ClassDef):
                    analysis["classes"].append({"name": node.name, "line": node.lineno})
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        analysis["imports"].append(node.module)
        except:  # noqa: E722
            pass

        # Analyze main execution pattern
        if 'if __name__ == "__main__"' in content:
            analysis["main_execution"] = self._extract_main_block(content)

        # Analyze argparse usage
        if "argparse" in content:
            analysis["argparse_usage"] = self._extract_argparse_usage(content)

        # Detect input methods
        input_methods = []
        if "input(" in content:
            input_methods.append("interactive_input")
        if "sys.argv" in content:
            input_methods.append("command_line_args")
        if "argparse" in content:
            input_methods.append("argparse")
        if "open(" in content or "with open(" in content:
            input_methods.append("file_input")
        if "sys.stdin" in content:
            input_methods.append("stdin")

        analysis["input_methods"] = input_methods

        return analysis

    @staticmethod
    def generate_python_analysis_prompt(repo_info: Dict[str, Any], entry_point_info: Dict[str, Any]) -> str:
        """Generate specialized prompt for Python repository analysis."""
        prompt = f"""
    Analyze this Python repository and its entry point to understand what kind of input this program expects.

    REPOSITORY INFORMATION:
    - Path: {repo_info["path"]}
    - Python files: {len(repo_info["python_files"])} files
    - Key Python files: {repo_info["python_files"][:10]}

    DEPENDENCIES:
    - Requirements: {list(repo_info["requirements"])}

    SETUP INFORMATION:
    - Setup.py: {"Yes" if repo_info["setup_py"] else "No"}
    - PyProject.toml: {"Yes" if repo_info["pyproject_toml"] else "No"}

    MAIN EXECUTION PATTERNS:
    {json.dumps(repo_info["main_patterns"], indent=2)}

    README CONTENT:
    {repo_info["readme"][:1000] if repo_info["readme"] else "No README found"}

    ENTRY POINT ANALYSIS:
    - File: {entry_point_info["path"]}
    - Functions: {[f["name"] for f in entry_point_info["functions"]]}
    - Classes: {[c["name"] for c in entry_point_info["classes"]]}
    - Input methods detected: {entry_point_info["input_methods"]}
    - Key imports: {entry_point_info["imports"][:10]}

    ENTRY POINT CODE:
    ```python
    {entry_point_info["content"][:3000]}
    ```

    MAIN EXECUTION BLOCK:
    ```python
    {entry_point_info["main_execution"] if entry_point_info["main_execution"] else "No main block found"}
    ```

    ARGPARSE USAGE:
    ```python
    {entry_point_info["argparse_usage"] if entry_point_info["argparse_usage"] else "No argparse usage found"}
    ```

    Based on this Python code analysis, please provide:
    1. If required, which parameters to pass and their values 
    2. What type of input it expects (command line args, files, stdin, interactive, etc.)
    3. Expected argument format and types
    4. Required and optional arguments
    5. Example usage of options that would work. The list example_options will be actually used for running the script, so pay attention to details.

    Format your response as JSON:
    {{ 
        "arguments_needed: "yes|no",
        "input_type": "command_line|file_input|stdin|interactive|mixed",
        "required_arguments": [
            {{"name": "arg_name", "type": "str|int|float|bool|file", "description": "what it does"}}
        ],
        "optional_arguments": [
            {{"name": "arg_name", "type": "str|int|float|bool|file", "description": "what it does", "default": "default_value"}}
        ],
        "example_options": [
            "--arg1 value1 --arg2 value2"
        ],   
        "expected_output": "description of what the program outputs",
        "usage_notes": "additional important information about running the program"
    }}
    """
        return prompt

    @staticmethod
    def generate_python_input_examples(analysis_result: str) -> List[str]:
        """Parse model analysis and generate Python-specific input examples."""
        try:
            analysis = json.loads(analysis_result)
            return analysis.get("example_commands", [])
        except json.JSONDecodeError:
            # Fallback: extract Python commands from text
            lines = analysis_result.split("\n")
            examples = []
            for line in lines:
                if  "python" in line.lower() and (".py" in line or "main" in line):
                    examples.append(line.strip())
            return examples

    def run_python_analysis(self, entry_point: str) -> Dict[str, Any]:
        """Run complete Python-specific analysis."""
        print(f"Analyzing Python entry point: {entry_point}")
        entry_point_info = self.analyze_python_entry_point(entry_point)

        print("Generating Python analysis prompt...")
        prompt = self.generate_python_analysis_prompt(self.repo_info, entry_point_info)

        print("Requesting LLM analysis...")
        analysis_result = self.adapter.query(prompt)

        return {
            # "repo_info": self.repo_info,
            # "entry_point_info": entry_point_info,
            "llm_analysis": analysis_result,
            # "input_examples": input_examples,
        }

    @staticmethod
    def get_arguments(analysis_result):
        """
        Extracts the potential arguments that can be used from the analysis_result and returns a list with them
        """
        if analysis_result.strip().startswith("```"):
            lines = analysis_result.strip().splitlines()
            analysis_result = "\n".join(lines[1:-1])

        analysis = json.loads(analysis_result)
        arg_need = analysis.get("arguments_needed", None)
        options = []
        if arg_need and arg_need.strip().lower() == "yes":
            options = analysis.get("example_options", [])
            if not options:
                required_arguments = analysis.get("required_arguments", [])
                for arg in required_arguments:
                    options.append(arg["name"])

        return options
