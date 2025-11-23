import re
import os
from pathlib import Path
from typing import Set, Optional, List, Dict


class RequirementsExtractor:
    """
    Scans a cloned repository directory to identify external Python package dependencies
    by looking for 'import' and 'from ... import' statements.
    
    This version includes the comprehensive standard library exclusion list and the 
    extended module-to-package mapping dictionary derived from common practice and 
    tools like pipreqs.
    """

    # --- 1. Comprehensive Standard Library Modules (Exclusion List) ---
    # These modules are part of the Python core and should NOT be included in requirements.txt.
    STANDARD_LIBRARY: Set[str] = {
        '__future__', '__main__', '_dummy_thread', '_thread', 'abc', 'aifc', 
        'antigravity', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 
        'asyncore', 'atexit', 'base64', 'bdb', 'binascii', 'binhex', 'bisect', 
        'builtins', 'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 
        'code', 'codecs', 'codeop', 'collections', 'colorsys', 'compileall', 
        'concurrent', 'configparser', 'contextlib', 'copy', 'copyreg', 'cProfile', 
        'csv', 'ctypes', 'datetime', 'dbm', 'decimal', 'difflib', 'dis', 
        'distutils', 'doctest', 'dummy_threading', 'email', 'encodings', 'errno', 
        'faulthandler', 'fcntl', 'filecmp', 'fileinput', 'fnmatch', 'formatter', 
        'fractions', 'ftplib', 'functools', 'gc', 'getopt', 'getpass', 'gettext', 
        'glob', 'grp', 'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'http', 
        'imaplib', 'imghdr', 'imp', 'inspect', 'io', 'ipaddress', 'itertools', 
        'json', 'keyword', 'lib2to3', 'linecache', 'locale', 'logging', 'lzma', 
        'mailbox', 'mailcap', 'marshal', 'math', 'mimetypes', 'mmap', 
        'modulefinder', 'msvcrt', 'multiprocessing', 'netrc', 'nis', 'nntplib', 
        'numbers', 'operator', 'optparse', 'os', 'ossaudiodev', 'parser', 
        'pathlib', 'pdb', 'pickle', 'pipes', 'pkgutil', 'platform', 'plistlib', 
        'poplib', 'pprint', 'profile', 'pstats', 'pty', 'pwd', 'py_compile', 
        'pyclbr', 'pydoc', 'queue', 'quopri', 'random', 're', 'readline', 
        'reprlib', 'resource', 'rlcompleter', 'runpy', 'sched', 'secrets', 'select', 
        'selectors', 'shelve', 'shlex', 'shutil', 'signal', 'site', 'smtpd', 
        'smtplib', 'sndhdr', 'socket', 'socketserver', 'spwd', 'sqlite3', 'ssl', 
        'stat', 'statistics', 'string', 'stringprep', 'struct', 'subprocess', 
        'sunau', 'symbol', 'symtable', 'sys', 'sysconfig', 'tabnanny', 'tarfile', 
        'telnetlib', 'tempfile', 'termios', 'textwrap', 'this', 'threading', 
        'time', 'timeit', 'tkinter', 'token', 'tokenize', 'trace', 'traceback', 
        'tracemalloc', 'tty', 'turtle', 'turtledemo', 'types', 'typing', 
        'unicodedata', 'unittest', 'urllib', 'uu', 'uuid', 'venv', 'warnings', 
        'wave', 'weakref', 'webbrowser', 'winreg', 'wsgiref', 'xdrlib', 'xml', 
        'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib', 'zoneinfo',
        # Also include common non-core but frequently mistaken modules
        'pydantic', 'click',
    }

    # --- 2. Comprehensive Import Name -> PyPI Install Name Mapping (Alias List) ---
    IMPORT_TO_INSTALL_NAME: dict[str, str] = {
        'PIL': 'Pillow',
        'bs4': 'beautifulsoup4',
        'yaml': 'PyYAML',
        'cv2': 'opencv-python',
        'lxml': 'lxml',
        'scipy': 'scipy',
        'sklearn': 'scikit-learn',
        'skimage': 'scikit-image',
        'tensorflow': 'tensorflow',
        'torch': 'torch',
        'torchvision': 'torchvision',
        'torchaudio': 'torchaudio',
        'matplotlib': 'matplotlib',
        'requests': 'requests',
        'tqdm': 'tqdm',
        'numpy': 'numpy',
        'pandas': 'pandas',
        'ax': 'matplotlib', # Common matplotlib alias
        'mpl': 'matplotlib', # Common matplotlib alias
        'dateutil': 'python-dateutil',
        'h5py': 'h5py',
        'skvideo': 'scikit-video',
        'gdown': 'gdown',
        'pytz': 'pytz',
        'xlrd': 'xlrd',
        'cairosvg': 'CairoSVG',
        # Using pycryptodome as the modern recommended replacement
        'Crypto': 'pycryptodome', 
        'cryptography': 'cryptography',
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

        # Simple filter for comments, docstrings, and empty lines
        if not line or line.startswith('#') or line.startswith('"""') or line.startswith("'''"):
            return None
        
        # Regex for 'import <module> [as alias]'
        match_import = re.match(r"import\s+([a-zA-Z0-9_]+)", line)
        if match_import:
            module = match_import.group(1)
            return module

        # Regex for 'from <module>.<sub_module> | from <module> import ...'
        match_from = re.match(r"from\s+([a-zA-Z0-9_\.]+)\s+import", line)
        if match_from:
            module_full = match_from.group(1)
            module = module_full.split('.')[0]
            
            # Filter out relative imports immediately (starting with .)
            if module.startswith('.'):
                return None
            
            return module
            
        return None

    def analyze_repo(self, repo_path: Path):
        """
        Walks the repository directory, analyzes Python files, and writes dependencies.
        """
        repo_path = Path(repo_path)
        print(f"[INFO] Starting dependency analysis in: {repo_path}")

        if not repo_path.is_dir():
            print(f"[ERROR] Repository path not found: {repo_path}")
            return

        for root, dirs, files in os.walk(repo_path, topdown=True):
            # Skip hidden/system directories (e.g., .git, .vscode)
            # This also filters out our Venv: .venv_repro
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
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
            # Check for the mapping, defaulting to the original import name if no mapping found
            install_name = self.IMPORT_TO_INSTALL_NAME.get(dep, dep)
            final_dependencies.add(install_name)

        sorted_dependencies = sorted(final_dependencies)
        self._write_requirements_file(sorted_dependencies)

    def _analyze_file(self, file_path: Path):
        """
        Reads a single Python file, extracts dependencies, and handles common parsing errors.
        """
        try:
            # Attempt to read the file content
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # Fallback to a more permissive encoding like latin-1 if utf-8 fails
            try:
                content = file_path.read_text(encoding='latin-1')
            except Exception as e:
                print(f"[WARNING] Skipping file due to encoding/read error: {file_path} ({e})")
                return
        except Exception as e:
            print(f"[WARNING] Skipping file due to read error: {file_path} ({e})")
            return
        
        try:
            # We rely on resilient line-by-line regex matching, which is much less likely to fail 
            # due to complex f-string syntax or incomplete Python code compared to ast.parse().
            
            for line in content.splitlines():
                module_name = self._extract_module_name(line)
                if module_name:
                    self.all_dependencies.add(module_name)

        except Exception as e:
             # This catch block is mostly for safety against unforeseen regex/processing errors
            print(f"[WARNING] Could not analyze imports in file {file_path}: {e}. Skipping file.")

    def _write_requirements_file(self, dependencies: List[str]):
        """Writes the collected external dependencies to requirements.txt."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Write dependencies without version specifiers
            with open(self.output_file, 'w') as f:
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
    
    # Example with different import names
    (TEST_DIR / "test1.py").write_text("""
import os
import requests 
import PIL.Image as Image # <-- Mapped to Pillow
from numpy import array 
from sklearn.metrics import accuracy_score # <-- Mapped to scikit-learn
import matplotlib.pyplot as plt
import bs4 
import gdown.download
from dateutil import parser
""")
    
    extractor = RequirementsExtractor(output_dir="tmp_output")
    extractor.analyze_repo(TEST_DIR)

    # Clean up dummy files
    import shutil
    shutil.rmtree(TEST_DIR, ignore_errors=True)
    shutil.rmtree("tmp_output", ignore_errors=True)
