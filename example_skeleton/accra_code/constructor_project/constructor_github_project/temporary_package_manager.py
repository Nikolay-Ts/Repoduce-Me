import shutil
import subprocess
import sys
import logging
import os
import re
import json

from .constructor_github_project_errors_analysers.error_manager import ErrorManager
from .github_project_helper import * # noqa: F403

class TemporaryPackageManager():
    """
    This class handles all the phases of the lifecycle of the
    python virtual environment created each project imported.
    """
    def __init__(self, python_executable=sys.executable, destination_folder: str = None, path_repository: str = None, python_version: str = None, supported_python_versions: list[str] = None):
        self.python_executable = python_executable
        print(f"[PackageManager] Using Python: {self.python_executable}", file=sys.stderr)
        self.local_env_vars = {}
        self._load_local_environment()
        self._preexisting_packages = set() # To avoid removing what is already there
        self.installed_temp_packages = []
        self.error_mng = ErrorManager()
        # Attributes for virtual environment
        self.path_dest_folder = os.path.abspath(destination_folder) if destination_folder is not None else "."
        self.path_repository = os.path.abspath(path_repository) if path_repository is not None else "."
        self.venv_path = None
        self.py_venv_exe = None # Path to python executable of the dynamic venv created
        if python_version and isinstance(python_version, str):
            self.python_version_venv = python_version
            self.venv_name = ".venv-py"+self.python_version_venv
            self.supported_py_versions = supported_python_versions
        else:
            self.python_version_venv = os.getenv("PYTHON_VERSION_VENV", "3.12.10")
            self.venv_name = os.getenv("VENV_NAME", ".venv-py3")
            self.supported_py_versions = [self.python_version_venv]
        print("venv version:", self.python_version_venv)
        self.handle_venv_creation()
        self.initialize_existing_packages()

    # def __del__(self):
    #     self.cleanup()

    def initialize_existing_packages(self):
        try:
            result = subprocess.run(
                [self.py_venv_exe, "-m", "pip", "list", "--format=json"],
                capture_output=True, text=True, check=True,env=self.local_env_vars
            )
            packages = json.loads(result.stdout)
            self._preexisting_packages = {pkg["name"].lower() for pkg in packages}
        except Exception as e:
            print(f"[Warning] Could not detect installed packages via pip: {e}", file=sys.stderr)
            self._preexisting_packages = set()

    @staticmethod
    def _extract_base_package(pkg):
        """Extract base package name for import checking (e.g., 'requests[security]>=2.0' → 'requests')"""
        # Remove environment markers (anything after `;`)
        pkg = pkg.split(";", 1)[0].strip()
        return re.split(r"[<>=\[\]]", pkg.strip())[0]

    def ensure_packages(self, package_list):
        """
        Install any missing packages from the list. Handles extras and skips special entries.
        Tracks installed packages for later cleanup.
        """
        for original_pkg in package_list:
            stripped_pkg = original_pkg.strip()

            # Skip invalid or pip option entries
            if not stripped_pkg or stripped_pkg.startswith("-"):
                print(f"[Skip] Skipping special requirement entry: {original_pkg}", file=sys.stderr)
                continue

            # Direct install if extras are specified (e.g., pydantic[email])
            if "[" in stripped_pkg:
                print(f"[Temp Install] Installing package with extras: {stripped_pkg}", file=sys.stderr)
                cmd = [self.py_venv_exe, "-m", "pip", "install", stripped_pkg]
                try:
                    subprocess.run(cmd, check=True, capture_output=True, env=self.local_env_vars)
                    self.installed_temp_packages.append(stripped_pkg)
                except subprocess.CalledProcessError as e:
                    logging.warning(
                        f"[Temp Install] Failed to install package with extras: {stripped_pkg}\n"
                        f"{e.stderr.decode().strip()}"
                    )
                    self.error_mng.handle_error(e, cmd)
                continue

            # Extract the base package name for importability check
            clean_pkg = self._extract_base_package(stripped_pkg)
            if not clean_pkg:
                print(f"[Warning] Could not extract base package name from: {stripped_pkg}", file=sys.stderr)
                continue
            if clean_pkg.lower() in self._preexisting_packages:
                print(f"[Info] Package already installed (base match): {clean_pkg}", file=sys.stderr)
                continue

            if not _is_package_importable(clean_pkg, self.py_venv_exe):  # noqa: F405
                print(f"[Temp Install] Installing missing package: {stripped_pkg}", file=sys.stderr)
                cmd = [self.py_venv_exe, "-m", "pip", "install", stripped_pkg]
                try:
                    subprocess.run(cmd, check=True, capture_output=True, env=self.local_env_vars)
                    self.installed_temp_packages.append(stripped_pkg)
                except subprocess.CalledProcessError as e:
                    print(f"[Temp Install] Failed to install package: {stripped_pkg}\n", f"{e.stderr.decode().strip()}", file=sys.stderr)
                    logging.warning(
                        f"[Temp Install] Failed to install package: {stripped_pkg}\n"
                        f"{e.stderr.decode().strip()}"
                    )
                    self.error_mng.handle_error(e, cmd)
                    continue

                # Final recheck to confirm successful importability
                if not _is_package_importable(clean_pkg, self.py_venv_exe):  # noqa: F405
                    print(f"[Warning] Package '{clean_pkg}' still not importable after installation.", file=sys.stderr)
            else:
                print(f"[Info] Package already installed and importable: {clean_pkg}", file=sys.stderr)

    def install_package(self,package_name):
        """Install the package given in the python virtual environment"""
        if self.py_venv_exe is None:
            raise RuntimeError("attribute self.py_venv_exe is None")
        if not os.path.exists(os.path.join(self.venv_path, "bin", "pip")):
            raise ModuleNotFoundError("pip module not installed")

        if package_name not in self._preexisting_packages:
            cmd = [self.py_venv_exe, "-m", "pip", "install", package_name]
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True, env=self.local_env_vars)
                return True
            except subprocess.CalledProcessError as e:
                print(f"[Error] Could not install {package_name}:\n{e.stderr.strip()}", file=sys.stderr)
                self.error_mng.handle_error(e, cmd)
                return False

    def cleanup(self):
        """Uninstall only the packages that were installed temporarily."""
        for pkg in list(set(self.installed_temp_packages)): # Remove duplicates
            if pkg in self._preexisting_packages:
                continue
            base_pkg = pkg.split("[")[0].lower()
            if base_pkg not in self._preexisting_packages:
                print(f"[Temp Cleanup] Uninstalling: {pkg}")
                try:
                    subprocess.run(
                        [self.py_venv_exe, "-m", "pip", "uninstall", "-y", pkg],
                        check=True, capture_output=True, env=self.local_env_vars
                    )
                except subprocess.CalledProcessError as e:
                    print(f"[Warning] Could not uninstall {pkg}:\n{e.stderr.decode().strip()}", file=sys.stderr)
            else:
                print(f"[Preserve] Keeping installed dependency: {pkg}", file=sys.stderr)
        # Clear internal state
        self.installed_temp_packages.clear()

    def _load_local_environment(self, project_envfile_path: str = None):
        """
        Load environment variables from `.accra_project_environment_variables` in the root of the project,
        storing previous values for restoration later.
        """
        self.local_env_vars = os.environ.copy()
        if project_envfile_path is None:
            env_file = ".accra_project_environment_variables"
        else:
            env_file = os.path.expanduser(project_envfile_path)
        env_file = os.path.join(os.getcwd(), env_file)
        print("Looking for the temp environment variables: in "+env_file)
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip() or line.strip().startswith("#"):
                    continue
                if "=" not in line:
                    continue  # Skip malformed lines
                key, value = line.strip().split("=", 1)
                self.local_env_vars[key] = value.strip()
                print("Setting "+key+" to "+value.strip())

    def ensure_py_interpreter_is_installed(self):
        """
        Ensure the python interpreter with version stored in self.python_version_venv is installed,
        otherwise it will be installed.
        """
        try:
            result = subprocess.run(
                ["pyenv", "versions", "--bare"],
                capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"[PyEnv] Failed to list installed versions: {e.stderr.strip()}") from e

        installed_versions = result.stdout.strip().splitlines()

        if re.fullmatch(r"\d+\.\d+", self.python_version_venv): # checks if version is in the format X.X
            match_found = any(v == self.python_version_venv or v.startswith(f"{self.python_version_venv}.") for v in installed_versions)
        else:
            # version in X.X.X so it has to match the exact version
            match_found = self.python_version_venv in installed_versions
        if match_found:
            print(f"[PyEnv] Python {self.python_version_venv} already installed")
        else:
            print(f"[PyEnv] Python {self.python_version_venv} not installed")
            self.install_python_interpreter()

        try:
            prefix_result = subprocess.run(
                ["pyenv", "prefix", self.python_version_venv],
                capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"[PyEnv] Failed to get prefix for version {self.python_version_venv}: {e.stderr.strip()}") from e

        prefix_path = prefix_result.stdout.strip()
        path_py_interpreter = os.path.join(prefix_path, "bin", "python")
        if not os.path.exists(path_py_interpreter):
            path_py_interpreter = os.path.join(prefix_path, "bin", "python3")
            if not os.path.exists(path_py_interpreter):
                raise FileExistsError("python interpreter does not exist")

        return path_py_interpreter

    def install_python_interpreter(self):
        """Install the Python interpreter with the necessary build flags"""
        print(f"[PyEnv] Installing Python {self.python_version_venv}")
        local_env = os.environ.copy()

        # For macOS:
        if sys.platform == 'darwin':
            # This ensures pip and other tools are properly bundled
            local_env['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
        elif sys.platform == 'linux':
            local_env['PYTHON_CONFIGURE_OPTS'] = '--enable-shared'
        else:
            raise OSError("current OS not supported")
        try:
            subprocess.run(
                ["pyenv", "install", self.python_version_venv],
                capture_output=True, text=True, env=local_env, check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"[PyEnv] Initial install failed: {e.stderr.strip()}\n", "[PyEnv] Retrying with verbose output...", file=sys.stderr)
            try:
                subprocess.run(
                    ["pyenv", "install", "-v", self.python_version_venv],
                    capture_output=True, text=True, env=local_env, check=True
                )
            except subprocess.CalledProcessError as e_verbose:
                raise RuntimeError(
                    f"[PyEnv] python {self.python_version_venv} installation failed, verbose error:\n{e_verbose.stderr.strip()}"
                ) from e

        print(f"[PyEnv] Python {self.python_version_venv} installed successfully")

    def handle_venv_creation(self):
        """
        Handles the creation of python virtual environment.
        If an error is raised during the creation or initialization using a python version,
        the process is restarted with the previous available version.
        If there is an error, the venv created is deleted.
        The process starts with the latest version in supported_py_versions.
        """
        has_worked = False
        # from latest to oldest version
        for i_version in range(len(self.supported_py_versions)-1, -1, -1):
            self.python_version_venv = self.supported_py_versions[i_version]
            self.venv_name = ".venv-py" + self.python_version_venv
            try:
                print("-" * 4 + f" creating venv using python {self.supported_py_versions[i_version]} " + "-" * 4)
                self.create_venv()
                has_worked = True
                break
            except Exception as e:
                print(f"error during the venv creation using python {self.supported_py_versions[i_version]}:\n{e}")
                path_venv_dir = os.path.join(self.path_dest_folder, self.venv_name)
                if os.path.exists(os.path.realpath(path_venv_dir)):
                    shutil.rmtree(os.path.realpath(path_venv_dir))
                    print(f"removed directory {path_venv_dir}")
        if not has_worked:
            raise RuntimeError("no python version has worked")

    def create_venv(self):
        """Creates a virtual environment"""
        path_venv_dir = os.path.join(self.path_dest_folder, self.venv_name)
        # Ensure the python interpreter is the proper one
        path_py_interpreter = self.ensure_py_interpreter_is_installed()

        try:
            subprocess.run(
                [path_py_interpreter, "-m", "venv", path_venv_dir],
                capture_output=True, text=True, check=True
            )
            self.update_venv_attributes(path_venv_dir=path_venv_dir)
        except subprocess.CalledProcessError as e:
            # Usually fails the module ensurepip when using the debugger, because it modifies the environment causing conflicts
            print(f"[VirtualEnv] Creation failed: {e.stderr.strip()}", file=sys.stderr)
            # Venv partially created
            if os.path.exists(path_venv_dir) and not os.path.exists(os.path.join(path_venv_dir, "bin", "pip")):
                print("[VirtualEnv] Venv partially created, installing pip")
                self.update_venv_attributes(path_venv_dir=path_venv_dir)
                self.install_pip()
            else:
                raise e
        except Exception as e:
            raise RuntimeError(f"[Error] An unexpected error occurred while creating the virtual environment:\n{str(e)}") from e
        # If code arrives here then the venv is created successfully
        print(f"[VirtualEnv] Creation venv successful: {self.venv_name} located in {self.venv_path}")
        self.install_predefined_package()

    def update_venv_attributes(self, path_venv_dir):
        self.update_venv_path(path_venv_dir)
        self.update_py_venv_exe_path()

    def update_venv_path(self, venv_path):
        """Update the virtual environment path"""
        self.venv_path = venv_path

    def update_py_venv_exe_path(self):
        path_py_interpreter = os.path.join(self.venv_path, "bin", "python")
        if os.path.exists(path_py_interpreter):
            self.py_venv_exe = path_py_interpreter
        elif os.path.exists(os.path.join(self.venv_path, "bin", "python3")):
            self.py_venv_exe = os.path.join(self.venv_path, "bin", "python3")
        else:
            raise FileExistsError("python interpreter does not exist")

    def remove_venv(self):
        """Remove the virtual environment directory and subdirectories"""
        is_removed = True
        if self.venv_path and os.path.exists(self.venv_path):
            print(f"[VirtualEnv] Start removal...")  # noqa: F541
            try:
                shutil.rmtree(self.venv_path)
                print(f"[VirtualEnv] Removed virtual environment: {self.venv_path}", file=sys.stdout)
            except OSError as o:
                print(f"[Error] Failed to remove virtual environment {self.venv_path}: {o.strerror}:", file=sys.stderr)
                is_removed = False
            except Exception as e:
                print(f"[Error] Failed to remove virtual environment: {e}", file=sys.stderr)
                is_removed = False
        return is_removed

    def install_predefined_package(self):
        """Initialize the virtual environment with packages used by the analyzers"""
        predefined_package = ["memray", "PyGithub", "typer", "scalene", "bertopic", "hf_xet"]
        for p in predefined_package:
            self.install_package(p)

    def install_pip(self):
        """Install pip into the virtual environment if ensurepip fails."""
        try:
            import urllib.request
            import tempfile

            print("[Install Pip] Attempting to install pip manually...", file=sys.stderr)
            if 3.2 <= float(self.python_version_venv) <= 3.8:
                url = f"https://bootstrap.pypa.io/pip/{str(self.python_version_venv)}/get-pip.py"
            else:
                url = "https://bootstrap.pypa.io/get-pip.py"
            with tempfile.NamedTemporaryFile("wb", delete=False) as f:
                f.write(urllib.request.urlopen(url).read())
                script = f.name
                subprocess.run([self.py_venv_exe, f.name], check=True, env=self.local_env_vars)
            print("[Install Pip] Successfully installed pip manually.", file=sys.stderr)
        except Exception as e:
            raise RuntimeError(f"[Install Pip] Failed to install pip: {e}") from e
        finally:
            if 'script' in locals() and os.path.exists(script):
                os.remove(script)

    def initialize_project(self):
        """Initialize the virtual environment with the initialization of the project, done with pip and pyproject.toml or setup.py"""
        print("trying to initialize the project...")
        try:
            command = [self.py_venv_exe, "-m", "pip", "install", self.path_repository]
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print("error during initialization: ", e)
