# Repoduce-Me

A streamlined pipeline that converts a research paper into a runnable demo by extracting its GitHub repository, resolving dependencies, creating an isolated environment, and generating an executable example script.

## Core Capabilities

- Parse a paper (PDF or ArXiv URL) and detect its GitHub repo.
- Clone the repo in a temporary or persistent workspace.
- Infer or normalize Python dependencies.
- Build a Python virtual environment and install all requirements safely.
- Use a Constructor-integrated LLM to generate a runnable demo (`generated_demo.py`).
- Optionally execute the demo automatically.
- Support batch processing for multiple papers.

---

## Repository Structure

```text
Repoduce-Me/
  .gitignore
  requirements.txt
  Repoduce-Me/
    src/
      main.py
      downloader.py
      paper_extracter.py
      requirements_extract.py
      venv_create.py
      demo_creator.py
      batch_eval.py
      cleanup.py
    ConstructorAdapter/
    test/
  example_skeleton/
````

Work is typically done inside:

```bash
cd Repoduce-Me/Repoduce-Me
```

---

## Pipeline Overview

1. **Parse Input** — PDF or URL → extracted text.
2. **Detect GitHub Repo** — via regex or LLM fallback.
3. **Clone Repo** — into `tmp/` or `workspace/`.
4. **Infer Dependencies** — pyproject/setup/requirements or static import analysis.
5. **Build Venv** — install normalized dependencies.
6. **Generate Demo** — LLM produces `generated_demo.py`.
7. **(Optional) Auto-Run** — execute demo inside the venv.
8. **Cleanup** — remove `tmp/` and/or `workspace/`.

---

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r ../requirements.txt
```

Constructor adapter (optional but required for demo generation):

```bash
cd Repoduce-Me/Repoduce-Me/ConstructorAdapter
pip install -e .
```

Environment variables:

```
CONSTRUCTOR_API_KEY=
CONSTRUCTOR_API_URL=
CONSTRUCTOR_KM_ID=
```

---

## Usage

Run full pipeline:

```bash
python src/main.py https://arxiv.org/pdf/XXXX.YYYYY.pdf
```

Run with explicit GitHub URL:

```bash
python src/main.py paper.pdf --github https://github.com/owner/repo
```

Use ephemeral workspace:

```bash
python src/main.py URL --tmp
```

Auto-run the generated demo:

```bash
python src/main.py URL --auto-run
```

Cleanup:

```bash
python src/cleanup.py --tmp --workspace
```

---

## Batch Mode

```bash
python src/batch_eval.py
```

Processes multiple papers, records logs, and outputs aggregated summaries.

---

