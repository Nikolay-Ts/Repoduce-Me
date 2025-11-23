"""
cleanup.py — Remove pipeline-generated directories.

USAGE:
------
# Remove ONLY tmp (venv, requirements, PDFs, ephemeral repo)
python cleanup.py --tmp

# Remove ONLY workspace (persistent cloned repositories + demos)
python cleanup.py --workspace

# Remove BOTH
python cleanup.py --tmp --workspace
"""

import argparse
import shutil
from pathlib import Path

TMP_DIR = Path("tmp")
WORKSPACE_DIR = Path("workspace")


def wipe(path: Path):
    if not path.exists():
        print(f"[INFO] Nothing to clean: {path}")
        return

    print(f"[CLEANUP] Removing directory: {path}")
    shutil.rmtree(path)
    print(f"[DONE] Removed: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup utility for pipeline folders.")
    parser.add_argument("--tmp", action="store_true", help="Delete the tmp/ directory.")
    parser.add_argument("--workspace", action="store_true", help="Delete the workspace/ directory.")

    args = parser.parse_args()

    if not args.tmp and not args.workspace:
        parser.error("No action specified — use --tmp and/or --workspace.")

    if args.tmp:
        wipe(TMP_DIR)

    if args.workspace:
        wipe(WORKSPACE_DIR)
