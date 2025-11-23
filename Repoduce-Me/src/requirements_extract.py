import re
import os
import shutil
from pathlib import Path
from typing import Set, Optional, List, Dict

class RequirementsExtractor:
    """
    Scans a cloned repository directory to identify external Python package dependencies.
    
    This version prioritizes finding and using existing dependency files (like 
    requirements.txt) before resorting to dynamic import analysis.
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
        'faulthandler', 'filecmp', 'fnmatch', 'formatter', 'fractions', 'ftplib', 
        'functools', 'gc', 'getopt', 'getpass', 'gettext', 'glob', 'grp', 'gzip', 
        'hashlib', 'heapq', 'hmac', 'html', 'http', 'imaplib', 'imghdr', 'imp', 
        'importlib', 'inspect', 'io', 'ipaddress', 'itertools', 'json', 'keyword', 
        'lib2to3', 'linecache', 'locale', 'logging', 'lzma', 'mailbox', 'mailcap', 
        'marshal', 'math', 'mimetypes', 'mmap', 'modulefinder', 'multiprocessing', 
        'netrc', 'nis', 'nntplib', 'numbers', 'operator', 'optparse', 'os', 
        'ossaudiodev', 'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes', 'pkgutil', 
        'platform', 'plistlib', 'poplib', 'posix', 'pprint', 'profile', 'pstats', 
        'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc', 'queue', 'quopri', 'random', 
        're', 'readline', 'reprlib', 'resource', 'rlcompleter', 'runpy', 'sched', 
        'secrets', 'select', 'selectors', 'shelve', 'shlex', 'shutil', 'signal', 
        'site', 'smtplib', 'sndhdr', 'socket', 'socketserver', 'spwd', 'sqlite3', 
        'sre_constants', 'sre_parse', 'ssl', 'stat', 'statistics', 'string', 
        'stringprep', 'struct', 'subprocess', 'sunau', 'symtable', 'sys', 'sysconfig', 
        'syslog', 'tabnanny', 'tarfile', 'telnetlib', 'tempfile', 'termios', 
        'textwrap', 'this', 'threading', 'time', 'timeit', 'tkinter', 'token', 
        'tokenize', 'trace', 'traceback', 'tracemalloc', 'tty', 'turtle', 'turtledemo', 
        'types', 'typing', 'unicodedata', 'unittest', 'urllib', 'uu', 'uuid', 'venv', 
        'warnings', 'wave', 'weakref', 'webbrowser', 'winreg', 'wsgiref', 'xdrlib', 
        'xml', 'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib', 'zoneinfo'
    }

    # --- 2. Package Name Mapping (Module Name -> PyPI Package Name) ---
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
        'ddp': 'torch-ddp-tools',
        'matplotlib_inline': 'matplotlib-inline',
        'healpy': 'healpy',
        'torchvision': 'torchvision',
        'torchaudio': 'torchaudio',
        'omegaconf': 'omegaconf',
        'einops': 'einops',
        'wandb': 'wandb',
        'astropy': 'astropy',
        # Add more mappings for common discrepancies
    }

    # Files to check for existing dependencies
    REQUIREMENTS_FILES: List[str] = [
        'requirements.txt',
        'requirements-dev.txt',
        'requirements-test.txt',
        'requirements-base.txt',
    ]

    def __init__(self, repo_dir: str, output_dir: str):
        self.repo_dir = Path(repo_dir)
        self.output_dir = Path(output_dir)
        self.output_file = self.output_dir / "requirements.txt"
        self.all_dependencies: Set[str] = set()

    def _extract_module_name(self, line: str) -> Optional[str]:
        """Extracts the base module name from an import statement."""
        
        # Regex for 'import <module> [as <alias>]'
        match_import = re.match(r'^\s*import\s+([a-zA-Z0-9._]+)', line)
        if match_import:
            module_path = match_import.group(1)
            return module_path.split('.')[0] # Get base module name

        # Regex for 'from <module> import <name> [as <alias>]'
        match_from = re.match(r'^\s*from\s+([a-zA-Z0-9._]+)\s+import', line)
        if match_from:
            module_path = match_from.group(1)
            return module_path.split('.')[0] # Get base module name
            
        return None

    def _is_local_import(self, module_name: str) -> bool:
        """Checks if a module is likely a local file/directory within the repo."""
        # Simple check: Is there a file or directory with this name (or as a package)
        return (self.repo_dir / f"{module_name}.py").exists() or \
               (self.repo_dir / module_name).is_dir()

    def _process_file(self, file_path: Path):
        """Reads a Python file, extracts imports, and adds external modules to the set."""
        if file_path.name.startswith('.') or file_path.suffix != '.py':
            return # Skip hidden files and non-Python files

        try:
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                content = file_path.read_text(encoding='latin-1')
            except Exception as e:
                print(f"[WARNING] Skipping file due to encoding/read error: {file_path} ({e})")
                return
        except Exception as e:
            print(f"[WARNING] Skipping file due to read error: {file_path} ({e})")
            return
        
        try:
            for line in content.splitlines():
                module_name = self._extract_module_name(line)
                if module_name:
                    # 1. Check if it's Standard Library
                    if module_name in self.STANDARD_LIBRARY:
                        continue
                    
                    # 2. Check if it's a local import (heuristic, not perfect)
                    if self._is_local_import(module_name):
                        continue
                        
                    # 3. Apply package mapping (e.g., sklearn -> scikit-learn)
                    package_name = self.MODULE_TO_PACKAGE.get(module_name, module_name)

                    # 4. Add the final package name
                    self.all_dependencies.add(package_name)

        except Exception as e:
            print(f"[WARNING] Could not analyze imports in file {file_path}: {e}. Skipping file.")

    def _get_dependencies_from_file(self, file_path: Path) -> List[str]:
        """Reads dependencies from a requirements-style file, cleaning comments/empty lines."""
        dependencies = []
        try:
            with file_path.open('r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Simplistic cleaning: remove extras and environment markers
                        dependency = re.sub(r'[ \t]*[;#].*$', '', line) # Remove comments
                        dependency = re.sub(r';.*$', '', dependency) # Remove env markers
                        dependencies.append(dependency.strip())
        except Exception as e:
            print(f"[ERROR] Could not read or parse dependency file {file_path}: {e}")
        return dependencies

    def find_existing_requirements(self) -> Optional[List[str]]:
        """
        Searches for common requirements.txt style dependency files in the repository.
        Returns a list of dependencies if found, otherwise None.
        """
        for filename in self.REQUIREMENTS_FILES:
            file_path = self.repo_dir / filename
            if file_path.exists():
                print(f"[INFO] Found existing dependency file: {filename}. Using contents for installation.")
                dependencies = self._get_dependencies_from_file(file_path)
                
                # Filter out known problematic dependencies that are standard library (e.g., unicodedata)
                filtered_deps = [
                    dep for dep in dependencies 
                    if dep.split('>')[0].split('=')[0].split('<')[0].split('~')[0].strip() not in self.STANDARD_LIBRARY
                ]
                
                if not filtered_deps:
                    print(f"[WARNING] Dependency file {filename} was found but contained no external packages after filtering.")
                    continue
                
                return filtered_deps

        return None

    def analyze_imports(self):
        """Walks the repository and analyzes all Python files for imports."""
        for root, _, files in os.walk(self.repo_dir):
            for file_name in files:
                file_path = Path(root) / file_name
                self._process_file(file_path)

    def extract(self) -> List[str]:
        """
        Main extraction logic. Prioritizes existing dependency files over dynamic analysis.
        
        Returns the list of final dependencies. This list is only generated if a
        requirements.txt-style file was found, OR if dynamic analysis was performed.
        It is NOT generated if pyproject.toml is detected (main.py handles that).
        """
        # 1. Check for requirements.txt style files
        final_dependencies = self.find_existing_requirements()
        
        if final_dependencies is None:
            # 2. If not found, perform dynamic analysis as the fallback
            print("[INFO] No existing requirements file found. Performing dynamic import analysis...")
            self.analyze_imports()
            final_dependencies = sorted(list(self.all_dependencies))

        # 3. Write the extracted/found dependencies to the standard output file (tmp/requirements.txt)
        if final_dependencies:
            self._write_requirements_file(final_dependencies)
        
        return final_dependencies

    def _write_requirements_file(self, dependencies: List[str]):
        """Writes the collected external dependencies to requirements.txt."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.output_file, 'w') as f:
                for dep in dependencies:
                    f.write(f"{dep}\n")

            print(f"\n[SUCCESS] Extracted {len(dependencies)} external dependencies.")
            print(f"[SUCCESS] Requirements file written to: {self.output_file.resolve()}")
        except Exception as e:
            print(f"[FATAL] Could not write requirements file: {e}")