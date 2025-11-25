"""
venv_create.py - Virtual Environment Creation and Dependency Installation

This module handles creating isolated Python virtual environments and installing
dependencies from cloned repositories. It supports pyproject.toml, setup.py,
and requirements.txt based projects.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple, List


class VenvCreationError(Exception):
    """Custom exception for venv creation failures."""
    pass


class DependencyInstallError(Exception):
    """Custom exception for dependency installation failures."""
    pass


def get_venv_python(venv_path: str) -> str:
    """
    Get the Python executable path inside a virtual environment.
    
    Args:
        venv_path: Path to the virtual environment directory.
        
    Returns:
        Path to the Python executable inside the venv.
    """
    if os.name == 'nt':  # Windows
        return os.path.join(venv_path, 'Scripts', 'python.exe')
    else:  # Unix/macOS
        return os.path.join(venv_path, 'bin', 'python')


def get_venv_pip(venv_path: str) -> str:
    """
    Get the pip executable path inside a virtual environment.
    
    Args:
        venv_path: Path to the virtual environment directory.
        
    Returns:
        Path to the pip executable inside the venv.
    """
    if os.name == 'nt':  # Windows
        return os.path.join(venv_path, 'Scripts', 'pip.exe')
    else:  # Unix/macOS
        return os.path.join(venv_path, 'bin', 'pip')


def run_command(
    cmd: List[str],
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    description: str = "Command"
) -> Tuple[int, str, str]:
    """
    Run a subprocess command with proper error handling.
    
    Args:
        cmd: Command and arguments as a list.
        cwd: Working directory for the command.
        env: Environment variables dictionary.
        description: Human-readable description of the command.
        
    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"{description} timed out after 600 seconds"
    except Exception as e:
        return -1, "", f"{description} failed with exception: {str(e)}"


def create_virtual_environment(
    venv_path: str,
    python_executable: Optional[str] = None
) -> str:
    """
    Create a new virtual environment.
    
    Args:
        venv_path: Path where the virtual environment should be created.
        python_executable: Python interpreter to use. Defaults to sys.executable.
        
    Returns:
        Path to the Python executable inside the created venv.
        
    Raises:
        VenvCreationError: If venv creation fails.
    """
    if python_executable is None:
        python_executable = sys.executable
    
    # Remove existing venv if present
    if os.path.exists(venv_path):
        print(f"[INFO] Removing existing virtual environment at {venv_path}...")
        shutil.rmtree(venv_path)
    
    print(f"[INFO] Creating virtual environment at {venv_path} using {python_executable}...")
    
    # Create the virtual environment
    returncode, stdout, stderr = run_command(
        [python_executable, "-m", "venv", venv_path],
        description="venv creation"
    )
    
    if returncode != 0:
        raise VenvCreationError(f"Failed to create virtual environment: {stderr}")
    
    # Verify the venv Python exists
    venv_python = get_venv_python(venv_path)
    if not os.path.exists(venv_python):
        raise VenvCreationError(f"Venv Python not found at {venv_python}")
    
    # Verify the venv Python works
    returncode, stdout, stderr = run_command(
        [venv_python, "--version"],
        description="venv Python version check"
    )
    
    if returncode != 0:
        raise VenvCreationError(f"Venv Python not working: {stderr}")
    
    print(f"[INFO] Virtual environment Python: {stdout.strip()}")
    print(f"[SUCCESS] Virtual environment created at {venv_path}")
    
    return venv_python


def upgrade_build_tools(venv_python: str) -> None:
    """
    Upgrade pip, setuptools, and wheel in the virtual environment.
    
    Args:
        venv_python: Path to the venv's Python executable.
        
    Raises:
        DependencyInstallError: If upgrade fails.
    """
    print("[INFO] Upgrading pip, setuptools, and wheel in the virtual environment...")
    
    # Create environment with SETUPTOOLS_USE_DISTUTILS to avoid conflicts
    env = os.environ.copy()
    env["SETUPTOOLS_USE_DISTUTILS"] = "stdlib"
    
    returncode, stdout, stderr = run_command(
        [venv_python, "-m", "pip", "install", "--upgrade", 
         "pip", "setuptools", "wheel"],
        env=env,
        description="build tools upgrade"
    )
    
    if returncode != 0:
        print(f"[WARNING] Build tools upgrade had issues: {stderr}")
        # Don't fail here, try to continue
    else:
        print("[SUCCESS] Core build tools upgraded.")


