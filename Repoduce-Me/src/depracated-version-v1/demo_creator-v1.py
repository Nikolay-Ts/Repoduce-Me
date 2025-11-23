from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from constructor_model import ConstructorModel


class DemoCreator:
    """
    Uses Constructor LLM to synthesize a runnable demo Python script
    from a cloned repository, primarily based on its README and examples.
    """

    def __init__(
        self,
        repo_path: Path,
        output_filename: str = "generated_demo.py",
        max_readme_chars: int = 8000,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.output_path = self.repo_path / output_filename
        self.max_readme_chars = max_readme_chars

        # Stateless: single-shot code generation
        self.llm = ConstructorModel(model="gpt-5.1")

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
        if example_snippets.strip():
            print("[INFO] Example snippets found and included in the LLM prompt.")
        else:
            print("[INFO] No example snippets found; proceeding with README only.")

        # 3) Build prompt for Constructor
        prompt = self._build_prompt(readme_text, example_snippets)

        # 4) Call Constructor LLM via LangChain interface
        print("[INFO] Calling Constructor LLM to generate demo code...")
        try:
            # ChatOpenAI-style usage: returns a ChatMessage-like object
            response = self.llm.invoke(prompt)
        except Exception as e:
            print(f"[ERROR] LLM invocation failed: {type(e).__name__} - {e}")
            print("=== DEMO GENERATION: FAILED DURING LLM CALL ===")
            return None

        # 5) Extract raw text from response
        raw_response = getattr(response, "content", str(response))

        # 6) Strip markdown fences if they slip through
        demo_code = self._extract_code(raw_response)
        if not demo_code or not demo_code.strip():
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

        if len(text) > self.max_readme_chars:
            print(f"[INFO] Truncating README from {len(text)} -> {self.max_readme_chars} chars.")
            text = text[: self.max_readme_chars]

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

        snippets: list[str] = []

        for d in candidate_dirs:
            if not d.is_dir():
                continue

            for py_file in sorted(d.glob("*.py")):
                try:
                    code = py_file.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                # only take smallish example files
                if len(code) <= 8000:
                    snippets.append(f"# File: {py_file.relative_to(self.repo_path)}\n{code}")
                if len("".join(snippets)) > 12000:
                    break

        return "\n\n".join(snippets)

    def _build_prompt(self, readme: str, example_snippets: str) -> str:
        """
        Constructs an instruction for Constructor to output a concrete,
        end-to-end demo script, closer in spirit to real workflows.
        """
        repo_name = self.repo_path.name

        prompt_parts = [
            "You are an AI assistant that generates **runnable Python demo scripts** ",
            "for scientific and simulation code repositories.",
            "",
            f"Repository name: {repo_name}",
            "",
            "You are given the repository README and (optionally) some example scripts.",
            "",
            "Your task is to produce ONE self-contained Python file that demonstrates a",
            "**realistic end-to-end workflow**, not just a trivial function call.",
            "",
            "Requirements for the demo script:",
            "- Output **only valid Python source code**. No markdown, no backticks, no prose.",
            "- The script must be runnable as `python demo.py` after the user installs the repo's dependencies.",
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
            "",
            "README CONTENT START",
            "--------------------",
            readme,
            "--------------------",
            "README CONTENT END",
        ]

        if example_snippets.strip():
            prompt_parts += [
                "",
                "EXAMPLE PYTHON SCRIPTS (for reference only, do NOT just copy-paste them):",
                "--------------------",
                example_snippets,
                "--------------------",
                "",
            ]

        prompt_parts += [
            "",
            "Now generate the final demo Python script.",
            "Remember: return ONLY Python code, no ``` fences, no explanation text."
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

