import shutil
import subprocess
from pathlib import Path
from pprint import pprint
import sys
import os

# Import your extractor
from src.requirements_extract import RequirementsExtractor

# Where to store cloned repos + outputs
BASE = Path("tmp_req_git_test")
CLONE_DIR = BASE / "repos"
OUT_DIR = BASE / "outputs"


def reset(path: Path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def git_clone(repo_url: str, dest: Path) -> bool:
    try:
        print(f"\n[CLONE] Cloning {repo_url} -> {dest}")
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(dest)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print("[CLONE] Success.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[CLONE] FAIL: {repo_url}")
        print(e.stderr)
        return False


def test_repo(url: str, idx: int):
    print("\n" + "=" * 80)
    print(f"[TEST] #{idx}  {url}")
    print("=" * 80)

    repo_local = CLONE_DIR / f"repo_{idx}"
    output_dir = OUT_DIR / f"repo_{idx}"

    # 1. Clone repo ------------------------------------------
    if not git_clone(url, repo_local):
        print("[SKIP] Clone failed. Moving on.")
        return

    # 2. Extract dependencies ---------------------------------
    print("[EXTRACT] Running RequirementsExtractor...")
    extractor = RequirementsExtractor(repo_dir=repo_local, output_dir=output_dir)
    try:
        result = extractor.extract()
    except Exception as e:
        print(f"[EXTRACT] ERROR: {type(e).__name__}: {e}")
        return

    print("\n[RESULT] Extracted Dependencies:")
    pprint(result)

    # If a requirements file was generated, show its path
    req_file = output_dir / "requirements.txt"
    if req_file.exists():
        print(f"\n[FILE] requirements.txt saved at: {req_file.resolve()}")
        print("-------- FILE CONTENT --------")
        print(req_file.read_text())
        print("------------------------------")
    else:
        print("[INFO] No requirements.txt generated.")


if __name__ == "__main__":
    # Read GitHub URLs from a file OR inline list
    urls_file = Path("/Users/bilalwaraich/Desktop/CU Hackathon/Repoduce-Me/Repoduce-Me/src/github_test_list.txt")

    if urls_file.exists():
        print(f"[INFO] Loading GitHub URLs from: {urls_file}")
        urls = [u.strip() for u in urls_file.read_text().splitlines() if u.strip()]
    else:
        print("[WARN] github_test_list.txt not found. Using fallback test repos.")
        urls = [
            "https://github.com/psf/requests",
            "https://github.com/pallets/flask",
            "https://github.com/huggingface/transformers",
        ]

    reset(BASE)
    reset(CLONE_DIR)
    reset(OUT_DIR)

    print(f"\n[INIT] Loaded {len(urls)} GitHub repositories to test.")

    for i, url in enumerate(urls, start=1):
        test_repo(url, i)

    print("\n=== DONE: GitHub-based RequirementsExtractor tests complete ===")
