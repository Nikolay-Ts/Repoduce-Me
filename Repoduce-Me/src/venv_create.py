import sys
import subprocess
from pathlib import Path
from typing import List
import shutil 
import os

# Configuration constants (must match main.py)
TMP_DIR = "tmp"
VENV_DIR = Path(TMP_DIR) / ".venv_repro"
REQUIREMENTS_FILE = Path(TMP_DIR) / "requirements.txt"
REQUIREMENTS_FILTERED_FILE = Path(TMP_DIR) / "requirements_filtered.txt"

def get_venv_python_executable(venv_path: Path) -> Path:
    """Determines the path to the venv's Python executable based on the operating system."""
    if sys.platform.startswith('win'):
        return venv_path / "Scripts" / "python.exe"
    else:
        # Assumes Linux/macOS
        return venv_path / "bin" / "python"


def execute_subprocess(command: List[str], error_message: str, cwd: str = None):
    """Utility to run a subprocess command with check=True and custom error handling."""
    try:
        # check=True raises CalledProcessError if the command fails
        result = subprocess.run(command, check=True, capture_output=True, text=True, cwd=cwd)
        return result
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] {error_message} (External command failed).", file=sys.stderr)
        # Print the error output for debugging
        print(f"Command: {' '.join(command)}", file=sys.stderr)
        print(f"Stderr:\n{e.stderr}", file=sys.stderr)
        raise RuntimeError(f"{error_message} failed.")


def create_and_install_venv(repo_dir: str, use_repo_install: bool, has_extracted_requirements: bool):
    """
    Creates a virtual environment and installs dependencies using the most appropriate method:
    1. If use_repo_install is True (pyproject.toml or setup.py exists), use `pip install .`.
    2. Otherwise, use `pip install -r requirements.txt`.
    """
    # Clean up the previous filtered file if it exists
    if REQUIREMENTS_FILTERED_FILE.exists():
        os.remove(REQUIREMENTS_FILTERED_FILE)
    
    # We copy REQUIREMENTS_FILE to REQUIREMENTS_FILTERED_FILE just for consistent logging 
    # if it was created by the extractor.
    if REQUIREMENTS_FILE.exists() and has_extracted_requirements:
        shutil.copy(REQUIREMENTS_FILE, REQUIREMENTS_FILTERED_FILE) 

    print(f"[INFO] Creating virtual environment at {VENV_DIR}...")
    execute_subprocess([sys.executable, '-m', 'venv', str(VENV_DIR)], "Virtual environment creation")
    print("[SUCCESS] Virtual environment created.")
    
    python_executable = get_venv_python_executable(VENV_DIR)

    # --- 5a. Upgrade Core Build Tools ---
    print("[INFO] Upgrading pip, setuptools, and wheel in the virtual environment...")
    execute_subprocess(
        [str(python_executable), '-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel'],
        "Upgrade of core build tools"
    )
    print("[SUCCESS] Core build tools upgraded.")

    # --- 5b. Pre-installing Critical Build Dependencies (Cython, numpy, scipy) ---
    # This step is crucial for scientific packages that need these installed before compilation.
    packages_to_preinstall = ['Cython', 'numpy', 'scipy']
    print(f"[INFO] Pre-installing critical build dependencies: {', '.join(packages_to_preinstall)}...")
    
    # Prioritize numpy and scipy first if they are on the list
    for package in ['numpy', 'scipy', 'Cython']:
        if package in packages_to_preinstall:
            try:
                execute_subprocess(
                    [str(python_executable), '-m', 'pip', 'install', package],
                    f"Pre-installation of {package}"
                )
                print(f"[SUCCESS] '{package}' pre-installed.")
                packages_to_preinstall.remove(package)
            except Exception as e:
                # Log warning and continue to main installation
                print(f"[WARNING] Failed to pre-install {package}: {e}. Proceeding with main installation.", file=sys.stderr)

    # --- 5c. Main Dependency Installation ---
    install_command: List[str]
    repo_path = Path(repo_dir)

    if use_repo_install:
        # Strategy 1: Use pip install . on the repository directory
        print(f"[INFO] Installing dependencies using 'pip install .' from {repo_path}...")
        
        # We need to run the command from the repo directory (cwd=repo_dir)
        install_command = [
            str(python_executable), 
            '-m', 
            'pip', 
            'install', 
            '--no-cache-dir', 
            str(repo_path),
            '--no-build-isolation'
        ]
        
        execute_subprocess(
            install_command, 
            "Final dependency installation (pip install .)",
            # Crucially, run the installation from the cloned repo directory
            cwd=str(repo_path) 
        )

    elif has_extracted_requirements and REQUIREMENTS_FILTERED_FILE.exists() and REQUIREMENTS_FILTERED_FILE.stat().st_size > 0:
        # Strategy 2: Use pip install -r requirements.txt (either existing or dynamically generated)
        print(f"[INFO] Installing dependencies from {REQUIREMENTS_FILTERED_FILE.name} into Venv...")
        
        install_command = [
            str(python_executable), 
            '-m', 
            'pip', 
            'install', 
            '--no-cache-dir', 
            '-r', 
            str(REQUIREMENTS_FILTERED_FILE),
            '--no-build-isolation',
        ]
        
        execute_subprocess(
            install_command, 
            "Final dependency installation (requirements file)"
        )
    else:
        print("[WARNING] Skipping main dependency installation: No project file (pyproject.toml/setup.py) found, and extracted requirements list is empty.")
        return # Skip success message if installation was skipped
        
    print("[SUCCESS] All dependencies successfully installed.")