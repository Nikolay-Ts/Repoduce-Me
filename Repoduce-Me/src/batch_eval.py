import subprocess
import sys
import textwrap
from pathlib import Path
from typing import List, Dict, Any

ROOT = Path(__file__).resolve().parents[1]
MAIN_SCRIPT = ROOT / "src" / "main.py"

TMP_DIR = ROOT / "tmp"
REPO_DIR = TMP_DIR / "repo"
VENV_DIR = TMP_DIR / ".venv_repro"

# Demo file name must match DemoCreator's output_filename
DEMO_FILENAME = "generated_demo.py"

LOG_DIR = ROOT / "batch_logs"
RESULTS_CSV = ROOT / "batch_results.csv"

# The list of paper URLs to evaluate
PAPER_URLS: List[str] = [
    "https://arxiv.org/pdf/2203.14090",
    "https://arxiv.org/pdf/1907.10902",
    "https://arxiv.org/pdf/1802.03426",
    "https://arxiv.org/pdf/2207.12274",
    "https://genomebiology.biomedcentral.com/counter/pdf/10.1186/s13059-017-1382-0.pdf",
    "https://arxiv.org/pdf/2406.07817",
    "https://www.theoj.org/joss-papers/joss.07975/10.21105.joss.07975.pdf",
    "https://arxiv.org/pdf/2103.16196v2",
    "https://arxiv.org/pdf/2307.08234v2",
    "https://arxiv.org/pdf/2507.06825",
    "https://arxiv.org/pdf/2506.01192",
    "https://arxiv.org/pdf/2506.01151",
    "https://arxiv.org/pdf/2507.07257",
    "https://arxiv.org/pdf/2507.07101",
    "https://arxiv.org/pdf/2507.06849",
    "https://arxiv.org/pdf/2507.06219",
    "https://arxiv.org/pdf/2507.04127",
    "https://arxiv.org/pdf/2507.03009",
    "https://arxiv.org/pdf/2506.23825",
    "https://arxiv.org/pdf/2506.21182",
    "https://arxiv.org/pdf/2506.19398",
    "https://arxiv.org/pdf/2506.14965",
    "https://arxiv.org/pdf/2506.12494",
    "https://arxiv.org/pdf/2506.09081",
    "https://arxiv.org/pdf/2506.08889",
    "https://arxiv.org/pdf/2506.03887",
    "https://arxiv.org/pdf/2506.01853",
    "https://arxiv.org/pdf/2506.01822",
    "https://arxiv.org/pdf/2506.01268",
    "https://arxiv.org/pdf/2505.23313",
    "https://arxiv.org/pdf/2505.22296",
    "https://arxiv.org/pdf/2505.21297",
    "https://arxiv.org/pdf/2505.20414",
    "https://arxiv.org/pdf/2505.18582",
    "https://arxiv.org/pdf/2505.17756",
    "https://arxiv.org/pdf/2505.15307",
    "https://arxiv.org/pdf/2505.15155",
    "https://arxiv.org/pdf/2505.13307",
    "https://arxiv.org/pdf/2505.12668",
    "https://arxiv.org/pdf/2505.03336",
    "https://arxiv.org/pdf/2505.02395",
    "https://arxiv.org/pdf/2505.01257",
    "https://arxiv.org/pdf/2504.20073",
    "https://arxiv.org/pdf/2504.15329",
    "https://arxiv.org/pdf/2504.14603",
    "https://arxiv.org/pdf/2504.13934",
    "https://arxiv.org/pdf/2504.13619",
    "https://arxiv.org/pdf/2504.20650",
    "https://arxiv.org/pdf/2504.10591",
    "https://arxiv.org/pdf/2504.09975",
    "https://arxiv.org/pdf/2504.08339",
    "https://arxiv.org/pdf/2504.07439",
    "https://arxiv.org/pdf/2504.07091",
    "https://arxiv.org/pdf/2504.00906",
    "https://arxiv.org/pdf/2504.00882",
    "https://arxiv.org/pdf/2503.22673",
    "https://arxiv.org/pdf/2503.20563",
    "https://arxiv.org/pdf/2503.20068",
    "https://arxiv.org/pdf/2503.17076",
    "https://arxiv.org/pdf/2503.15621",
    "https://arxiv.org/pdf/2503.15438",
    "https://arxiv.org/pdf/2503.12340",
    "https://arxiv.org/pdf/2503.11509",
    "https://arxiv.org/pdf/2503.11070",
    "https://arxiv.org/pdf/2503.10284",
    "https://arxiv.org/pdf/2503.09642",
    "https://arxiv.org/pdf/2503.09033",
    "https://arxiv.org/pdf/2503.08373",
    "https://arxiv.org/pdf/2503.08354",
    "https://arxiv.org/pdf/2503.07465",
    "https://arxiv.org/pdf/2503.07091",
    "https://arxiv.org/pdf/2503.07029",
    "https://arxiv.org/pdf/2503.06252",
    "https://arxiv.org/pdf/2503.05447",
    "https://arxiv.org/pdf/2503.04548",
    "https://arxiv.org/pdf/2503.04065",
    "https://arxiv.org/pdf/2503.03669",
    "https://arxiv.org/pdf/2503.02950",
    "https://arxiv.org/pdf/2503.01840",
    "https://arxiv.org/pdf/2503.01461",
    "https://arxiv.org/pdf/2502.20762",
    "https://arxiv.org/pdf/2502.20272",
    "https://arxiv.org/pdf/2502.20110",
    "https://arxiv.org/pdf/2502.19854",
    "https://arxiv.org/pdf/2502.19209",
    "https://arxiv.org/pdf/2502.18834",
    "https://arxiv.org/pdf/2502.18807",
    "https://arxiv.org/pdf/2502.16776",
    "https://arxiv.org/pdf/2502.15824",
    "https://arxiv.org/pdf/2502.15589",
    "https://arxiv.org/pdf/2502.13785",
    "https://arxiv.org/pdf/2502.13716",
    "https://arxiv.org/pdf/2502.10470",
    "https://arxiv.org/pdf/2502.09390",
    "https://arxiv.org/pdf/2502.07972",
    "https://arxiv.org/pdf/2502.05505",
]

