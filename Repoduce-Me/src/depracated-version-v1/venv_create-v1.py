import sys
import subprocess
from pathlib import Path
from typing import List
import shutil 
import os
import re

# Configuration constants (must match main.py)
TMP_DIR = "tmp"
VENV_DIR = Path(TMP_DIR) / ".venv_repro"
REQUIREMENTS_FILE = Path(TMP_DIR) / "requirements.txt"
REQUIREMENTS_FILTERED_FILE = Path(TMP_DIR) / "requirements_filtered.txt"

BASE_PYTHON = os.environ.get("REPRO_PYTHON", sys.executable)

def get_venv_python_executable(venv_path: Path) -> Path:
    """Determines the path to the venv's Python executable based on the operating system."""
    venv_path = venv_path.resolve()
    
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

def _normalize_requirement_line(raw: str) -> str | None:
    """
    Normalize problematic requirement specs for compatibility with the current Python.

    - Strip CUDA suffixes like '+cu121'
    - Relax numpy pins (let pip pick a compatible version)
    - Relax torch pins (and strip CUDA suffixes)
    - Ignore nested '-r otherfile.txt' includes
    """
    line = raw.strip()
    if not line or line.startswith("#"):
        return None

    # Ignore nested requirement includes for now
    if line.lower().startswith("-r "):
        print(f"[WARNING] Ignoring nested requirements include: {line}")
        return None

    # Strip CUDA local version tags: 'torch==2.1.2+cu121' -> 'torch==2.1.2'
    line = re.sub(r"\+cu[0-9]+", "", line, flags=re.IGNORECASE)

    # Extract package name best-effort
    m = re.match(r"^\s*([A-Za-z0-9_\-]+)", line)
    name = m.group(1).lower() if m else ""

    if name == "numpy":
        # Completely unpin numpy
        print(f"[INFO] Normalizing numpy requirement: '{raw.strip()}' -> 'numpy'")
        return "numpy"

    if name == "torch":
        # Completely unpin torch; rely on pip's latest compatible wheel
        print(f"[INFO] Normalizing torch requirement: '{raw.strip()}' -> 'torch'")
        return "torch"

    return line

def _build_filtered_requirements() -> None:
    """
    Read REQUIREMENTS_FILE, normalize each line, and write REQUIREMENTS_FILTERED_FILE.
    """
    if not REQUIREMENTS_FILE.exists():
        print(f"[INFO] No {REQUIREMENTS_FILE} present; skipping requirement normalization.")
        return

    normalized: list[str] = []
    with REQUIREMENTS_FILE.open("r", encoding="utf-8") as f:
        for raw in f:
            norm = _normalize_requirement_line(raw)
            if norm:
                normalized.append(norm)

    if not normalized:
        print("[WARNING] No dependencies remained after normalization.")
    else:
        print(
            f"[INFO] Writing {len(normalized)} normalized dependencies to {REQUIREMENTS_FILTERED_FILE}."
        )

    with REQUIREMENTS_FILTERED_FILE.open("w", encoding="utf-8") as f:
        for dep in normalized:
            f.write(dep + "\n")

def create_and_install_venv(
    repo_dir: str,
    use_repo_install: bool,
    has_extracted_requirements: bool,
):
    """
    Creates a virtual environment and installs dependencies using the most appropriate method:
    1. If use_repo_install is True (pyproject.toml or setup.py exists), use `pip install .`.
    2. Otherwise, use `pip install -r requirements_filtered.txt` (normalized deps).
    """
    # Clean up the previous filtered file if it exists
    if REQUIREMENTS_FILTERED_FILE.exists():
        os.remove(REQUIREMENTS_FILTERED_FILE)
    print(f"[INFO] Creating virtual environment at {VENV_DIR} using {BASE_PYTHON}...")
    execute_subprocess(
        [BASE_PYTHON, "-m", "venv", str(VENV_DIR)],
        "Virtual environment creation",
    )
    
    python_executable = get_venv_python_executable(VENV_DIR)

    # --- 5a. Upgrade Core Build Tools ---
    print("[INFO] Upgrading pip, setuptools, and wheel in the virtual environment...")
    execute_subprocess(
        [str(python_executable), '-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel'],
        "Upgrade of core build tools"
    )
    print("[SUCCESS] Core build tools upgraded.")

    # --- 5b. Pre-installing Critical Build Dependencies (numpy, scipy) ---
    # This step is crucial for scientific packages that need these installed before compilation.
    packages_to_preinstall = ['numpy', 'scipy']
    print(f"[INFO] Pre-installing critical build dependencies: {', '.join(packages_to_preinstall)}...")
    
    # Prioritize numpy and scipy first if they are on the list
    for package in ['numpy', 'scipy']:
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
        ]
        
        execute_subprocess(
            install_command, 
            "Final dependency installation (pip install .)",
            # Crucially, run the installation from the cloned repo directory
            cwd=str(repo_path) 
        )

    elif has_extracted_requirements:
        # Strategy 2: Use normalized requirements file
        _build_filtered_requirements()

        if REQUIREMENTS_FILTERED_FILE.exists() and REQUIREMENTS_FILTERED_FILE.stat().st_size > 0:
            print(
                f"[INFO] Installing dependencies from {REQUIREMENTS_FILTERED_FILE.name} into venv..."
            )
            install_command = [
                str(python_executable),
                "-m",
                "pip",
                "install",
                "--no-cache-dir",
                "-r",
                str(REQUIREMENTS_FILTERED_FILE),
            ]
            execute_subprocess(
                install_command,
                "Final dependency installation (requirements file)",
            )
        else:
            print(
                "[WARNING] Skipping main dependency installation: filtered requirements file is missing or empty."
            )
            return
