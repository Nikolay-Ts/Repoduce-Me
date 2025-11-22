import configparser
import os
import re
import sys
import logging
import subprocess

from packaging.specifiers import SpecifierSet
from packaging.version import Version

import requests
import toml
from typing import List
from dotenv import load_dotenv
from git import Repo

from .constructor_github_project_errors_analysers.error_manager import ErrorManager
from ..constructor_project import Project
from .constructor_github_project_profiles_analysers.github_project_parallelism_analyser_static import GitHubProjectParallelismAnalyserStatic
from .constructor_github_project_profiles_analysers.github_project_network_analyser_static import GitHubProjectNetworkAnalyserStatic
from .constructor_github_project_profiles_analysers.github_project_memory_analyser_static import GitHubProjectMemoryAnalyserStatic
from .constructor_github_project_profiles_analysers.github_project_load_analyser_static import GitHubProjectLoadAnalyserStatic
from .github_project_helper import *  # noqa: F403
from .temporary_package_manager import TemporaryPackageManager
from ..constructor_project_analyser import ProjectAnalyser



class GitHubProject(Project):
    """
    Adapter for GitHub repositories.
    Handles fetching and parsing accra_code data from GitHub.
    """

    def __init__(
        self,
        project_url: str = None,
        project_name: str = None,
        import_directory: str = None,
        github_user: str = None,
        github_path: str = None,
        github_owner: str = None,
        accra_timeout: int = None,
        reuse_existing: bool = False,
    ) -> None:
        """
        Initialize the ExternalProject with a accra_code URL.

        :param project_url: URL of the external accra_code (e.g., GitHub repo, Amazon resource).
        :param reuse_existing: If True, reuse existing folder if it exists instead of creating a new one with .1, .2, etc.
        """
        print("GitHubProject__init__")

        super().__init__(project_url, project_name, import_directory, accra_timeout)
        load_dotenv()

        if project_url is None:
            self.project_url = os.getenv("GITHUB_REPOSITORY", "github.com/giancarlosucci")
        else:
            self.project_url = project_url
        print("GITHUB_REPOSITORY: ", self.project_url)

        if project_name is None:
            self.project_name = os.getenv("GITHUB_NAME", "ACCRa")
        else:
            self.project_name = project_name
        print("GITHUB_NAME: ", self.project_name)

        if import_directory is None:
            self.import_directory = os.getenv("IMPORT_DIRECTORY", "./ImportedProjects")
        else:
            self.import_directory = import_directory
        print("IMPORT_DIRECTORY: ", self.import_directory)

        if github_user is None:
            self.github_user = os.getenv("GITHUB_USER", "giancarlosucci")
        else:
            self.github_user = github_user
        print("GITHUB_USER: ", self.github_user)

        if github_owner is None:
            self.github_owner = os.getenv("GITHUB_OWNER", "giancarlosucci")
        else:
            self.github_owner = github_owner
        print("GITHUB_OWNER: ", self.github_owner)

        if github_path is None:
            self.github_path = os.getenv("GITHUB_PATH")
        else:
            self.github_path = github_path
        print("GITHUB_PATH: ", self.github_path)

        if accra_timeout is None:
            timeout_string = os.getenv("ACCRA_TIMEOUT", "10")
        else:
            timeout_string = accra_timeout
        try:
            self.accra_timeout = int(timeout_string)
        except ValueError as e:
            print(f"accra timeout must be an integer:\n{e}")
            self.accra_timeout = 10
        print("ACCRA_TIMEOUT: ", self.accra_timeout)

        self.github_token = os.getenv("GITHUB_TOKEN", None)

        self.default_python = sys.executable
        print("DEFAULT_PYTHON: ", self.default_python)

        self.reuse_existing = reuse_existing
        print("REUSE_EXISTING: ", self.reuse_existing)

        logging.info(f"Initialized ExternalProject for {self.project_url}")
        self.analysers: List[ProjectAnalyser] = []

        self.error_handler = ErrorManager()

    @staticmethod
    def infer_optional_extras_from_code(project_path):
        optional_extras = set()

        patterns_extras_map = {
            r"\bForm\(": "python-multipart",
            r"\bOAuth2PasswordBearer\(": "python-jose",
            r"\bUploadFile\(": "python-multipart",
            r"\bDepends\(Security\(": "python-jose",
            r"\bJWT\(": "python-jose",
            r"\bCryptContext\(": "passlib"
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
                    except Exception as e:
                        print(f"[Warning] Could not read {file}: {e}", file=sys.stderr)

        return optional_extras

    @staticmethod
    def _parse_supported_py_version(requires_python: str) -> list[str]:
        """
        Args: requires_python is a string which express a constraint on the version, e.g. ">=3.6, <3.11"
        Return: a list of the python versions supported in the form ["3.8", "3.9", "3.10"]
        """
        min_version = 0
        max_py2_version = 7
        max_py3_version = 13
        all_versions = [f"2.{i}" for i in range(min_version, max_py2_version + 1)]
        all_versions.extend([f"3.{i}" for i in range(min_version, max_py3_version + 1)])
        parsed_versions = [v for v in all_versions if SpecifierSet(requires_python).contains(Version(v))]
        return parsed_versions

    def _extract_info_config_files(self):
        """
        Extract relevant information by analyzing the configuration files, in particular
        it extracts the required packages and the python version needed

        Returns:
        - required packages from requirements.txt (with recursive -r support),
        pyproject.toml (PEP 621/Poetry), setup.cfg and setup.py.
        Skips editable installs, pip options, comments, and duplicates.
        - list of the supported versions for the python interpreter
        - a boolean which indicates if pyproject.toml or setup.py are present
        """
        packages = set()
        visited_files = set()
        supported_py_versions: list[str] = []

        are_pyproject_or_setup_present = False

        # --- 1. Parse requirements.txt (recursive) ---
        def _parse_req_file(req_file_path):
            if not os.path.exists(req_file_path) or req_file_path in visited_files:
                return
            visited_files.add(req_file_path)

            with open(req_file_path, "r", encoding="utf-8") as file_handle:
                for line in file_handle:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    # Nested requirement files
                    if line.startswith("-r ") or line.startswith("--requirement "):
                        nested_file = line.split(maxsplit=1)[-1].strip()
                        nested_path = os.path.join(os.path.dirname(req_file_path), nested_file)
                        _parse_req_file(nested_path)
                        continue

                    # Skip editable installs and pip options
                    if line.startswith(("-e", "--editable", "--index-url", "--find-links", "--extra-index-url", "--")):
                        continue

                    # Extract base package name (remove version specifiers)
                    base_pkg = re.split(r'[<>=~!]', line)[0].strip()
                    if base_pkg:
                        packages.add(base_pkg)

        main_req_path = os.path.join(self.project_data["path"], "requirements.txt")
        _parse_req_file(main_req_path)

        # --- 2. Parse pyproject.toml ---
        pyproject_path = os.path.join(self.project_data["path"], "pyproject.toml")
        if os.path.exists(pyproject_path):
            are_pyproject_or_setup_present = True
            try:
                with open(pyproject_path, "r", encoding="utf-8") as f:
                    pyproject = toml.load(f)

                # PEP 621-style dependencies
                if "project" in pyproject and "dependencies" in pyproject["project"]:
                    for dep in pyproject["project"]["dependencies"]:
                        pkg = re.split(r'[<>=~!]', dep)[0].strip()
                        if pkg:
                            packages.add(pkg)

                # Poetry-style dependencies
                elif "tool" in pyproject and "poetry" in pyproject["tool"]:
                    deps = pyproject["tool"]["poetry"].get("dependencies", {})
                    for pkg, version in deps.items():
                        if pkg.lower() == "python":
                            continue  # skip base python version spec
                        clean_pkg = re.split(r'[<>=~!]', pkg)[0].strip()
                        if clean_pkg:
                            packages.add(clean_pkg)

                requires_python = pyproject.get("project", {}).get("requires-python")
                if requires_python and not supported_py_versions:
                    supported_py_versions = self._parse_supported_py_version(requires_python=requires_python)

            except Exception as e:
                print(f"[Warning] Failed to parse pyproject.toml: {e}", file=sys.stderr)

        # --- 3. Parse setup.cfg ---
        setup_cfg_path = os.path.join(self.project_data["path"], "setup.cfg")
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
                        supported_py_versions = self._parse_supported_py_version(requires_python=python_requires)

            except Exception as e:
                print(f"[Warning] Failed to parse setup.cfg: {e}", file=sys.stderr)
        additional_needed = set()
        for root, _, files in os.walk(self.project_data["path"]):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            code = f.read()
                            if "pydantic_settings" in code or "from pydantic_settings" in code:
                                additional_needed.add("pydantic-settings")
                            # (Optional) Add similar rules for other packages
                    except Exception as e:
                        print(f"[Warning] Could not scan {file_path} for imports: {e}", file=sys.stderr)

        packages.update(additional_needed)

        # --- 4. Parse setup.py ---
        setup_py_path = os.path.join(self.project_data["path"], "setup.py")
        if os.path.exists(setup_py_path):
            are_pyproject_or_setup_present = True
            try:
                in_install_requires = False
                with open(setup_py_path, "r", encoding="utf-8") as f:
                    #  Removes whitespace and skips empty lines or comments
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue

                        match = re.search(r'(?:python_requires|requires_python)\s*=\s*[\'"]([^\'"]+)[\'"]', line)
                        if match and not supported_py_versions:
                            python_requires = match.group(1)
                            supported_py_versions = self._parse_supported_py_version(python_requires)

                        if line.startswith("install_requires"):
                            if "[" in line:
                                in_install_requires = True
                                # Finds all string inside single or double-quoted
                                for dep_tuple in re.findall(r"'([^']+)'|\"([^\"]+)\"", line):
                                    dep = dep_tuple[0] or dep_tuple[1]
                                    # Removes the version specifiers
                                    pkg = re.split(r'[<>=~!]', dep)[0].strip()
                                    if pkg:
                                        packages.add(pkg)
                                # If there is only one line
                                if "]" in line:
                                    in_install_requires = False
                            continue

                        if in_install_requires:
                            if "]" in line:
                                in_install_requires = False
                            dep_match = re.match(r"['\"]([^'\"]+)['\"]", line)
                            if dep_match:
                                dep = dep_match.group(1)
                                pkg = re.split(r'[<>=~!]', dep)[0].strip()
                                if pkg:
                                    packages.add(pkg)
            except Exception as e:
                print(f"[Warning] Failed to parse setup.py: {e}")

        # Last resort
        extras_detected = _detect_extras_by_code_scan(self.project_data["path"])  # noqa: F405
        packages.update(extras_detected)

        if not supported_py_versions:
            version_detected = self.detect_py_version()
            if version_detected:
                supported_py_versions = self._parse_supported_py_version(version_detected)
        # Determinist build
        return sorted(packages), supported_py_versions, are_pyproject_or_setup_present

    def detect_py_version(self) -> str | None:
        """
        It uses vermin to guess which python version could be used by analyzing the code of the imported project
        """
        min_version = None
        try:
            result = subprocess.run(
                ["vermin", self.project_data["path"]],
                capture_output=True,check=True,text=True)

            match = re.search(r"Minimum required versions:\s*([^\n]+)", result.stdout)
            if match:
                versions_str = match.group(1).strip()
                versions = [v.strip() for v in versions_str.split(",")]
                min_version = ">="+versions[-1]
        except subprocess.CalledProcessError as e:
            print("Error during analyzing Python version by code: ", e.stderr)

        return min_version

    def fetch_project_data(self):
        """
        Clone the GitHub repository locally and fetch relevant files.
        """

        # Use an existing project
        # self.project_data = {'repo_name': 'RadonPy', 'path': '/Users/alessandro/Desktop/work/ACCRa/ImportedProjects/project_RadonPy.1/RadonPy', 'project_details': {'github_user': 'giancarlosucci', 'github_owner': 'RadonPy', 'repo_url': 'https://github.com/giancarlosucci/RadonPy', 'clone_path': '/Users/alessandro/Desktop/work/ACCRa/ImportedProjects/project_RadonPy.2/RadonPy', 'default_branch': 'develop', 'created_at': '2022-03-17T11:05:22Z', 'updated_at': '2025-07-02T02:27:07Z', 'pushed_at': '2025-02-03T10:54:27Z', 'size': 5131, 'stargazers_count': 186, 'forks_count': 32, 'watchers_count': 186, 'open_issues_count': 9, 'has_issues': True, 'has_wiki': True, 'has_discussions': False, 'license': 'BSD 3-Clause "New" or "Revised" License', 'topics': ['data-driven-design', 'data-science', 'high-throughput-computing', 'lammps', 'materials-informatics', 'materials-science', 'modeling', 'molecular-dynamics', 'molecular-dynamics-simulation', 'polymer', 'polymer-informatics', 'polymer-simulation', 'psi4', 'rdkit', 'simulation'], 'language': 'Python', 'visibility': 'public', 'archived': False, 'disabled': False, 'fork': False, 'owner': 'RadonPy', 'owner_avatar': 'https://avatars.githubusercontent.com/u/101803456?v=4', 'html_url': 'https://github.com/RadonPy/RadonPy', 'contributors_url': 'https://api.github.com/repos/RadonPy/RadonPy/contributors', 'issues_url': 'https://api.github.com/repos/RadonPy/RadonPy/issues{/number}', 'pulls_url': 'https://api.github.com/repos/RadonPy/RadonPy/pulls{/number}', 'commits_url': 'https://api.github.com/repos/RadonPy/RadonPy/commits{/sha}', 'branches_url': 'https://api.github.com/repos/RadonPy/RadonPy/branches{/branch}', 'releases_url': 'https://api.github.com/repos/RadonPy/RadonPy/releases{/id}'}}
        # return

        # Determine where to clone the repository
        destination_folder = os.path.abspath(
            os.path.join(self.import_directory, ("project_" + self.project_name))
        )

        # Handle existing directories
        if os.path.exists(destination_folder):
            if self.reuse_existing:
                # Reuse the existing folder
                print(f"Reusing existing folder: {destination_folder}")
            else:
                # Append .1, .2, etc.
                counter = 1
                new_destination_folder = f"{destination_folder}.{counter}"
                while os.path.exists(new_destination_folder):
                    counter += 1
                    new_destination_folder = f"{destination_folder}.{counter}"
                destination_folder = new_destination_folder

        # Expected format for open repositories: "github.com/owner/repo" or "owner/repo".

        # Prepare API URL to check repository metadata
        api_url = f"https://api.github.com/repos/{self.github_path}"
        headers = {}

        if self.github_token:
            headers["Authorization"] = "token " + self.github_token

        print(f"Querying GitHub API: {api_url}")
        response = requests.get(api_url, headers=headers)

        if response.status_code == 200:
            repo_metadata = response.json()
            is_private = repo_metadata.get("private", False)
            print(f"Repository privacy: {is_private}")
        else:
            print(
                f"Error fetching metadata ({response.status_code}), error: {response.text}",
                file=sys.stderr,
            )
            raise RuntimeError(
                f"Error fetching metadata of {self.project_name}\nStatus code: {response.status_code}\nError:{response.text}"
            )

        # Build the clone URL based on the privacy of the repository.
        if is_private:
            clone_url = f"https://{self.github_user}:{self.github_token}@github.com/{self.github_path}.git"
        else:
            clone_url = f"https://github.com/{self.github_path}.git"

        print(f"Cloning using URL: {clone_url}")

        # destination_folder is the path to the project, while the venv is in the parent directory
        destination_folder = os.path.join(destination_folder, self.project_name)

        # Clone repository only if not reusing existing folder
        if self.reuse_existing and os.path.exists(destination_folder):
            print(
                f"Skipping clone, reusing existing repository at {destination_folder}"
            )
        else:
            try:
                Repo.clone_from(clone_url, destination_folder)
                print(f"Repository cloned successfully into {destination_folder}")
            except Exception as e:
                print(f"Error cloning repository: {e}", file=sys.stderr)
                return

        self.project_data = {
            "repo_name": self.project_name,
            "path": destination_folder,
            "project_details": {
                "github_user": self.github_user,
                "github_owner": self.github_owner,
                "repo_url": f"https://github.com/{self.github_user}/{self.project_name}",
                "clone_path": destination_folder,
                "default_branch": repo_metadata.get("default_branch", None),
                "created_at": repo_metadata.get("created_at", None),
                "updated_at": repo_metadata.get("updated_at", None),
                "pushed_at": repo_metadata.get("pushed_at", None),
                "size": repo_metadata.get("size", None),
                "stargazers_count": repo_metadata.get("stargazers_count", 0),
                "forks_count": repo_metadata.get("forks_count", 0),
                "watchers_count": repo_metadata.get("watchers_count", 0),
                "open_issues_count": repo_metadata.get("open_issues_count", 0),
                "has_issues": repo_metadata.get("has_issues", False),
                "has_wiki": repo_metadata.get("has_wiki", False),
                "has_discussions": repo_metadata.get("has_discussions", False),
                "license": repo_metadata.get("license", {}).get("name") if repo_metadata.get("license") else None,
                "topics": repo_metadata.get("topics", []),
                "language": repo_metadata.get("language", None),
                "visibility": repo_metadata.get("visibility", None),
                "archived": repo_metadata.get("archived", False),
                "disabled": repo_metadata.get("disabled", False),
                "fork": repo_metadata.get("fork", False),
                "owner": repo_metadata.get("owner", {}).get("login", None) if repo_metadata.get("owner") else None,
                "owner_avatar": repo_metadata.get("owner", {}).get("avatar_url", None) if repo_metadata.get("owner") else None,
                "html_url": repo_metadata.get("html_url", None),
                "contributors_url": repo_metadata.get("contributors_url", None),
                "issues_url": repo_metadata.get("issues_url", None),
                "pulls_url": repo_metadata.get("pulls_url", None),
                "commits_url": repo_metadata.get("commits_url", None),
                "branches_url": repo_metadata.get("branches_url", None),
                "releases_url": repo_metadata.get("releases_url", None),
            }
        }

        # print("\n\nProject data:\n", self.project_data, "\n\n")

    def adapt_to_constructor(self):
        """
        Convert accra_code data into Constructor-compatible format.
        """

        print(f"Adapting GitHub accra_code to Constructor format")  # noqa: F541

        """
        We need to build something like the following
        adapted_data = {
            "name": self.project_data["repo_name"],
            "resources": {"cpu": 2, "memory": "8GB"},  # Default resources; adjust as needed
            "dependencies": self.project_data.get("configurations", {}).get("requirements.txt", "").splitlines()
        }
        """
        adapted_data = {

        }
        return adapted_data
        

    def body_create_project_profile(self) -> TemporaryPackageManager:
        py_versions_supported: list[str] = []
        # Add project path to sys.path temporarily
        
   
        # Ensure temporary dependencies for analysis
        if self.project_data["path"] not in sys.path:
            sys.path.insert(0, self.project_data["path"])  # Ensure project modules are importable
        print("start extraction requirements...")
        required_pkgs, py_versions_supported, are_pyproject_or_setup_present = self._extract_info_config_files()

        extra_inferred_pkgs = self.infer_optional_extras_from_code(self.project_data["path"])
        required_pkgs.extend(extra_inferred_pkgs)
        required_pkgs = list(set(required_pkgs))  # Remove duplicates
        required_pkgs.sort()
        self.project_data["project_details"]["standard_packages"] = required_pkgs

        if py_versions_supported:
            print(f"project {self.project_data["repo_name"]} supports the following versions for the python interpreter:\n", py_versions_supported)
            version2use = py_versions_supported[-1] # the last version
        else:
            print("the parsing did not find supported versions, thus we use default python interpreter version")
            version2use = None
        print("creation of virtual environment")
        profiler_temporary_package_mgr = TemporaryPackageManager(destination_folder=os.path.dirname(self.project_data["path"]), path_repository=self.project_data["path"], python_version=version2use, supported_python_versions=py_versions_supported)

        if are_pyproject_or_setup_present:
            profiler_temporary_package_mgr.initialize_project()

        profiler_temporary_package_mgr.ensure_packages(required_pkgs)
        for pkg in required_pkgs:
            # remove version spec and the extras optional dependencies if present
            clean_pkg = re.split(r'\[', pkg.strip().split("==")[0])[0]
            try:
                result = subprocess.run(
                    [profiler_temporary_package_mgr.py_venv_exe, "-m", "pip", "show", clean_pkg],
                    capture_output=True, text=True, check=True
                )
                requires_line = [line for line in result.stdout.splitlines() if line.startswith("Requires:")]
                if requires_line:
                    deps = [dep.strip() for dep in requires_line[0].replace("Requires:", "").split(",") if
                            dep.strip()]
                    # Install subdependencies if not already available
                    for dep in deps:
                        if not _is_package_importable(dep, profiler_temporary_package_mgr.py_venv_exe):  # noqa: F405
                            print(f"[Subdependency] Installing missing: {dep}")
                            profiler_temporary_package_mgr.install_package(dep)
                            profiler_temporary_package_mgr.installed_temp_packages.append(dep)
            except subprocess.CalledProcessError as e:
                print(f"[Warning] Could not analyze dependencies of {clean_pkg}: {e.stderr}", file=sys.stderr)

        return profiler_temporary_package_mgr
        

    def finalize_create_project_profile(self, original_sys_path, tmp_pkg_mng = None):
        # Restore original sys.path
        sys.path = original_sys_path
        
        if tmp_pkg_mng:
            # Cleanup temporary packages
            tmp_pkg_mng.cleanup()
            # Remove virtual environment
            tmp_pkg_mng.remove_venv()


    def create_project_profile(self):
        """
        It handles the process of profiling the project by the resources used.
        After the extraction of packages and python versions, the python virtual environment
        is created and the imported code is analyzed through the available analyzers.
        """
        self.fetch_project_data()
        original_sys_path = list(sys.path)
        try:
            self.body_create_project_profile()

            self.analysers.append(GitHubProjectParallelismAnalyserStatic(self))
            self.analysers.append(GitHubProjectNetworkAnalyserStatic(self))
            self.analysers.append(GitHubProjectMemoryAnalyserStatic(self))
            self.analysers.append(GitHubProjectLoadAnalyserStatic(self))

            for analyser in self.analysers:
                try:
                    analyser.analyze()
                except Exception as e:
                    self.error_handler.handle_error(e)
                finally:
                    analyser.finalize()

        finally:
            self.finalize_create_project_profile(original_sys_path)

    def predict_project_dimension(self) -> dict:
        """
        Compute from project_data the specific dimension prediction.
        The dimensions are stored in project_dimension_prediction.
        """
        print("Predicting project dimensions...")

        project_details = self.project_data.get("project_details", {})

        # --- Memory (RAM) Prediction ---
        memory_profile = project_details.get("memory_profile", {})
        total_ram = 0.0
        for _, result in memory_profile.items():
            if result.get("status") == "success":
                mem_str = result.get("total_memory_forecasted", "0 MB").split()[0]
                try:
                    total_ram += float(mem_str)
                except ValueError:
                    continue

        print("Ram detected:", round(total_ram, 2))

        # --- Load (CPU/GPU) Prediction ---
        load_profile = project_details.get("load_profile", {})
        total_cpu = 0.0
        total_gpu = 0.0
        for _, result in load_profile.items():
            if result.get("status") == "success":
                total_cpu += result.get("percent_cpu", 0.0)
                total_gpu += result.get("percent_gpu", 0.0)

        print("CPU detected:", round(total_cpu, 2))
        print("GPU detected:", round(total_gpu, 2))

        # --- Network usage ---
        network_info = project_details.get("network_requirements", {})
        total_network_dependencies = len(network_info.get("dependencies", []))
        total_api_calls = sum(count for _, count in network_info.get("api_calls", []))

        print("total_network_dependencies:", total_network_dependencies)
        print("total_api_calls:", total_api_calls)

        self.project_dimension_prediction = {
            "CPUs": total_cpu,
            "GPUs": total_gpu,
            "RAM": total_ram,
            "Storage": 2,
            "NetworkBandwidth": total_network_dependencies,
        }
        print(f"Predicted dimension: {self.project_dimension_prediction}")
        return self.project_dimension_prediction