def preinstall_build_dependencies(venv_python: str, dependencies: List[str]) -> None:
    """
    Pre-install critical build dependencies that are commonly needed.
    
    Args:
        venv_python: Path to the venv's Python executable.
        dependencies: List of package names to pre-install.
    """
    env = os.environ.copy()
    env["SETUPTOOLS_USE_DISTUTILS"] = "stdlib"
    
    print(f"[INFO] Pre-installing critical build dependencies: {', '.join(dependencies)}...")
    
    for dep in dependencies:
        returncode, stdout, stderr = run_command(
            [venv_python, "-m", "pip", "install", "--no-cache-dir", dep],
            env=env,
            description=f"pre-install {dep}"
        )
        
        if returncode == 0:
            print(f"[SUCCESS] '{dep}' pre-installed.")
        else:
            print(f"[WARNING] Failed to pre-install '{dep}': {stderr[:200]}")


def detect_install_method(repo_path: str) -> str:
    """
    Detect the best installation method for a repository.
    
    Args:
        repo_path: Path to the cloned repository.
        
    Returns:
        One of: 'pyproject', 'setup', 'requirements', 'none'
    """
    repo_path = Path(repo_path)
    
    if (repo_path / "pyproject.toml").exists():
        print("[INFO] Found pyproject.toml. Will install via `pip install .`.")
        return 'pyproject'
    elif (repo_path / "setup.py").exists():
        print("[INFO] Found setup.py. Will install via `pip install .`.")
        return 'setup'
    elif (repo_path / "requirements.txt").exists():
        print("[INFO] Found requirements.txt. Will install via `pip install -r requirements.txt`.")
        return 'requirements'
    else:
        print("[WARNING] No standard dependency file found.")
        return 'none'


def install_from_pyproject_or_setup(
    venv_python: str,
    repo_path: str,
    editable: bool = False
) -> bool:
    """
    Install a package from pyproject.toml or setup.py.
    
    Args:
        venv_python: Path to the venv's Python executable.
        repo_path: Path to the repository.
        editable: Whether to install in editable mode.
        
    Returns:
        True if installation succeeded, False otherwise.
    """
    env = os.environ.copy()
    env["SETUPTOOLS_USE_DISTUTILS"] = "stdlib"
    
    # Strategy 1: Try editable install if requested
    if editable:
        print(f"[INFO] Attempting editable install from {repo_path}...")
        returncode, stdout, stderr = run_command(
            [venv_python, "-m", "pip", "install", "--no-cache-dir", "-e", "."],
            cwd=repo_path,
            env=env,
            description="editable install"
        )
        
        if returncode == 0:
            print("[SUCCESS] Editable install completed.")
            return True
        else:
            print(f"[WARNING] Editable install failed, trying regular install...")
            print(f"  Error: {stderr[:300]}")
    
    # Strategy 2: Regular install without build isolation
    print(f"[INFO] Installing dependencies using 'pip install .' from {repo_path}...")
    returncode, stdout, stderr = run_command(
        [venv_python, "-m", "pip", "install", "--no-cache-dir", "--no-build-isolation", "."],
        cwd=repo_path,
        env=env,
        description="regular install (no build isolation)"
    )
    
    if returncode == 0:
        print("[SUCCESS] Package installed successfully.")
        return True
    
    print(f"[WARNING] Regular install failed: {stderr[:300]}")
    
    # Strategy 3: Try with build isolation
    print("[INFO] Retrying with build isolation...")
    returncode, stdout, stderr = run_command(
        [venv_python, "-m", "pip", "install", "--no-cache-dir", "."],
        cwd=repo_path,
        env=env,
        description="install with build isolation"
    )
    
    if returncode == 0:
        print("[SUCCESS] Package installed with build isolation.")
        return True
    
    print(f"[WARNING] Build isolation install failed: {stderr[:300]}")
    
    # Strategy 4: Try installing just the dependencies from pyproject.toml
    pyproject_path = Path(repo_path) / "pyproject.toml"
    if pyproject_path.exists():
        print("[INFO] Attempting to extract and install dependencies from pyproject.toml...")
        deps = extract_dependencies_from_pyproject(str(pyproject_path))
        if deps:
            returncode, stdout, stderr = run_command(
                [venv_python, "-m", "pip", "install", "--no-cache-dir"] + deps,
                env=env,
                description="install extracted dependencies"
            )
            if returncode == 0:
                print("[SUCCESS] Dependencies from pyproject.toml installed.")
                return True
    
    return False


