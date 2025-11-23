import argparse
import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Optional, List
from demo_creator import DemoCreator
import shutil 

# Configuration
# Define the temporary directory where files will be processed and repositories cloned.
# This path is used by the Downloader class's __init__ method by default.
TMP_DIR = "tmp"
PDF_OUTPUT_FILENAME = Path(TMP_DIR) / "downloaded_paper.pdf"
VENV_DIR = Path(TMP_DIR) / ".venv_repro"
REQUIREMENTS_FILE = Path(TMP_DIR) / "requirements.txt"

from downloader import Downloader
from paper_extracter import PaperParser

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

def create_demo_from_readme(repo_path: Path):
    """
    Step 4: Call Constructor to generate a demo script from the cloned repo.
    """
    print(f"\n--- STEP 4: Creating Demo from Readme via Constructor LLM... ---")

    if not repo_path or not repo_path.is_dir():
        print("[WARNING] Skipping demo creation: Repository path is invalid or clone failed.")
        return

    creator = DemoCreator(repo_path)
    demo_path = creator.generate_demo()

    if demo_path:
        print(f"[INFO] Demo script generated at: {demo_path}")
        print("[INFO] You can now run it with something like:")
        print(f"       cd {repo_path}")
        print(f"       python {demo_path.name}")
    else:
        print("[WARNING] Demo generation failed or returned empty code.")

def run_pipeline(input_path: str):
    """
    The main orchestration function for the pipeline.
    """
    downloader = Downloader(target_dir=str(TMP_DIR))
    pdf_path: Optional[Path] = None
    
    # Ensure the TMP_DIR exists before starting operations
    Path(TMP_DIR).mkdir(exist_ok=True) 

    try:
        # STEP 1: Handle Input (URL vs. Local PDF)
        if input_path.lower().startswith('http'):
            print("--- STEP 1: Input is a URL. Downloading PDF... ---")
            if downloader.download_pdf(input_path, str(PDF_OUTPUT_FILENAME)):
                pdf_path = PDF_OUTPUT_FILENAME
            else:
                raise ConnectionError(f"Failed to download PDF from: {input_path}")
        else:
            print("--- STEP 1: Input is a local PDF file. Skipping download... ---\n[INFO] Using local PDF file: {input_path}")
            pdf_path = Path(input_path)
            if not pdf_path.is_file():
                raise FileNotFoundError(f"Local file not found at: {pdf_path}")

        if not pdf_path:
                raise ValueError("PDF file path could not be determined.")

        # STEP 2: Parse PDF for GitHub Repository URL
        print("\n--- STEP 2: Parsing PDF for GitHub Repository URL... ---")
        github_links: list[str] = PaperParser(str(pdf_path)).extract_github_link()
        
        if not github_links:
            print("[WARNING] No GitHub link found in the paper. Pipeline stops.")
            return

        github_url = github_links[0]
        print(f"[SUCCESS] Found GitHub URL: {github_url}")

        # STEP 3: Cloning GitHub Repository
        print("\n--- STEP 3: Cloning GitHub Repository... ---")
        clone_success = downloader.download(github_url)
        cloned_repo_path = Path(TMP_DIR) 

        if not clone_success:
            raise RuntimeError(f"Git clone failed for repository: {github_url}")
        
        print(f"[SUCCESS] Repository successfully cloned into: {cloned_repo_path}")
        
        # STEP 4: Dependency Extraction (now integrated into Step 5 using pipreqs)
        print("\n--- STEP 4: Dependency Extraction is integrated into Step 5 using pipreqs. ---")

        # STEP 5: Virtual Environment Setup & Installation
        create_and_install_venv(cloned_repo_path)

        # STEP 6: Demo Creation
        create_demo_from_readme(cloned_repo_path)

    # --- Error Handling ---
    except FileNotFoundError as e:
        print(f"[ERROR] Required file not found: {e}", file=sys.stderr)
        sys.exit(1)
    except ConnectionError as e:
        print(f"[ERROR] Network operation failed: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"[ERROR] Data validation failed: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"[ERROR] Command execution failed (e.g., git, venv, or pipreqs): {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[FATAL] An unexpected error occurred: {type(e).__name__} - {e}", file=sys.stderr)
        sys.exit(1)
        
    finally:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A pipeline orchestrator for processing research papers (URL or PDF) to generate code demos."
    )
    parser.add_argument(
        "input",
        type=str,
        help="The input source, which can be either a full URL (e.g., http://arxiv.org/...) or a local path to a PDF file (e.g., ./paper.pdf)."
    )
    
    args = parser.parse_args()
    
    print(f"\n--- Starting Pipeline Execution with Input: {args.input} ---")
    
    # Start timing
    start_time = time.time()
    
    run_pipeline(args.input)
    
    # End timing and report duration
    end_time = time.time()
    duration = end_time - start_time
    print(f"\n--- Pipeline Complete in {duration:.2f} seconds. ---")
    
    # Example of how to run this script from the command line:
    # python main.py "http://example.com/paper.pdf"
    # python main.py "./local_paper.pdf"