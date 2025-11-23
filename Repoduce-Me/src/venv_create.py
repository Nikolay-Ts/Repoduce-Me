import sys
import subprocess
from pathlib import Path
from typing import List
import shutil 

TMP_DIR = "tmp"
PDF_OUTPUT_FILENAME = Path(TMP_DIR) / "downloaded_paper.pdf"
VENV_DIR = Path(TMP_DIR) / ".venv_repro"
REQUIREMENTS_FILE = Path(TMP_DIR) / "requirements.txt"


def get_venv_python_executable(venv_path: Path) -> Path:
    """Determines the path to the venv's Python executable based on the operating system."""
    if sys.platform.startswith('win'):
        return venv_path / "Scripts" / "python.exe"
    else:
        # Assumes Linux/macOS
        return venv_path / "bin" / "python"


def execute_subprocess(command: List[str], error_message: str):
    """Utility to run a subprocess command with check=True and custom error handling."""
    try:
        # check=True raises CalledProcessError if the command fails
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return result
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] {error_message} (External command failed).", file=sys.stderr)
        # Print the error output for debugging
        print(f"Command: {' '.join(command)}", file=sys.stderr)
        print(f"Stderr:\n{e.stderr}", file=sys.stderr)
        raise RuntimeError(f"{error_message} failed.") from e
    except FileNotFoundError as e:
        print(f"[FATAL] System executable not found (e.g., 'python'): {e}", file=sys.stderr)
        raise RuntimeError(f"{error_message} failed.") from e
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}", file=sys.stderr)
        raise RuntimeError(f"{error_message} failed.") from e


def create_and_install_venv(repo_path: Path):
    """
    Implements the robust installation strategy:
    ... (omitted docstring for brevity)
    """
    print(f"\n--- STEP 5: Setting up Virtual Environment in {VENV_DIR.name}... ---")
    
    # --- 5a. Create the Virtual Environment ---
    # ADDED: Cleanup for the new VENV_DIR location.
    if VENV_DIR.exists():
        print(f"[INFO] Cleaning up existing Venv directory: {VENV_DIR.name}...")
        try:
            shutil.rmtree(VENV_DIR)
            print("[INFO] Venv directory cleaned.")
        except Exception as e:
            print(f"[WARNING] Could not remove Venv directory {VENV_DIR.name}: {e}")
            
    print(f"[INFO] Creating virtual environment at {VENV_DIR}...")
    execute_subprocess(
        [sys.executable, '-m', 'venv', str(VENV_DIR)],
        "Virtual environment creation"
    )
    print("[SUCCESS] Virtual environment created.")
    
    python_executable = get_venv_python_executable(VENV_DIR)

    # --- 5b. Install pipreqs into the Venv ---
    print(f"[INFO] Installing pipreqs into the temporary Venv (to analyze dependencies)...")
    execute_subprocess(
        [str(python_executable), '-m', 'pip', 'install', 'pipreqs'],
        "Installation of pipreqs"
    )
    print("[SUCCESS] pipreqs installed in Venv.")

    print(f"[INFO] Running pipreqs on the cloned repository ({repo_path}) to generate {REQUIREMENTS_FILE.name}...")
    
    ignore_paths = [
        str(repo_path / 'datasets'), 
        str(VENV_DIR)                
    ]
    ignore_path_str = ",".join(ignore_paths)

    pipreqs_command = [
        str(python_executable), 
        '-m', 
        'pipreqs.pipreqs', 
        str(repo_path), 
        '--savepath', 
        str(REQUIREMENTS_FILE),
        '--force',
        '--encoding', 'latin1',
        # Combine the --ignore flag and its argument using the '=' sign for robustness
        f'--ignore={ignore_path_str}' 
    ]
    
    execute_subprocess(
        pipreqs_command,
        "Requirement generation via pipreqs"
    )
    
    if not REQUIREMENTS_FILE.exists() or REQUIREMENTS_FILE.stat().st_size == 0:
        print("[WARNING] Requirements file is empty or not created. Skipping final dependency install.")
        return
        
    print(f"[SUCCESS] Dependencies analyzed and written to {REQUIREMENTS_FILE.name}.")


    # --- 5d. Install dependencies from the generated requirements.txt ---
    print(f"[INFO] Installing final dependencies from {REQUIREMENTS_FILE.name} into Venv...")
    
    install_command = [
        str(python_executable), 
        '-m', 
        'pip', 
        'install', 
        '--no-cache-dir', 
        '-r', 
        str(REQUIREMENTS_FILE),
        '--use-deprecated=legacy-resolver'
    ]
    
    execute_subprocess(
        install_command,
        "Final dependency installation"
    )
    
    print("[SUCCESS] All final dependencies installed successfully.")