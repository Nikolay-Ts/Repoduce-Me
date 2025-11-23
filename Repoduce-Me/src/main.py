"""
USAGE:
    python main.py <pdf_path_or_url>
        - Clones into workspace/<repo_name> (persistent)
        - tmp/ is used for venv + intermediate artifacts
        - No cleanup is performed unless explicitly requested

OPTIONAL FLAGS:
    --tmp
        Clone the repository into tmp/repo (ephemeral) instead of workspace/.
    
    --cleanup-tmp
        Remove only the tmp/ directory after pipeline completion.
    
    --cleanup-workspace
        Remove only the workspace/ directory after pipeline completion.

    --cleanup-all
        Convenience option. Removes BOTH tmp/ and workspace/.
        Equivalent to: --cleanup-tmp --cleanup-workspace
"""

import argparse
import sys
import time
import shutil
from pathlib import Path
from typing import Optional

from downloader import Downloader
from paper_extracter import PaperParser
from demo_creator import DemoCreator
from venv_create import create_and_install_venv
from requirements_extract import RequirementsExtractor


TMP_DIR = "tmp"
PDF_OUTPUT_FILENAME = Path(TMP_DIR) / "downloaded_paper.pdf"

WORKSPACE_DIR = "workspace"

VENV_DIR = Path(TMP_DIR) / ".venv_repro"
REQUIREMENTS_FILE = Path(TMP_DIR) / "requirements.txt"


def _parse_repo_name_from_github_url(github_url: str) -> str:
    """
    Extract a reasonable repo directory name from a GitHub URL.
    """
    # Strips everything up to the last slash and removes '.git' if present
    name = github_url.split('/')[-1]
    if name.lower().endswith('.git'):
        name = name[:-4]
    return name or "cloned_repo"