# STEP markers used in main.py logs
STEP_MARKERS = {
    1: "--- STEP 1:",
    2: "--- STEP 2:",
    3: "--- STEP 3:",
    4: "--- STEP 4:",
    5: "--- STEP 5:",
    6: "--- STEP 6:",
}


# ---------- Helpers ----------

def run_subprocess(cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a subprocess and return the result."""
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def detect_last_step(log_text: str) -> int:
    """
    Detect the highest step number that appears in the main.py log.
    Returns 0 if no step marker was found.
    """
    last_step = 0
    for step, marker in STEP_MARKERS.items():
        if marker in log_text:
            last_step = max(last_step, step)
    return last_step


def extract_last_error_line(log_text: str) -> str:
    """Return the last line containing [ERROR] or [FATAL], or empty string."""
    lines = log_text.splitlines()
    for line in reversed(lines):
        if "[ERROR]" in line or "[FATAL]" in line:
            return line.strip()
    return ""


def get_venv_python() -> Path:
    """Return the python executable path inside tmp/.venv_repro."""
    if sys.platform.startswith("win"):
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run_main_for_url(url: str, index: int) -> Dict[str, Any]:
    """
    Run `python src/main.py <url> --tmp` and capture:
    - return code
    - stage reached
    - log file path
    - error summary
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"log_{index:03d}.txt"

    cmd = [sys.executable, str(MAIN_SCRIPT), url, "--tmp", "--cleanup-all"]
    print(f"\n=== [{index:03d}] Running main.py for URL ===")
    print(f"URL: {url}")
    print(f"CMD: {' '.join(cmd)}")

    result = run_subprocess(cmd, cwd=ROOT)

    # Combine stdout + stderr into a single log
    combined_log = result.stdout + "\n" + result.stderr
    log_path.write_text(combined_log, encoding="utf-8")

    last_step = detect_last_step(combined_log)
    error_line = extract_last_error_line(combined_log)

    pipeline_ok = (result.returncode == 0)

    return {
        "url": url,
        "index": index,
        "pipeline_rc": result.returncode,
        "pipeline_ok": pipeline_ok,
        "last_step": last_step,
        "log_path": str(log_path.relative_to(ROOT)),
        "pipeline_error": error_line,
    }


def run_generated_demo() -> Dict[str, Any]:
    """
    Run tmp/repo/generated_demo.py using tmp/.venv_repro python, if present.

    Returns:
        dict with:
            demo_exists: bool
            venv_python_exists: bool
            demo_rc: int | None
            demo_ok: bool
            demo_error_summary: str
    """
    demo_path = REPO_DIR / DEMO_FILENAME
    venv_python = get_venv_python()

    result: Dict[str, Any] = {
        "demo_exists": demo_path.is_file(),
        "venv_python_exists": venv_python.is_file(),
        "demo_rc": None,
        "demo_ok": False,
        "demo_error_summary": "",
    }

    if not result["demo_exists"] or not result["venv_python_exists"]:
        # Nothing to run
        return result

    cmd = [str(venv_python), DEMO_FILENAME]
    print(f"[DEMO] Running generated demo: {demo_path}")
    print(f"[DEMO] CMD: {' '.join(cmd)}")

    proc = run_subprocess(cmd, cwd=demo_path.parent)
    result["demo_rc"] = proc.returncode
    result["demo_ok"] = (proc.returncode == 0)

    if not result["demo_ok"]:
        # Capture a short summary from stderr (or stdout fallback)
        stderr = proc.stderr.strip()
        stdout = proc.stdout.strip()
        summary = stderr or stdout
        if len(summary) > 500:
            summary = summary[:500] + "... [truncated]"
        result["demo_error_summary"] = summary

    return result


def write_results_csv(rows: List[Dict[str, Any]]) -> None:
    """Write all results into a CSV file for downstream analysis."""
    import csv

    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "index",
        "url",
        "pipeline_rc",
        "pipeline_ok",
        "last_step",
        "pipeline_error",
        "log_path",
        "demo_exists",
        "venv_python_exists",
        "demo_rc",
        "demo_ok",
        "demo_error_summary",
    ]

    with RESULTS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"\n=== Batch evaluation summary written to: {RESULTS_CSV} ===")


# ---------- Main batch runner ----------

def main() -> None:
    print(textwrap.dedent(f"""
    ========================================
    Batch Evaluation Runner
    Root: {ROOT}
    Main script: {MAIN_SCRIPT}
    URLs to process: {len(PAPER_URLS)}
    ========================================
    """))

    results: List[Dict[str, Any]] = []

    for idx, url in enumerate(PAPER_URLS, start=1):
        # 1) Run the main pipeline
        main_res = run_main_for_url(url, idx)

        # 2) If pipeline succeeded, try running generated_demo.py
        demo_res: Dict[str, Any]
        if main_res["pipeline_ok"]:
            demo_res = run_generated_demo()
        else:
            demo_res = {
                "demo_exists": False,
                "venv_python_exists": False,
                "demo_rc": None,
                "demo_ok": False,
                "demo_error_summary": "",
            }

        # Merge dictionaries for final row
        row = {**main_res, **demo_res}
        results.append(row)

        # Print a concise one-line status per URL
        print(
            f"[RESULT {idx:03d}] "
            f"pipeline_ok={row['pipeline_ok']} "
            f"last_step={row['last_step']} "
            f"demo_ok={row['demo_ok']}"
        )

    write_results_csv(results)


if __name__ == "__main__":
    main()
