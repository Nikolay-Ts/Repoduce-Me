import re
import os
from pathlib import Path
from typing import Set, Optional, List, Dict


class RequirementsExtractor:
    """
    Scans a cloned repository directory to identify external Python package dependencies
    by looking for 'import' and 'from ... import' statements.
    It compiles a list of unique, external dependencies into a requirements.txt file.
    """

    STANDARD_LIBRARY: Set[str] = {
        'os', 'sys', 'pathlib', 're', 'json', 'csv', 'math', 'time', 'datetime',
        'typing', 'collections', 'itertools', 'functools', 'logging', 'argparse',
        'subprocess', 'shutil', 'tempfile', 'threading', 'queue', 'socket',
        'http', 'urllib', 'xml', 'html', 'unittest', 'doctest', 'warnings',
        'dataclasses', 'abc', 'enum', 'decimal', 'io', 'pickle', 'gzip', 'zipfile',
        'hashlib', 'base64', 'asyncio'
    }

    # Map import names to PyPI package names
    IMPORT_TO_INSTALL_NAME: Dict[str, str] = {
        'PIL': 'Pillow',
        # 'cv2': 'opencv-python',
        # 'yaml': 'PyYAML',
    }

    # Directories to skip entirely when walking the repo
    IGNORE_DIRS: Set[str] = {
        '.git', '.hg', '.svn',
        '__pycache__',
        '.venv', 'venv', 'env',
        'build', 'dist',
        'node_modules',
    }

    # Regex patterns
    _IMPORT_RE = re.compile(r'^\s*import\s+(.+)')
    _FROM_RE = re.compile(r'^\s*from\s+([a-zA-Z0-9_.]+)\s+import\s+')

    def __init__(self, output_dir: str = "tmp"):
        """
        Initializes the extractor with the directory where the requirements.txt
        will be written.
        """
        self.output_dir = Path(output_dir)
        self.output_file = self.output_dir / "requirements.txt"
        self.all_dependencies: Set[str] = set()

    # ---- Core logic ---------------------------------------------------------

    def _extract_modules_from_line(self, line: str) -> Set[str]:
        """
        Extracts one or more top-level module names from a single import line.
        Handles:
          - import a, b as c
          - from a.b import x, y
        """
        modules: Set[str] = set()
        line = line.strip()

        # Handle "from X.Y import Z"
        m_from = self._FROM_RE.match(line)
        if m_from:
            full_mod = m_from.group(1)
            # Skip relative imports like "from .foo import bar"
            if not full_mod.startswith('.'):
                top_level = full_mod.split('.')[0]
                modules.add(top_level)
            return modules

        # Handle "import a, b as c"
        m_import = self._IMPORT_RE.match(line)
        if m_import:
            imports_part = m_import.group(1)
            # Split by comma, then strip "as ..." if present
            for chunk in imports_part.split(','):
                chunk = chunk.strip()
                if not chunk:
                    continue
                # Remove trailing comments
                if '#' in chunk:
                    chunk = chunk.split('#', 1)[0].strip()
                # Remove "as alias"
                if ' as ' in chunk:
                    chunk = chunk.split(' as ', 1)[0].strip()
                # Only keep valid identifiers (top-level module name)
                top_level = chunk.split('.')[0]
                if top_level and not top_level.startswith('.'):
                    modules.add(top_level)
        return modules

    def analyze_repo(self, repo_path: Path):
        """
        Walks the repository directory, analyzes Python files, and writes dependencies.
        """
        repo_path = Path(repo_path)
        print(f"[INFO] Starting dependency analysis in: {repo_path}")

        if not repo_path.is_dir():
            print(f"[ERROR] Repository path not found: {repo_path}")
            return

        for root, dirs, files in os.walk(repo_path):
            # Filter directories in-place to avoid descending into ignored ones
            dirs[:] = [
                d for d in dirs
                if not (d in self.IGNORE_DIRS or d.startswith('.'))
            ]

            # Skip hidden directories in entire path as extra safety
            if any(part.startswith('.') for part in Path(root).parts):
                continue

            for file_name in files:
                if not file_name.endswith(".py"):
                    continue
                file_path = Path(root) / file_name
                self._analyze_file(file_path)

        # Filter out standard library modules
        external_dependencies = self.all_dependencies - self.STANDARD_LIBRARY

        # Apply the name mapping (e.g., PIL -> Pillow)
        final_dependencies: Set[str] = set()
        for dep in external_dependencies:
            install_name = self.IMPORT_TO_INSTALL_NAME.get(dep, dep)
            final_dependencies.add(install_name)

        sorted_dependencies = sorted(final_dependencies)
        self._write_requirements_file(sorted_dependencies)

    def _analyze_file(self, file_path: Path):
        """Reads a single Python file and extracts dependencies."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    for module_name in self._extract_modules_from_line(line):
                        self.all_dependencies.add(module_name)
        except Exception as e:
            print(f"[WARNING] Could not read or analyze file {file_path}: {e}")

    def _write_requirements_file(self, dependencies: List[str]):
        """Writes the collected external dependencies to requirements.txt."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                for dep in dependencies:
                    f.write(f"{dep}\n")

            print(f"\n[SUCCESS] Extracted {len(dependencies)} external dependencies.")
            print(f"[SUCCESS] Requirements file written to: {self.output_file.resolve()}")
        except Exception as e:
            print(f"[ERROR] Failed to write requirements.txt: {e}")


if __name__ == "__main__":
    # Simple self-test
    TEST_DIR = Path("test_repo_for_reqs")
    TEST_DIR.mkdir(exist_ok=True)

    (TEST_DIR / "test1.py").write_text("""
import os
import requests
import PIL.Image as Image  # mapped to Pillow
from numpy import array
import pandas as pd
from . import local_file
from mypkg.submod import something
""")

    (TEST_DIR / "sub_dir").mkdir(exist_ok=True)
    (TEST_DIR / "sub_dir" / "test2.py").write_text("""
from sklearn.metrics import accuracy_score
import matplotlib.pyplot as plt
import re, sys, json
import numpy as np, scipy as sp
""")

    extractor = RequirementsExtractor(output_dir="tmp_output")
    extractor.analyze_repo(TEST_DIR)

    # Cleanup example dirs if you want
    # import shutil
    # shutil.rmtree(TEST_DIR, ignore_errors=True)
    # shutil.rmtree("tmp_output", ignore_errors=True)