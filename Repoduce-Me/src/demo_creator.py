"""
demo_creator.py - Generate runnable demo scripts using LLM.

This module uses the Constructor LLM to synthesize a runnable demo Python script
from a cloned repository, primarily based on its README and examples.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Set, List, Any

from constructor_model import ConstructorModel


class DemoCreator:
    """
    Uses Constructor LLM to synthesize a runnable demo Python script
    from a cloned repository, primarily based on its README and examples.
    """

    def __init__(
        self,
        repo_path: Any,
        output_filename: str = "generated_demo.py",
        max_readme_chars: Any = 8000,
        installed_packages: Any = None,
    ) -> None:
        """
        Initialize DemoCreator.
        
        Args:
            repo_path: Path to the repository (str or Path).
            output_filename: Name of the output demo file.
            max_readme_chars: Maximum characters to read from README.
            installed_packages: Set/list of installed package names.
        """
        # Ensure repo_path is a Path
        self.repo_path = Path(repo_path).resolve()
        self.output_path = self.repo_path / str(output_filename)
        
        # CRITICAL: Ensure max_readme_chars is an integer
        try:
            self.max_readme_chars: int = int(max_readme_chars)
        except (TypeError, ValueError):
            self.max_readme_chars = 8000
        
        # CRITICAL: Ensure installed_packages is a proper set of strings
        self.installed_packages: Set[str] = self._normalize_packages(installed_packages)

        # Lazy initialization - don't create LLM until needed
        self._llm: Optional[ConstructorModel] = None

    def _normalize_packages(self, packages: Any) -> Set[str]:
        """Convert any input to a set of strings safely."""
        if packages is None:
            return set()
        
        if isinstance(packages, set):
            return {str(p) for p in packages}
        
        if isinstance(packages, (list, tuple, frozenset)):
            return {str(p) for p in packages}
        
        if isinstance(packages, str):
            # Single package name
            return {packages}
        
        # Try to iterate over it
        try:
            return {str(p) for p in packages}
        except TypeError:
            return set()

    @property
    def llm(self) -> ConstructorModel:
        """Lazy initialization of the LLM."""
        if self._llm is None:
            self._llm = ConstructorModel(model="gpt-5.1")
        return self._llm

    # ---------- Public API ----------

    def generate_demo(self) -> Optional[Path]:
        """
        Main entrypoint:
        - Discover README and sample scripts
        - Call Constructor LLM (via ConstructorModel) to generate a Python demo
        - Write demo to file

        Returns:
            Path to generated demo script if successful, else None.
        """
        print("\n=== DEMO GENERATION: START ===")
        print(f"[INFO] Repository path: {self.repo_path}")

        # 1) Load README
        readme_text = self._load_readme()
        if not readme_text:
            print("[WARN] No README found in repository root. Skipping demo generation.")
            print("=== DEMO GENERATION: ABORTED (NO README) ===")
            return None

        # 2) Load example code snippets (if any)
        example_snippets = self._load_example_snippets()
        if example_snippets and len(example_snippets.strip()) > 0:
            print("[INFO] Example snippets found and included in the LLM prompt.")
        else:
            example_snippets = ""
            print("[INFO] No example snippets found; proceeding with README only.")

        # 3) Build prompt for Constructor
        prompt = self._build_prompt(readme_text, example_snippets)

        # 4) Call Constructor LLM via LangChain interface
        print("[INFO] Calling Constructor LLM to generate demo code...")
        try:
            response = self.llm.invoke(prompt)
        except Exception as e:
            print(f"[ERROR] LLM invocation failed: {type(e).__name__} - {e}")
            print("=== DEMO GENERATION: FAILED DURING LLM CALL ===")
            return None

        # 5) Extract raw text from response
        raw_response = getattr(response, "content", str(response))

        # 6) Strip markdown fences if they slip through
        demo_code = self._extract_code(raw_response)
        if not demo_code or len(demo_code.strip()) == 0:
            print("[ERROR] LLM response did not contain any recognizable Python code.")
            print("=== DEMO GENERATION: FAILED (EMPTY CODE) ===")
            return None

        # 7) Persist generated script
        try:
            self._write_demo(demo_code)
        except Exception as e:
            print(f"[ERROR] Failed to write demo script: {type(e).__name__} - {e}")
            print("=== DEMO GENERATION: FAILED DURING WRITE ===")
            return None

        print(f"[SUCCESS] Demo script written to: {self.output_path}")
        print("=== DEMO GENERATION: COMPLETE ===")
        return self.output_path

    # ---------- Internal helpers ----------

    def _load_readme(self) -> Optional[str]:
        """
        Finds and loads README.* in repo root. Returns truncated content.
        """
        candidates = [
            self.repo_path / "README.md",
            self.repo_path / "README.rst",
            self.repo_path / "README.txt",
            self.repo_path / "README",
        ]

        readme_path = next((p for p in candidates if p.is_file()), None)
        if not readme_path:
            return None

        try:
            text = readme_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"[ERROR] Failed to read README: {e}")
            return None

        # CRITICAL: Use explicit int conversion for comparison
        text_len: int = len(text)
        max_chars: int = int(self.max_readme_chars)
        
        if text_len > max_chars:
            print(f"[INFO] Truncating README from {text_len} -> {max_chars} chars.")
            text = text[:max_chars]

        return text

    def _load_example_snippets(self) -> str:
        """
        Rough heuristic to pull in some example code to guide the LLM.
        Looks under common example directories and picks a few small files.
        """
        candidate_dirs = [
            self.repo_path / "examples",
            self.repo_path / "example",
            self.repo_path / "sample",
            self.repo_path / "samples",
            self.repo_path / "demo",
            self.repo_path / "demos",
            self.repo_path / "sample_script",
        ]

        snippets: List[str] = []
        total_length: int = 0
        
        # CRITICAL: Use explicit integer constants
        MAX_FILE_SIZE: int = 8000
        MAX_TOTAL_SIZE: int = 12000

        for d in candidate_dirs:
            if not d.is_dir():
                continue

            try:
                py_files = list(sorted(d.glob("*.py")))
            except Exception:
                continue

            for py_file in py_files:
                try:
                    code = py_file.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                # CRITICAL: Use explicit int for length
                code_len: int = len(code)
                
                # only take smallish example files
                if code_len <= MAX_FILE_SIZE:
                    try:
                        rel_path = py_file.relative_to(self.repo_path)
                        snippet = f"# File: {rel_path}\n{code}"
                    except ValueError:
                        snippet = f"# File: {py_file.name}\n{code}"
                    
                    snippets.append(snippet)
                    total_length = total_length + code_len
                
                if total_length > MAX_TOTAL_SIZE:
                    break
            
            if total_length > MAX_TOTAL_SIZE:
                break

        return "\n\n".join(snippets)

    def _build_prompt(self, readme: str, example_snippets: str) -> str:
        """
        Constructs an instruction for Constructor to output a concrete,
        end-to-end demo script, with awareness of installed packages.
        """
        repo_name = self.repo_path.name

        # Format installed packages list for the prompt
        packages_info = ""
        
        # CRITICAL: Get count as explicit int
        num_packages: int = len(self.installed_packages)
        
        if num_packages > 0:
            # Show a sample of installed packages (not all of them to save tokens)
            pkg_list: List[str] = sorted([str(p) for p in self.installed_packages])
            sample_packages: List[str] = pkg_list[:50]
            
            packages_info = (
                "\n\nIMPORTANT - INSTALLED PACKAGES IN VIRTUAL ENVIRONMENT:\n"
                "The following packages are confirmed to be installed and available for import:\n"
                f"{', '.join(sample_packages)}"
            )
            
            if num_packages > 50:
                extra: int = num_packages - 50
                packages_info = packages_info + f" (and {extra} more)"
            
            packages_info = packages_info + (
                "\n\nYou MUST ONLY import from packages that are listed above or are part of Python's standard library.\n"
                "Do NOT import packages like 'aiohttp', 'requests', 'httpx', etc. unless they appear in the list above.\n"
            )

        prompt_parts: List[str] = [
            "You are an AI assistant that generates **runnable Python demo scripts** ",
            "for scientific and simulation code repositories.",
            "",
            f"Repository name: {repo_name}",
            "",
            packages_info,
            "",
            "You are given the repository README and (optionally) some example scripts.",
            "",
            "Your task is to produce ONE self-contained Python file that demonstrates a",
            "**realistic end-to-end workflow**, not just a trivial function call.",
            "",
            "Requirements for the demo script:",
            "- Output **only valid Python source code**. No markdown, no backticks, no prose.",
            "- The script must be runnable as `python demo.py` after the user installs the repo's dependencies.",
            "- CRITICAL: Only import packages that are either:",
            "  1. Part of Python's standard library (os, sys, pathlib, json, etc.)",
            "  2. Listed in the INSTALLED PACKAGES section above",
            "- Prefer using the public API (importing the installed package) instead of private internals.",
            "- Show a sequence of meaningful steps (e.g., model/set up a system, run a calculation/simulation, ",
            "  compute a couple of properties, and print or save results).",
            "- Use a `if __name__ == \"__main__\":` block to orchestrate the workflow.",
            "- Add concise comments explaining the high-level workflow, not wall-of-text commentary.",
            "",
            "If the README and examples suggest using environment variables or a working directory, you MAY:",
            "- Read a few key environment variables with sensible defaults (e.g. SMILES strings, IDs, temp, pressure).",
            "- Create a working directory like `./{DBID}` and a subdirectory like `analyze/` for results.",
            "- Write CSV / JSON / text outputs with key results.",
            "",
            "If the project is about simulations (e.g. polymers, MD, QM, etc.),",
            "aim to demonstrate a **mini pipeline** such as:",
            "- build or load a system (e.g. from SMILES or input data),",
            "- set up force fields / parameters,",
            "- run a small simulation or calculation,",
            "- compute and print/save a few physically meaningful properties.",
            "",
            "Avoid:",
            "- Overly long, 300+ line scripts; keep it focused but realistic.",
            "- Copy-pasting whole example files verbatim.",
            "- Relying on external shell scripts or complex job schedulers.",
            "- Importing packages that are NOT in the installed packages list above.",
            "",
            "README CONTENT START",
            "--------------------",
            readme,
            "--------------------",
            "README CONTENT END",
        ]

        if example_snippets and len(example_snippets.strip()) > 0:
            prompt_parts = prompt_parts + [
                "",
                "EXAMPLE PYTHON SCRIPTS (for reference only, do NOT just copy-paste them):",
                "--------------------",
                example_snippets,
                "--------------------",
                "",
            ]

        prompt_parts = prompt_parts + [
            "",
            "Now generate the final demo Python script.",
            "Remember: return ONLY Python code, no ``` fences, no explanation text.",
            "CRITICAL: Only use imports from the INSTALLED PACKAGES list or Python standard library."
        ]

        return "\n".join(prompt_parts)

    def _extract_code(self, raw_response: str) -> str:
        """
        Removes markdown fences if the model still wraps output in ```python ``` etc.
        """
        if "```" not in raw_response:
            return raw_response

        # grab the first fenced code block
        match = re.search(r"```(?:python)?\s*(.*?)```", raw_response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1)
        return raw_response

    def _write_demo(self, code: str) -> None:
        self.output_path.write_text(code, encoding="utf-8")