def extract_dependencies_from_pyproject(pyproject_path: str) -> List[str]:
    """
    Extract dependencies from pyproject.toml file.
    
    Args:
        pyproject_path: Path to pyproject.toml file.
        
    Returns:
        List of dependency strings.
    """
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            print("[WARNING] Neither tomllib nor tomli available for parsing pyproject.toml")
            return []
    
    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        
        deps = []
        
        # Check project.dependencies
        if "project" in data and "dependencies" in data["project"]:
            deps.extend(data["project"]["dependencies"])
        
        # Check build-system.requires
        if "build-system" in data and "requires" in data["build-system"]:
            deps.extend(data["build-system"]["requires"])
        
        return deps
    except Exception as e:
        print(f"[WARNING] Failed to parse pyproject.toml: {e}")
        return []


def install_from_requirements(venv_python: str, repo_path: str) -> bool:
    """
    Install dependencies from requirements.txt.
    
    Args:
        venv_python: Path to the venv's Python executable.
        repo_path: Path to the repository.
        
    Returns:
        True if installation succeeded, False otherwise.
    """
    env = os.environ.copy()
    env["SETUPTOOLS_USE_DISTUTILS"] = "stdlib"
    
    requirements_file = os.path.join(repo_path, "requirements.txt")
    
    print(f"[INFO] Installing from requirements.txt...")
    returncode, stdout, stderr = run_command(
        [venv_python, "-m", "pip", "install", "--no-cache-dir", "-r", requirements_file],
        env=env,
        description="requirements.txt install"
    )
    
    if returncode == 0:
        print("[SUCCESS] Requirements installed successfully.")
        return True
    
    print(f"[ERROR] Failed to install requirements: {stderr[:500]}")
    return False


def setup_venv_and_install(
    venv_path: str,
    repo_path: str,
    python_executable: Optional[str] = None,
    preinstall_deps: Optional[List[str]] = None
) -> Tuple[bool, str]:
    """
    Main function to create venv and install all dependencies.
    
    Args:
        venv_path: Path where the virtual environment should be created.
        repo_path: Path to the cloned repository.
        python_executable: Python interpreter to use. Defaults to sys.executable.
        preinstall_deps: List of packages to pre-install before main installation.
        
    Returns:
        Tuple of (success: bool, venv_python_path: str)
    """
    if preinstall_deps is None:
        preinstall_deps = ["numpy", "scipy"]
    
    try:
        # Step 1: Create the virtual environment
        venv_python = create_virtual_environment(venv_path, python_executable)
        
        # Step 2: Upgrade build tools (pip, setuptools, wheel)
        upgrade_build_tools(venv_python)
        
        # Step 3: Pre-install critical build dependencies
        if preinstall_deps:
            preinstall_build_dependencies(venv_python, preinstall_deps)
        
        # Step 4: Detect installation method
        install_method = detect_install_method(repo_path)
        
        # Step 5: Install based on detected method
        success = False
        
        if install_method in ('pyproject', 'setup'):
            success = install_from_pyproject_or_setup(venv_python, repo_path)
        elif install_method == 'requirements':
            success = install_from_requirements(venv_python, repo_path)
        else:
            print("[WARNING] No installation method detected. Venv created but no deps installed.")
            success = True  # Venv created successfully, just no deps
        
        if success:
            print(f"[SUCCESS] Virtual environment ready at: {venv_path}")
            return True, venv_python
        else:
            print(f"[ERROR] Dependency installation failed.")
            return False, venv_python
            
    except VenvCreationError as e:
        print(f"[ERROR] Virtual environment creation failed: {e}")
        return False, ""
    except Exception as e:
        print(f"[ERROR] Unexpected error during venv setup: {e}")
        return False, ""


# For backwards compatibility and direct usage
def create_venv_and_install_dependencies(
    venv_path: str,
    repo_path: str,
    python_executable: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Backwards-compatible wrapper for setup_venv_and_install.
    
    Args:
        venv_path: Path where the virtual environment should be created.
        repo_path: Path to the cloned repository.
        python_executable: Python interpreter to use.
        
    Returns:
        Tuple of (success: bool, venv_python_path: str)
    """
    return setup_venv_and_install(venv_path, repo_path, python_executable)


if __name__ == "__main__":
    # Example usage / testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Create venv and install dependencies")
    parser.add_argument("repo_path", help="Path to the repository")
    parser.add_argument("--venv-path", default=".venv_repro", help="Path for virtual environment")
    parser.add_argument("--python", default=None, help="Python executable to use")
    
    args = parser.parse_args()
    
    success, venv_python = setup_venv_and_install(
        args.venv_path,
        args.repo_path,
        args.python
    )
    
    if success:
        print(f"\n✅ Setup complete! Activate with:")
        if os.name == 'nt':
            print(f"   {args.venv_path}\\Scripts\\activate")
        else:
            print(f"   source {args.venv_path}/bin/activate")
        sys.exit(0)
    else:
        print("\n❌ Setup failed!")
        sys.exit(1)
