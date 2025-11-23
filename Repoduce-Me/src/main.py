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
from pathlib import Path
from typing import Optional
from downloader import Downloader
from paper_extracter import PaperParser
from demo_creator import DemoCreator
from venv_create import create_and_install_venv
from requirements_extract import RequirementsExtractor

# Configuration

# Temporary directory for:
# - downloaded PDF
# - temporary venv
# - requirements.txt
TMP_DIR = "tmp"
PDF_OUTPUT_FILENAME = Path(TMP_DIR) / "downloaded_paper.pdf"

# Persistent directory where cloned repositories will live by default
WORKSPACE_DIR = "workspace"

def _parse_repo_name_from_github_url(github_url: str) -> str:
    """
    Extract a reasonable repo directory name from a GitHub URL.
    Example: https://github.com/user/radonpy.git -> radonpy
    """
    tail = github_url.rstrip("/").split("/")[-1]
    if tail.endswith(".git"):
        tail = tail[:-4]
    return tail or "cloned_repo"

def run_pipeline(input_path: str, istmp: bool, cleanup_tmp: bool, cleanup_workspace: bool):
    """
    The main orchestration function for the pipeline.

    :param input_path: URL or local PDF path.
    :param istmp: If True, clone repo into tmp/repo (ephemeral).
                         If False, clone into workspace/<repo_name> (persistent).
    """
    # Downloader uses the target_dir for cleanup and cloning
    downloader = Downloader(target_dir=str(TMP_DIR)) 
    pdf_path: Optional[Path] = None

    try:
        # STEP 1: Handle Input (URL vs. Local PDF)
        if input_path.lower().startswith('http'):
            print("--- STEP 1: Input is a URL. Downloading PDF... ---")
            if pdf_downloader.download_pdf(input_path, str(PDF_OUTPUT_FILENAME)):
                pdf_path = PDF_OUTPUT_FILENAME
            else:
                raise ConnectionError(f"Failed to download PDF from: {input_path}")
        else:
            print("--- STEP 1: Input is a local PDF file. Skipping download... ---")
            pdf_path = Path(input_path)
            if not pdf_path.is_file():
                raise FileNotFoundError(f"Local file not found at: {pdf_path}")
            print(f"[INFO] Using local PDF file: {pdf_path}")

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

        # Decide clone target directory
        if istmp:
            # Ephemeral repo clone inside tmp/, separate from venv/pdf
            clone_dir = Path(TMP_DIR) / "repo"
            print(f"[INFO] Cloning repository into ephemeral directory: {clone_dir}")
        else:
            # Persistent repo clone in workspace/<repo_name>
            repo_name = _parse_repo_name_from_github_url(github_url)
            clone_dir = Path(WORKSPACE_DIR) / repo_name
            print(f"[INFO] Cloning repository into workspace directory: {clone_dir}")

        clone_dir.parent.mkdir(parents=True, exist_ok=True)

        # STEP 3: Cloning GitHub Repository
        print("\n--- STEP 3: Cloning GitHub Repository... ---")
        repo_downloader = Downloader(target_dir=str(clone_dir))
        clone_success = repo_downloader.download(github_url)

        if not clone_success:
            raise RuntimeError(f"Git clone failed for repository: {github_url}")
        
        print(f"[SUCCESS] Repository successfully cloned into: {cloned_repo_path}")
        
        # --- NEW STEP 4: Dependency Extraction using our custom tool ---
        print("\n--- STEP 4: Extracting Dependencies using RequirementsExtractor... ---")
        extractor = RequirementsExtractor(output_dir=str(TMP_DIR))
        extractor.analyze_repo(cloned_repo_path)
        print(f"[SUCCESS] Dependencies written to: {REQUIREMENTS_FILE}")
        
        # --- UPDATED STEP 5: Virtual Environment Setup & Installation ---
        # This function now only needs to create the venv and run `pip install -r requirements.txt`
        print("\n--- STEP 5: Virtual Environment Setup & Installation... ---")
        create_and_install_venv(cloned_repo_path) # Assumes this function is updated
        
        # STEP 6: Demo Creation
        print("\n--- STEP 6: Demo Creation... ---")
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
        # Includes command execution failures (git, venv, or pip, or our extractor run)
        print(f"[ERROR] Command execution failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[FATAL] An unexpected error occurred: {type(e).__name__} - {e}", file=sys.stderr)
        sys.exit(1)
        
    finally:
        if cleanup_tmp:
            try:
                print("[INFO] Cleaning up tmp/ directory...")
                shutil.rmtree(TMP_DIR, ignore_errors=True)
                print("[SUCCESS] tmp/ cleaned.")
            except Exception as e:
                print(f"[WARNING] Failed to clean tmp/: {e}")

        if cleanup_workspace:
            try:
                print("[INFO] Cleaning up workspace/ directory...")
                shutil.rmtree(WORKSPACE_DIR, ignore_errors=True)
                print("[SUCCESS] workspace/ cleaned.")
            except Exception as e:
                print(f"[WARNING] Failed to clean workspace/: {e}")


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
    
    print(f"\n--- Starting Pipeline Execution with Input: {args.input} ---")
    
    # Start timing
    start_time = time.time()
    
    run_pipeline(
        args.input,
        istmp=args.tmp,
        cleanup_tmp=args.cleanup_tmp or args.cleanup_all,
        cleanup_workspace=args.cleanup_workspace or args.cleanup_all,
    )

    end_time = time.time()
    duration = end_time - start_time
    print(f"\n--- Pipeline Complete in {duration:.2f} seconds. ---")