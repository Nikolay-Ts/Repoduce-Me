"""
Agent for determining technical requirements of a project
"""
import os
import re
import configparser
import toml
from packaging.specifiers import SpecifierSet
from packaging.version import Version


class ConstructorRequirementsAgentLC:
    """
    Agent to determine technical requirements including:
    - Required Python packages
    - Python version constraints
    - Optional dependencies
    """

    @staticmethod
    def _parse_supported_py_version(requires_python: str) -> list[str]:
        """Parse Python version constraints into list of supported versions"""
        min_version = 0
        max_py2_version = 7
        max_py3_version = 13
        all_versions = [f"2.{i}" for i in range(min_version, max_py2_version + 1)]
        all_versions.extend([f"3.{i}" for i in range(min_version, max_py3_version + 1)])
        parsed_versions = [v for v in all_versions if SpecifierSet(requires_python).contains(Version(v))]
        return parsed_versions

    def run(self, project_data: dict) -> dict:
        """
        Analyze project to determine technical requirements

        Returns:
            dict with keys:
                - required_packages: list of package names
                - python_versions: list of supported Python versions
                - optional_packages: list of optional dependencies
        """
        if not project_data or "path" not in project_data:
            return {
                "required_packages": [],
                "python_versions": [],
                "optional_packages": []
            }

        project_path = project_data["path"]
        packages = set()
        visited_files = set()
        supported_py_versions = []
        optional_packages = set()

        # Parse requirements.txt
        def _parse_req_file(req_file_path):
            if not os.path.exists(req_file_path) or req_file_path in visited_files:
                return
            visited_files.add(req_file_path)

            with open(req_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    # Handle nested requirements
                    if line.startswith("-r ") or line.startswith("--requirement "):
                        nested_file = line.split(maxsplit=1)[-1].strip()
                        nested_path = os.path.join(os.path.dirname(req_file_path), nested_file)
                        _parse_req_file(nested_path)
                        continue

                    # Skip pip options
                    if line.startswith(("-e", "--editable", "--index-url", "--find-links", "--extra-index-url", "--")):
                        continue

                    # Extract package name
                    base_pkg = re.split(r'[<>=~!]', line)[0].strip()
                    if base_pkg:
                        packages.add(base_pkg)

        main_req_path = os.path.join(project_path, "requirements.txt")
        _parse_req_file(main_req_path)

        # Parse pyproject.toml
        pyproject_path = os.path.join(project_path, "pyproject.toml")
        if os.path.exists(pyproject_path):
            try:
                with open(pyproject_path, "r", encoding="utf-8") as f:
                    pyproject = toml.load(f)

                # PEP 621 dependencies
                if "project" in pyproject and "dependencies" in pyproject["project"]:
                    for dep in pyproject["project"]["dependencies"]:
                        pkg = re.split(r'[<>=~!]', dep)[0].strip()
                        if pkg:
                            packages.add(pkg)

                # Poetry dependencies
                elif "tool" in pyproject and "poetry" in pyproject["tool"]:
                    deps = pyproject["tool"]["poetry"].get("dependencies", {})
                    for pkg, version in deps.items():
                        if pkg.lower() != "python":
                            clean_pkg = re.split(r'[<>=~!]', pkg)[0].strip()
                            if clean_pkg:
                                packages.add(clean_pkg)

                # Python version
                requires_python = pyproject.get("project", {}).get("requires-python")
                if requires_python and not supported_py_versions:
                    supported_py_versions = self._parse_supported_py_version(requires_python)

            except Exception as e:
                print(f"[Warning] Failed to parse pyproject.toml: {e}")

        # Parse setup.cfg
        setup_cfg_path = os.path.join(project_path, "setup.cfg")
        if os.path.exists(setup_cfg_path):
            try:
                config = configparser.ConfigParser()
                config.read(setup_cfg_path)

                if config.has_section("options") and config.has_option("options", "install_requires"):
                    deps = config.get("options", "install_requires").splitlines()
                    for dep in deps:
                        dep = dep.strip()
                        if dep and not dep.startswith("#"):
                            pkg = re.split(r'[<>=~!]', dep)[0].strip()
                            if pkg:
                                packages.add(pkg)

                if config.has_section("options") and config.has_option("options", "python_requires"):
                    python_requires = config.get("options", "python_requires")
                    if python_requires and not supported_py_versions:
                        supported_py_versions = self._parse_supported_py_version(python_requires)

            except Exception as e:
                print(f"[Warning] Failed to parse setup.cfg: {e}")

        # Parse setup.py
        setup_py_path = os.path.join(project_path, "setup.py")
        if os.path.exists(setup_py_path):
            try:
                with open(setup_py_path, "r", encoding="utf-8") as f:
                    content = f.read()

                    # Extract python_requires
                    match = re.search(r'(?:python_requires|requires_python)\s*=\s*[\'"]([^\'"]+)[\'"]', content)
                    if match and not supported_py_versions:
                        python_requires = match.group(1)
                        supported_py_versions = self._parse_supported_py_version(python_requires)

                    # Extract install_requires
                    install_requires_match = re.search(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
                    if install_requires_match:
                        deps_str = install_requires_match.group(1)
                        for dep_match in re.findall(r'[\'"]([^\'"]+)[\'"]', deps_str):
                            pkg = re.split(r'[<>=~!]', dep_match)[0].strip()
                            if pkg:
                                packages.add(pkg)

            except Exception as e:
                print(f"[Warning] Failed to parse setup.py: {e}")

        # Detect optional extras from code
        optional_packages = self._detect_optional_extras(project_path)

        return {
            "required_packages": sorted(list(packages)),
            "python_versions": supported_py_versions,
            "optional_packages": sorted(list(optional_packages))
        }

    @staticmethod
    def _detect_optional_extras(project_path: str) -> set:
        """Detect optional package extras by scanning code"""
        optional_extras = set()

        patterns_extras_map = {
            r"\bForm\(": "python-multipart",
            r"\bOAuth2PasswordBearer\(": "python-jose",
            r"\bUploadFile\(": "python-multipart",
            r"\bEmailStr\b": "pydantic[email]",
            r"\bSecretStr\b": "pydantic[email]",
        }

        for root, _, files in os.walk(project_path):
            for file in files:
                if file.endswith(".py"):
                    try:
                        with open(os.path.join(root, file), encoding="utf-8") as f:
                            content = f.read()
                            for pattern, extra in patterns_extras_map.items():
                                if re.search(pattern, content):
                                    optional_extras.add(extra)
                    except Exception:
                        continue

        return optional_extras
