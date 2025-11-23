import argparse
import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Optional, List
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
from demo_creator import DemoCreator
from venv_create import create_and_install_venv

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
        DemoCreator.generate_demo(cloned_repo_path)

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