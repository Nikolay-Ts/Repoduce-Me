import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set


class RequirementsExtractor:
    """
    Scans a cloned repository directory to identify external Python package dependencies.

    Priority:
        1) If pyproject.toml exists      -> caller should run `pip install .`
        2) If setup.py/setup.cfg exists  -> caller should run `pip install .`
        3) If requirements*.txt exists   -> use that directly
        4) Else                          -> dynamic import analysis to build requirements.txt

    Usage pattern (expected from main.py):

        extractor = RequirementsExtractor(repo_dir=str(repo_target_path),
                                            output_dir=str(TMP_DIR))
        deps_or_mode = extractor.extract()

    Where deps_or_mode is:
        - ["__USE_PYPROJECT__"]   => install via `pip install .`
        - ["__USE_SETUPTOOLS__"]  => install via `pip install .`
        - [<deps...>]             => install via `pip install -r tmp/requirements.txt`
    """

    # --- 1. Comprehensive Standard Library Modules (Exclusion List) ---
    STANDARD_LIBRARY: Set[str] = {
        '__future__', '__main__', '_dummy_thread', '_thread', 'abc', 'aifc',
        'antigravity', 'argparse', 'array', 'ast', 'asynchat', 'asyncio',
        'asyncore', 'atexit', 'base64', 'bdb', 'binascii', 'binhex', 'bisect',
        'builtins', 'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd',
        'code', 'codecs', 'codeop', 'collections', 'colorsys', 'compileall',
        'concurrent', 'configparser', 'contextlib', 'copy', 'copyreg', 'cProfile',
        'csv', 'ctypes', 'datetime', 'dbm', 'decimal', 'difflib', 'dis',
        'distutils', 'doctest', 'dummy_threading', 'email', 'encodings', 'errno',
        'faulthandler', 'filecmp', 'fileinput', 'fnmatch', 'formatter', 'fractions',
        'ftplib', 'functools', 'gc', 'getopt', 'getpass', 'gettext', 'glob', 'grp',
        'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'http', 'imaplib', 'imghdr',
        'imp', 'importlib', 'inspect', 'io', 'ipaddress', 'itertools', 'json',
        'keyword', 'lib2to3', 'linecache', 'locale', 'logging', 'lzma', 'mailbox',
        'mailcap', 'marshal', 'math', 'mimetypes', 'mmap', 'modulefinder',
        'multiprocessing', 'netrc', 'nis', 'nntplib', 'numbers', 'operator',
        'optparse', 'os', 'ossaudiodev', 'pathlib', 'pdb', 'pickle', 'pickletools',
        'pipes', 'pkgutil', 'platform', 'plistlib', 'poplib', 'posix', 'pprint',
        'profile', 'pstats', 'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc',
        'queue', 'quopri', 'random', 're', 'readline', 'reprlib', 'resource',
        'rlcompleter', 'runpy', 'sched', 'secrets', 'select', 'selectors',
        'shelve', 'shlex', 'shutil', 'signal', 'site', 'smtplib', 'sndhdr',
        'socket', 'socketserver', 'spwd', 'sqlite3', 'sre_constants', 'sre_parse',
        'ssl', 'stat', 'statistics', 'string', 'stringprep', 'struct', 'subprocess',
        'sunau', 'symtable', 'sys', 'sysconfig', 'syslog', 'tabnanny', 'tarfile',
        'telnetlib', 'tempfile', 'termios', 'textwrap', 'this', 'threading',
        'time', 'timeit', 'tkinter', 'token', 'tokenize', 'trace', 'traceback',
        'tracemalloc', 'tty', 'turtle', 'turtledemo', 'types', 'typing',
        'unicodedata', 'unittest', 'urllib', 'uu', 'uuid', 'venv', 'warnings',
        'wave', 'weakref', 'webbrowser', 'winreg', 'wsgiref', 'xdrlib', 'xml',
        'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib', 'zoneinfo'
    }

    MODULE_TO_PACKAGE: Dict[str, str] = {
        'skimage': 'scikit-image',
        'sklearn': 'scikit-learn',
        'mpl_toolkits': 'matplotlib',
        'cv2': 'opencv-python',
        'PIL': 'Pillow',
        'yaml': 'PyYAML',
        'tqdm': 'tqdm',
        'h5py': 'h5py',
        'jax': 'jax',
        'tf': 'tensorflow',
        'torch': 'torch',
        'timm': 'timm',
        'matplotlib_inline': 'matplotlib-inline',
        'healpy': 'healpy',
        'torchvision': 'torchvision',
        'torchaudio': 'torchaudio',
        'omegaconf': 'omegaconf',
        'einops': 'einops',
        'wandb': 'wandb',
        'astropy': 'astropy',
    }

    REQUIREMENTS_FILES: List[str] = [
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-test.txt",
        "requirements-base.txt",
    ]

    # Directories to skip during import analysis
    IGNORE_DIRS: Set[str] = {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        "build",
        "dist",
        "node_modules",
    }

    def __init__(self, repo_dir: str | Path, output_dir: str | Path):
        self.repo_dir = Path(repo_dir)
        self.output_dir = Path(output_dir)
        self.output_file = self.output_dir / "requirements.txt"
        self.all_dependencies: Set[str] = set()

    def _extract_module_name(self, line: str) -> Optional[str]:
        """
        Extract base module name from a Python import line.

        Handles:
            - import foo
            - import foo.bar as baz
            - from foo.bar import x, y
        """
        line = line.strip()
        if not line or line.startswith("#"):
            return None

        # 'import foo[.bar...]'
        match_import = re.match(r"^\s*import\s+([a-zA-Z0-9_\.]+)", line)
        if match_import:
            module_path = match_import.group(1)
            return module_path.split(".")[0]

        # 'from foo[.bar...] import ...'
        match_from = re.match(r"^\s*from\s+([a-zA-Z0-9_\.]+)\s+import", line)
        if match_from:
            module_path = match_from.group(1)
            # Skip relative imports: from .foo import ...
            if module_path.startswith("."):
                return None
            return module_path.split(".")[0]

        return None

    def _is_local_import(self, module_name: str) -> bool:
        """
        Heuristic: check if module_name corresponds to a local module/package
        inside the repository.
        """
        if not module_name:
            return False

        # e.g. <repo>/foo.py or <repo>/foo/__init__.py
        if (self.repo_dir / f"{module_name}.py").exists():
            return True

        pkg_dir = self.repo_dir / module_name
        if pkg_dir.is_dir():
            # if there's an __init__.py, treat as local package
            if (pkg_dir / "__init__.py").exists():
                return True

        return False

    def _process_file(self, file_path: Path) -> None:
        """
        Reads a Python file, extracts imports, and adds external modules to the set.
        """
        if not file_path.suffix == ".py":
            return

        # Skip hidden files
        if file_path.name.startswith("."):
            return

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = file_path.read_text(encoding="latin-1")
            except Exception as e:
                print(f"[WARNING] Skipping file due to encoding/read error: {file_path} ({e})")
                return
        except Exception as e:
            print(f"[WARNING] Skipping file due to read error: {file_path} ({e})")
            return

        try:
            for line in content.splitlines():
                module_name = self._extract_module_name(line)
                if not module_name:
                    continue

                # 1) Skip stdlib
                if module_name in self.STANDARD_LIBRARY:
                    continue

                # 2) Skip local imports
                if self._is_local_import(module_name):
                    continue

                # 3) Map module -> package if needed
                package_name = self.MODULE_TO_PACKAGE.get(module_name, module_name)

                self.all_dependencies.add(package_name)

        except Exception as e:
            print(f"[WARNING] Could not analyze imports in file {file_path}: {e}. Skipping file.")

    def _get_dependencies_from_file(self, file_path: Path) -> List[str]:
        """
        Reads dependencies from a requirements-style file, cleaning comments
        and trivial environment markers.
        """
        deps: List[str] = []
        try:
            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    # Strip inline comments and env markers
                    line = re.sub(r"[ \t]*#.*$", "", line)   # trailing comments
                    line = re.sub(r";.*$", "", line)         # env markers

                    cleaned = line.strip()
                    if cleaned:
                        deps.append(cleaned)
        except Exception as e:
            print(f"[ERROR] Could not read dependency file {file_path}: {e}")
        return deps

    def find_existing_requirements(self) -> Optional[List[str]]:
        """
        Priority:
            1) pyproject.toml       -> ['__USE_PYPROJECT__']
            2) setup.cfg/setup.py   -> ['__USE_SETUPTOOLS__']
            3) requirements*.txt    -> [deps...]
        """
        repo_root = self.repo_dir

        # 1) Modern pyproject-based project
        pyproject = repo_root / "pyproject.toml"
        if pyproject.exists():
            print("[INFO] Found pyproject.toml. Will install via `pip install .`.")
            return ["__USE_PYPROJECT__"]

        # 2) Legacy setuptools project
        setup_cfg = repo_root / "setup.cfg"
        setup_py = repo_root / "setup.py"
        if setup_cfg.exists() or setup_py.exists():
            print("[INFO] Found setup.cfg/setup.py. Will install via `pip install .`.")
            return ["__USE_SETUPTOOLS__"]

        # 3) requirements*.txt files
        for filename in self.REQUIREMENTS_FILES:
            file_path = repo_root / filename
            if not file_path.exists():
                continue

            print(f"[INFO] Found existing dependency file: {filename}. Using contents.")
            deps = self._get_dependencies_from_file(file_path)

            # Filter out obvious stdlib mistakes (very defensive)
            filtered = [
                dep for dep in deps
                if dep.split(">")[0].split("=")[0].split("<")[0].split("~")[0].strip()
                not in self.STANDARD_LIBRARY
            ]

            if not filtered:
                print(f"[WARNING] Dependency file {filename} contained no external packages after filtering.")
                continue

            return filtered

        return None

    def analyze_imports(self) -> None:
        """Walk over the repo and collect imported external modules."""
        for root, dirs, files in os.walk(self.repo_dir):
            # prune ignored dirs in-place
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS and not d.startswith(".")]

            for file_name in files:
                file_path = Path(root) / file_name
                self._process_file(file_path)

    def extract(self) -> List[str]:
        """
        Main extraction logic.

        Returns:
            - ['__USE_PYPROJECT__']   -> caller should run `pip install .`
            - ['__USE_SETUPTOOLS__']  -> caller should run `pip install .`
            - [list of deps]          -> caller should install from requirements.txt
        """
        # 1) Try existing metadata/files
        deps = self.find_existing_requirements()

        if deps is not None and deps[0] in ("__USE_PYPROJECT__", "__USE_SETUPTOOLS__"):
            return deps

        if deps is not None:
            self._write_requirements_file(deps)
            return deps

        # Case 3: nothing found -> dynamic analysis
        print("[INFO] No existing requirements files found. Performing dynamic import analysis...")
        self.analyze_imports()
        deps = sorted(self.all_dependencies)

        if deps:
            self._write_requirements_file(deps)

        return deps

    def _write_requirements_file(self, dependencies: List[str]) -> None:
        """Write dependencies to output_dir/requirements.txt."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            with self.output_file.open("w", encoding="utf-8") as f:
                for dep in dependencies:
                    f.write(f"{dep}\n")

            print(f"\n[SUCCESS] Extracted {len(dependencies)} external dependencies.")
            print(f"[SUCCESS] Requirements file written to: {self.output_file.resolve()}")
        except Exception as e:
            print(f"[FATAL] Could not write requirements file: {e}")