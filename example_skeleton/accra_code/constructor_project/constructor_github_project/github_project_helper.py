import io
import os
import re
import subprocess
import sys
import importlib.util  # noqa: F401
import tokenize
import ast

from collections import Counter


__all__ = ["_should_skip_file", "_extract_base_package", "_is_package_importable",
           "_detect_extras_by_code_scan", "_is_py310_syntax_required", "_prepend_sys_path_to_script",
           "_extract_library_counts","_extract_multiprocessing_elements", "_extract_imports_from_file"]

def _should_skip_file(file_path):
    """
    Determine if a file should be skipped from analysis due to known import issues:
    - Test files
    - Files with relative imports
    - Files using Python 3.10+ union type syntax when running under older Python versions
    - setup.py
    """
    if "test" in file_path.lower():
        return True  # Skip test files or folders

    if os.path.basename(file_path).lower() in {"setup.py"}:
        return True

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

            # Check for relative imports like `from ..` or `from .something`
            if re.search(r"from\s+\.+", content):
                return True

            # Check for PEP 604 union type syntax (`str | None`)
            if sys.version_info < (3, 10):
                # Simple check: if there's a type followed by `| None`
                if re.search(r"\b\w+\s*\|\s*None\b", content):
                    # print(f"[Skip] Detected union type syntax in {file_path}, incompatible with Python < 3.10.")
                    return True

    except Exception as e:
        print(f"[Warning] Could not read {file_path}: {e}")
        return True

    return False

def _extract_base_package(pkg):
    """Extract base package name for import checking (e.g., 'requests[security]>=2.0' → 'requests')"""
    return re.split(r"[<>=\[\]]", pkg.strip())[0]

def _is_package_importable(package_name, py_exec):
    """Checks if a package is importable in the environment associated to the python executable passed"""
    import_name = {
        "pyyaml": "yaml",
        "types-orjson": "orjson",
        "pillow": "PIL",
        "pre-commit": "pre_commit",
        "mkdocs-material": None,
        "mkdocs-macros-plugin": None,
        "mkdocs-redirects": None,
    }.get(package_name, package_name.split("[")[0].replace("-", "_"))
    if import_name is None:
        return True
    if py_exec is None:
        raise RuntimeError(f"The python executable passed is 'None', can't check if the package {import_name} is imported")
    try:
        subprocess.run(
            [py_exec, "-c", f"import importlib; importlib.import_module('{import_name}')"],
            capture_output=True,
            text=True,
            check=True
        )
        # importlib.invalidate_caches()
        # importlib.import_module(import_name)
        return True
    except subprocess.CalledProcessError:
        return False
    except ImportError:
        return False

def _detect_extras_by_code_scan(project_path):
    """
    Scan accra_code files to detect usage patterns that suggest extras (e.g., pydantic[email]).
    Returns a set of extra-required packages.
    """
    extras = set()

    # Mapping: import pattern -> required extra package
    import_to_extra = {
        r'\bEmailStr\b': 'pydantic[email]',
        r'\bSecretStr\b': 'pydantic[email]',
        r'\bfrom\s+github\b': 'PyGithub',
        r'\bimport\s+github\b': 'PyGithub',
        r'\bimport\s+material\b': 'mkdocs-material',
        r'\bfrom\s+material\b': 'mkdocs-material',
        r'\bimport\s+PIL\b': 'pillow',
        r'\bfrom\s+PIL\b': 'pillow',
        r'\bimport\s+yaml\b': 'pyyaml',
        r'\bfrom\s+yaml\b': 'pyyaml',
        r'\bimport\s+uvicorn\b': 'uvicorn',
        r'\bfrom\s+uvicorn\b': 'uvicorn',
        r'\bimport\s+starlette\b': 'starlette',
        r'\bfrom\s+starlette\b': 'starlette',
        r'\bimport\s+python_multipart\b': 'python-multipart',
        r'\bfrom\s+python_multipart\b': 'python-multipart',
        r'\bimport\s+email_validator\b': 'pydantic[email]',
        r'\bfrom\s+email_validator\b': 'pydantic[email]',
        r'\bimport\s+orjson\b': 'orjson',
        r'\bfrom\s+orjson\b': 'orjson',
    }

    for root, _, files in os.walk(project_path):
        for file in files:
            if not file.endswith(".py"):
                continue
            full_path = os.path.join(root, file)

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    for pattern, extra_pkg in import_to_extra.items():
                        if re.search(pattern, content):
                            extras.add(extra_pkg)
            except Exception as e:
                print(f"[Warning] Failed to scan file: {full_path} – {e}", file=sys.stderr)
                continue

    return sorted(extras)