def run_pipeline(input_path: str, github_link: str,  istmp: bool, cleanup_tmp: bool, cleanup_workspace: bool):
    """
    The main orchestration function for the pipeline.
    """
    # Initialize Downloader, using TMP_DIR for PDF/default operations
    downloader = Downloader(target_dir=str(TMP_DIR))
    pdf_path: Optional[Path] = None
    repo_target_path: Path # Initialize outside try/except for cleanup reference

    # Ensure the TMP_DIR exists before starting operations (for PDF/venv)
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
            print(f"--- STEP 1: Input is a local PDF file. Skipping download... ---\n[INFO] Using local PDF file: {input_path}")
            pdf_path = Path(input_path)
            if not pdf_path.is_file():
                raise FileNotFoundError(f"Local file not found at: {pdf_path}")

        if not pdf_path:
                raise ValueError("PDF file path could not be determined.")

        # STEP 2: Parse PDF for GitHub Repository URL
        print("\n--- STEP 2: Parsing PDF for GitHub Repository URL... ---")
        parser = PaperParser(str(pdf_path))

        github_url: str
        if github_link is None:

            github_links: list[str] = parser.extract_github_link()
            
            
            if not github_links:
                # Try to get the GitHub URL from the user-provided input URL itself
                if "github.com" in input_path.lower():
                    github_url = input_path
                    print(f"[INFO] Using input URL as GitHub URL: {github_url}")
                else:
                    print("[WARNING] No GitHub link found in the paper. Pipeline stops.")
                    return
            else:
                github_url = github_links[0]
                print(f"[SUCCESS] Found GitHub URL: {github_url}")
        else: 
            github_url = github_link 

        # Determine the final clone target path based on the flag
        if istmp:
            # Clone repo into tmp/repo
            repo_target_path = Path(TMP_DIR) / "repo"
        else:
            # Clone repo into workspace/<repo_name> (Persistent)
            repo_name = _parse_repo_name_from_github_url(github_url)
            repo_target_path = Path(WORKSPACE_DIR) / repo_name
            Path(WORKSPACE_DIR).mkdir(exist_ok=True) # Ensure workspace dir exists

        
        # STEP 3: Cloning GitHub Repository
        print("\n--- STEP 3: Cloning GitHub Repository... ---")
        # Ensure the parent directory is created before cloning (if it's not workspace/ or tmp/)
        repo_target_path.parent.mkdir(parents=True, exist_ok=True)

        # CRITICAL FIX: The downloader.download method now expects the target_path.
        clone_success = downloader.download(github_url, str(repo_target_path))
        
        if not clone_success:
            # The downloader already printed the error details
            raise RuntimeError(f"Git clone failed for repository: {github_url}")
        
        print(f"[SUCCESS] Repository successfully cloned into: {repo_target_path}")
        
        # STEP 4: Dependency Extraction
        print("\n--- STEP 4: Dependency Extraction using RequirementsExtractor... ---")
        extractor = RequirementsExtractor(output_dir=str(TMP_DIR))
        extractor.analyze_repo(repo_target_path)
        print(f"[SUCCESS] Dependencies written to: {REQUIREMENTS_FILE.name}")
        
        # STEP 5: Virtual Environment Setup & Installation
        print(f"\n--- STEP 5: Setting up Virtual Environment in {VENV_DIR.name}... ---")
        # Ensure venv_create is called with the correct path
        create_and_install_venv(repo_target_path)

        # STEP 6: Demo Creation
        print("\n--- STEP 6: Creating Demo from Readme via Constructor LLM... ---")
        creator = DemoCreator(repo_target_path)
        demo_path = creator.generate_demo()

        if demo_path:
            print(f"[INFO] Demo script generated at: {demo_path}")
            print("[INFO] You can now run it with something like:")
            print(f"       cd {repo_target_path}")
            print(f"       python {demo_path.name}")
        else:
            print("[WARNING] Demo generation failed or returned empty code.")


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
        print(f"[ERROR] Command execution failed (e.g., git, venv, or dependency install): {e}", file=sys.stderr)
        # Allow finally block to run cleanup
        sys.exit(1)
    except Exception as e:
        print(f"[FATAL] An unexpected error occurred: {type(e).__name__} - {e}", file=sys.stderr)
        sys.exit(1)
        
    finally:
        # --- Cleanup ---
        # The final cleanup block ensures directories are removed if requested
        if cleanup_tmp and Path(TMP_DIR).exists():
            print(f"[INFO] Cleaning up tmp/ directory...")
            shutil.rmtree(TMP_DIR, ignore_errors=True)
        
        if cleanup_workspace and Path(WORKSPACE_DIR).exists():
            print(f"[INFO] Cleaning up workspace/ directory...")
            # We assume the cleanup_workspace flag means cleaning the entire workspace
            # or relying on the calling script to manage it if only specific repo cleanup is needed.
            # For simplicity here, we clear the entire WORKSPACE_DIR if the flag is set.
            shutil.rmtree(WORKSPACE_DIR, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A pipeline orchestrator for processing research papers (URL or PDF) to generate code demos."
    )
    parser.add_argument(
        "input",
        type=str,
        help="The input source, which can be either a full URL (e.g., http://arxiv.org/...) or a local path to a PDF file (e.g., ./paper.pdf).",
    )

    parser.add_argument(
        "--github",
        type=str,
        help="The input of a github link if there is one",
    )

    parser.add_argument(
        "--tmp",
        action="store_true",
        help="Clone the repository into an ephemeral tmp/repo directory instead of the persistent workspace."
    )

    parser.add_argument(
        "--cleanup-tmp",
        action="store_true",
        help="Remove only the tmp/ directory after pipeline completion."
    )

    parser.add_argument(
        "--cleanup-workspace",
        action="store_true",
        help="Remove only the workspace/ directory after pipeline completion."
    )

    parser.add_argument(
        "--cleanup-all",
        action="store_true",
        help="Remove BOTH tmp/ and workspace/ directories after pipeline completion."
    )
    
    args = parser.parse_args()
    
    print(f"\n--- Starting Pipeline Execution with Input: {args.input} ---\n")
    
    # Start timing
    start_time = time.time()

    run_pipeline(
        args.input,
        github_link=args.github,
        istmp=args.tmp,
        cleanup_tmp=args.cleanup_tmp or args.cleanup_all,
        cleanup_workspace=args.cleanup_workspace or args.cleanup_all
    )
    
    # End timing and report duration
    end_time = time.time()
    duration = end_time - start_time
    print(f"\n--- Pipeline Complete in {duration:.2f} seconds. ---")