def _is_py310_syntax_required(file_path):
    """
    Detects if a Python file likely uses syntax that requires Python 3.10+,
    specifically the use of the `|` operator for type annotations (PEP 604).

    This function:
    - Parses tokens to avoid false positives from bitwise OR operations.
    - Detects `|` used in type hints (e.g., `def foo(a: int | None) -> str | None`)
    - Logs the offending lines for debugging support.
    - Avoids catching `|` in comments, docstrings, or values.

    Returns:
        bool: True if 3.10+ syntax is likely required, False otherwise.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"[Warning] Could not read {file_path}: {e}", file=sys.stderr)
        return False

    try:
        uses_py310_union = False
        offending_lines = []

        tokens = tokenize.generate_tokens(io.StringIO(content).readline)
        prev_token = None
        inside_function = False

        for toknum, tokval, start, end, line in tokens:
            # Track function headers or variable annotations
            if tokval in ("def", "class"):
                inside_function = True  # noqa: F841

            # Track if `|` appears in annotation context
            if tokval == "|":
                line_no = start[0]

                # Check if previous token was colon or arrow (likely annotation)
                if prev_token and prev_token.string in (":", "->"):
                    uses_py310_union = True
                    offending_lines.append((line_no, line.strip()))

            # Track tokens for annotation context
            prev_token = tokenize.TokenInfo(toknum, tokval, start, end, line)

        if uses_py310_union:
            print(f"[Detected Python 3.10+ syntax in {file_path}]")
            for line_no, offending_line in offending_lines:
                print(f"Line {line_no}: {offending_line}")

        return uses_py310_union

    except Exception as e:
        print(f"[Tokenization error in {file_path}]: {e}")
        return False

def _prepend_sys_path_to_script(script_path, project_root_path):
    """
    Inject sys.path.insert(...) at the top of the given script to ensure imports work.
    """
    sys_path_code = f"""import sys
import os
sys.path.insert(0, os.path.abspath("{project_root_path}"))\n"""

    try:
        with open(script_path, "r", encoding="utf-8") as f:
            original_code = f.read()

        # Avoid injecting twice
        if sys_path_code.strip() not in original_code:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(sys_path_code + original_code)

    except Exception as e:
        print(f"[Warning] Could not prepend sys.path to {script_path}: {e}", file=sys.stderr)


def _extract_library_counts(data):
    """
    Takes a dictionary mapping file paths to lists of library names.
    Returns a list of tuples (library_name, count) sorted by name.
    """
    # Flatten the list of libraries from all values
    all_libraries = [lib for libs in data.values() for lib in libs]

    # Count occurrences
    counts = Counter(all_libraries)

    # Convert to list of tuples
    return sorted(counts.items())

def _extract_multiprocessing_elements(multiprocessing_usage):
    """
    Process a dictionary mapping file paths to lists of {"name", "module"} dicts,
    and count occurrences of each unique (name, module) pair across all files.

    Returns:
        {
            "used": bool,  # True if any multiprocessing elements were found
            "elements": [
                {"name": str, "module": str, "instances": int},
                ...
            ]
        }
    """
    counter = Counter()

    for file_entries in multiprocessing_usage.values():
        for entry in file_entries:
            key = (entry["name"], entry["module"])
            counter[key] += 1

    if not counter:
        return {"used": False, "elements": []}

    elements = [
        {"name": name, "module": module, "instances": count}
        for (name, module), count in counter.items()
    ]

    return {"used": True, "elements": elements}


def _extract_imports_from_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=file_path)

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split('.')[0])
    return list(imports)