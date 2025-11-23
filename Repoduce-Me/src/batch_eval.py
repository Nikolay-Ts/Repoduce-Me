import subprocess
import sys
import textwrap
import time
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import traceback

ROOT = Path(__file__).resolve().parents[1]
MAIN_SCRIPT = ROOT / "src" / "main.py"

TMP_DIR = ROOT / "tmp"
REPO_DIR = TMP_DIR / "repo"
VENV_DIR = TMP_DIR / ".venv_repro"
WORKSPACE_DIR = ROOT / "workspace"

# Demo file name must match DemoCreator's output_filename
DEMO_FILENAME = "generated_demo.py"

LOG_DIR = ROOT / "batch_logs"
RESULTS_CSV = ROOT / "batch_results.csv"
RESULTS_JSON = ROOT / "batch_results.json"
SUMMARY_TXT = ROOT / "batch_summary.txt"

# Timeout settings (in seconds)
PIPELINE_TIMEOUT = 600  # 10 minutes per paper
DEMO_TIMEOUT = 120      # 2 minutes per demo

# Full list of paper URLs - uncomment to run all 96
ALL_PAPER_URLS: List[str] = [
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

# Sample 10 random papers for quick testing
import random
random.seed()  # For reproducibility
PAPER_URLS = random.sample(ALL_PAPER_URLS, min(10, len(ALL_PAPER_URLS)))

# To run ALL papers, uncomment this:
# PAPER_URLS = ALL_PAPER_URLS

# STEP markers used in main.py logs
STEP_MARKERS = {
    1: "--- STEP 1:",
    2: "--- STEP 2:",
    3: "--- STEP 3:",
    4: "--- STEP 4:",
    5: "--- STEP 5:",
    6: "--- STEP 6:",
    7: "--- STEP 7:",
}

STEP_NAMES = {
    0: "No steps completed",
    1: "PDF Download/Loading",
    2: "GitHub URL Extraction",
    3: "Repository Cloning",
    4: "Dependency Extraction",
    5: "Virtual Environment Setup",
    6: "Demo Generation",
    7: "Demo Execution",
}


# ---------- Helpers ----------

def run_subprocess(cmd: List[str], cwd: Path, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    """Run a subprocess with optional timeout and return the result."""
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=-1,
            stdout=e.stdout.decode() if e.stdout else "",
            stderr=f"TIMEOUT after {timeout}s\n" + (e.stderr.decode() if e.stderr else ""),
        )


def detect_last_step(log_text: str) -> int:
    """Detect the highest step number that appears in the main.py log."""
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


def categorize_error(log_text: str, error_line: str) -> str:
    """Categorize the type of error based on log content."""
    log_lower = log_text.lower()
    error_lower = error_line.lower()
    
    if "timeout" in log_lower or "timeout" in error_lower:
        return "TIMEOUT"
    elif "no github link found" in log_lower:
        return "NO_GITHUB_LINK"
    elif "git clone failed" in log_lower:
        return "CLONE_FAILED"
    elif "typeerror" in log_lower and "list" in log_lower:
        return "PARSER_TYPE_ERROR"
    elif "modulenotfounderror" in log_lower or "importerror" in log_lower:
        return "MISSING_DEPENDENCY"
    elif "pip install" in error_lower:
        return "INSTALL_FAILED"
    elif "virtual environment" in error_lower:
        return "VENV_FAILED"
    elif "demo generation failed" in log_lower:
        return "DEMO_GEN_FAILED"
    elif "network" in error_lower or "connection" in error_lower:
        return "NETWORK_ERROR"
    elif error_line:
        return "OTHER_ERROR"
    else:
        return "UNKNOWN"


def get_venv_python() -> Path:
    """Return the python executable path inside tmp/.venv_repro."""
    if sys.platform.startswith("win"):
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def extract_repo_name(log_text: str) -> Optional[str]:
    """Extract repository name from log if available."""
    import re
    # Look for the actual repo name, not just "repo"
    match = re.search(r"Repository successfully cloned into: .*?/([^/\n]+)(?:\s|$)", log_text)
    if match:
        name = match.group(1).strip()
        # Filter out the partial matches
        if name != "repo" and "---" not in name:
            return name
    return None


def cleanup_tmp_directory():
    """Clean up tmp/ directory between runs."""
    if TMP_DIR.exists():
        try:
            shutil.rmtree(TMP_DIR)
            print(f"  [CLEANUP] Removed tmp/ directory")
        except Exception as e:
            print(f"  [WARNING] Could not fully clean tmp/: {e}")


def run_main_for_url(url: str, index: int, total: int) -> Dict[str, Any]:
    """
    Run main.py WITHOUT cleanup flags, so we can inspect demo afterwards.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"log_{index:03d}.txt"

    # CRITICAL FIX: Remove --cleanup-all so demo persists for inspection
    cmd = [sys.executable, str(MAIN_SCRIPT), url, "--tmp"]
    
    print(f"\n{'='*70}")
    print(f"[{index:03d}/{total:03d}] Processing Paper")
    print(f"{'='*70}")
    print(f"URL: {url}")
    print(f"Log: {log_path.relative_to(ROOT)}")
    print(f"Timeout: {PIPELINE_TIMEOUT}s")
    print(f"{'='*70}")

    start_time = time.time()
    result = run_subprocess(cmd, cwd=ROOT, timeout=PIPELINE_TIMEOUT)
    duration = time.time() - start_time

    combined_log = result.stdout + "\n" + result.stderr
    log_path.write_text(combined_log, encoding="utf-8")

    last_step = detect_last_step(combined_log)
    error_line = extract_last_error_line(combined_log)
    error_category = categorize_error(combined_log, error_line)
    repo_name = extract_repo_name(combined_log)

    pipeline_ok = (result.returncode == 0)
    timed_out = ("TIMEOUT" in combined_log)

    print(f"✓ Pipeline completed in {duration:.1f}s")
    print(f"  Return code: {result.returncode}")
    print(f"  Last step: {last_step} ({STEP_NAMES.get(last_step, 'Unknown')})")
    if error_category != "UNKNOWN":
        print(f"  Error type: {error_category}")
    if repo_name:
        print(f"  Repository: {repo_name}")

    return {
        "url": url,
        "index": index,
        "pipeline_rc": result.returncode,
        "pipeline_ok": pipeline_ok,
        "pipeline_timeout": timed_out,
        "pipeline_duration": round(duration, 2),
        "last_step": last_step,
        "last_step_name": STEP_NAMES.get(last_step, "Unknown"),
        "log_path": str(log_path.relative_to(ROOT)),
        "pipeline_error": error_line,
        "error_category": error_category,
        "repo_name": repo_name or "",
    }


def run_generated_demo() -> Dict[str, Any]:
    """
    Run tmp/repo/generated_demo.py using tmp/.venv_repro python, if present.
    """
    demo_path = REPO_DIR / DEMO_FILENAME
    venv_python = get_venv_python()

    result: Dict[str, Any] = {
        "demo_exists": demo_path.is_file(),
        "venv_python_exists": venv_python.is_file(),
        "demo_rc": None,
        "demo_ok": False,
        "demo_duration": 0.0,
        "demo_timeout": False,
        "demo_error_summary": "",
        "demo_error_type": "",
    }

    if not result["demo_exists"]:
        print(f"  [DEMO] No demo file found at {demo_path}")
        return result
    
    if not result["venv_python_exists"]:
        print(f"  [DEMO] No venv python found at {venv_python}")
        return result

    cmd = [str(venv_python), DEMO_FILENAME]
    print(f"  [DEMO] Running: {DEMO_FILENAME}")

    start_time = time.time()
    proc = run_subprocess(cmd, cwd=demo_path.parent, timeout=DEMO_TIMEOUT)
    duration = time.time() - start_time

    result["demo_rc"] = proc.returncode
    result["demo_ok"] = (proc.returncode == 0)
    result["demo_duration"] = round(duration, 2)
    result["demo_timeout"] = proc.returncode == -1

    if not result["demo_ok"]:
        stderr = proc.stderr.strip()
        stdout = proc.stdout.strip()
        summary = stderr or stdout
        
        if "ModuleNotFoundError" in summary:
            result["demo_error_type"] = "MISSING_MODULE"
            # Extract module name if possible
            import re
            match = re.search(r"No module named ['\"]([^'\"]+)['\"]", summary)
            if match:
                print(f"  [DEMO] Missing module: {match.group(1)}")
        elif "ImportError" in summary:
            result["demo_error_type"] = "IMPORT_ERROR"
        elif "TIMEOUT" in summary:
            result["demo_error_type"] = "TIMEOUT"
        elif summary:
            result["demo_error_type"] = "RUNTIME_ERROR"
            # Show first line of error for quick diagnosis
            first_error_line = summary.split('\n')[0] if '\n' in summary else summary[:100]
            print(f"  [DEMO] Error: {first_error_line}")
        else:
            result["demo_error_type"] = "UNKNOWN"
        
        if len(summary) > 500:
            summary = summary[:500] + "... [truncated]"
        result["demo_error_summary"] = summary

    status = "✓ SUCCESS" if result["demo_ok"] else "✗ FAILED"
    print(f"  [DEMO] Completed in {duration:.1f}s - {status}")
    if not result["demo_ok"] and result["demo_error_type"]:
        print(f"  [DEMO] Error type: {result['demo_error_type']}")

    return result


def write_results_csv(rows: List[Dict[str, Any]]) -> None:
    """Write all results into a CSV file."""
    import csv

    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "index",
        "url",
        "pipeline_rc",
        "pipeline_ok",
        "pipeline_timeout",
        "pipeline_duration",
        "last_step",
        "last_step_name",
        "error_category",
        "pipeline_error",
        "repo_name",
        "log_path",
        "demo_exists",
        "venv_python_exists",
        "demo_rc",
        "demo_ok",
        "demo_timeout",
        "demo_duration",
        "demo_error_type",
        "demo_error_summary",
    ]

    with RESULTS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"\n✓ CSV results written to: {RESULTS_CSV.relative_to(ROOT)}")


def write_results_json(rows: List[Dict[str, Any]], metadata: Dict[str, Any]) -> None:
    """Write results and metadata to JSON."""
    output = {
        "metadata": metadata,
        "results": rows,
    }
    
    with RESULTS_JSON.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print(f"✓ JSON results written to: {RESULTS_JSON.relative_to(ROOT)}")


def write_summary_report(rows: List[Dict[str, Any]], metadata: Dict[str, Any]) -> None:
    """Write a human-readable summary report."""
    total = len(rows)
    pipeline_success = sum(1 for r in rows if r["pipeline_ok"])
    demo_generated = sum(1 for r in rows if r["demo_exists"])
    demo_success = sum(1 for r in rows if r["demo_ok"])
    
    step_counts = {}
    for r in rows:
        step = r["last_step"]
        step_counts[step] = step_counts.get(step, 0) + 1
    
    error_counts = {}
    for r in rows:
        if not r["pipeline_ok"]:
            cat = r["error_category"]
            error_counts[cat] = error_counts.get(cat, 0) + 1
    
    demo_error_counts = {}
    for r in rows:
        if not r["demo_ok"] and r["demo_error_type"]:
            typ = r["demo_error_type"]
            demo_error_counts[typ] = demo_error_counts.get(typ, 0) + 1
    
    report = textwrap.dedent(f"""
    {'='*70}
    BATCH EVALUATION SUMMARY REPORT
    {'='*70}
    
    Run Date: {metadata['start_time']}
    Total Duration: {metadata['total_duration']:.1f}s ({metadata['total_duration']/60:.1f} min)
    Papers Processed: {total}
    
    {'='*70}
    PIPELINE SUCCESS RATES
    {'='*70}
    
    Pipeline Completion:  {pipeline_success:3d}/{total} ({100*pipeline_success/total:.1f}%)
    Demo Generated:       {demo_generated:3d}/{total} ({100*demo_generated/total:.1f}%)
    Demo Executed OK:     {demo_success:3d}/{total} ({100*demo_success/total:.1f}%)
    
    {'='*70}
    STAGE DISTRIBUTION (Last Step Reached)
    {'='*70}
    
    """)
    
    for step in sorted(step_counts.keys(), reverse=True):
        count = step_counts[step]
        pct = 100 * count / total
        report += f"  Step {step} ({STEP_NAMES.get(step, 'Unknown'):25s}): {count:3d} ({pct:5.1f}%)\n"
    
    if error_counts:
        report += textwrap.dedent(f"""
    
    {'='*70}
    PIPELINE ERROR CATEGORIES
    {'='*70}
    
    """)
        for cat, count in sorted(error_counts.items(), key=lambda x: -x[1]):
            report += f"  {cat:25s}: {count:3d}\n"
    
    if demo_error_counts:
        report += textwrap.dedent(f"""
    
    {'='*70}
    DEMO ERROR TYPES
    {'='*70}
    
    """)
        for typ, count in sorted(demo_error_counts.items(), key=lambda x: -x[1]):
            report += f"  {typ:25s}: {count:3d}\n"
    
    # Show successful demos for inspection
    successful_demos = [r for r in rows if r["demo_ok"]]
    if successful_demos:
        report += textwrap.dedent(f"""
    
    {'='*70}
    SUCCESSFUL DEMOS ({len(successful_demos)} papers)
    {'='*70}
    
    """)
        for r in successful_demos[:10]:
            report += f"  [{r['index']:03d}] {r['repo_name'] or 'Unknown'}\n"
            report += f"       URL: {r['url']}\n"
            report += f"       Duration: {r['demo_duration']}s\n"
            report += "\n"
    
    # Show detailed demo failures
    failed_demos = [r for r in rows if r["demo_exists"] and not r["demo_ok"]]
    if failed_demos:
        report += textwrap.dedent(f"""
    
    {'='*70}
    DEMO EXECUTION FAILURES ({len(failed_demos)} papers)
    {'='*70}
    
    """)
        for r in failed_demos[:10]:
            report += f"  [{r['index']:03d}] {r['demo_error_type']}\n"
            report += f"       Repo: {r['repo_name'] or 'Unknown'}\n"
            report += f"       URL: {r['url']}\n"
            if r['demo_error_summary']:
                preview = r['demo_error_summary'].split('\n')[0][:100]
                report += f"       Error: {preview}\n"
            report += "\n"
    
    failed_pipelines = [r for r in rows if not r["pipeline_ok"]]
    if failed_pipelines:
        report += textwrap.dedent(f"""
    
    {'='*70}
    TOP 10 PIPELINE FAILURES (for detailed inspection)
    {'='*70}
    
    """)
        for r in failed_pipelines[:10]:
            report += f"  [{r['index']:03d}] Step {r['last_step']} - {r['error_category']}\n"
            report += f"       URL: {r['url']}\n"
            report += f"       Log: {r['log_path']}\n"
            if r['pipeline_error']:
                report += f"       Error: {r['pipeline_error'][:100]}\n"
            report += "\n"
    
    report += f"{'='*70}\n"
    report += f"Full details in: {RESULTS_CSV.relative_to(ROOT)}\n"
    report += f"{'='*70}\n"
    
    with SUMMARY_TXT.open("w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"✓ Summary report written to: {SUMMARY_TXT.relative_to(ROOT)}")
    print("\n" + report)


# ---------- Main batch runner ----------

def main() -> None:
    start_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start_time = time.time()
    
    print(textwrap.dedent(f"""
    {'='*70}
    BATCH EVALUATION RUNNER
    {'='*70}
    Root Directory: {ROOT}
    Main Script:    {MAIN_SCRIPT}
    Papers:         {len(PAPER_URLS)}
    Pipeline Timeout: {PIPELINE_TIMEOUT}s
    Demo Timeout:     {DEMO_TIMEOUT}s
    {'='*70}
    """))

    results: List[Dict[str, Any]] = []

    try:
        for idx, url in enumerate(PAPER_URLS, start=1):
            try:
                # Clean tmp/ before each run for fresh start
                cleanup_tmp_directory()
                
                # 1) Run the main pipeline (without cleanup)
                main_res = run_main_for_url(url, idx, len(PAPER_URLS))

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
                        "demo_duration": 0.0,
                        "demo_timeout": False,
                        "demo_error_summary": "",
                        "demo_error_type": "",
                    }

                row = {**main_res, **demo_res}
                results.append(row)

                # Print concise progress
                demo_status = '✓' if row['demo_ok'] else ('✗' if row['demo_exists'] else '-')
                print(f"\n[PROGRESS] {idx}/{len(PAPER_URLS)} complete - "
                      f"Pipeline: {'✓' if row['pipeline_ok'] else '✗'} "
                      f"Demo: {demo_status}")
                
                # Clean up after demo check
                cleanup_tmp_directory()

            except Exception as e:
                print(f"\n[CRITICAL ERROR] Failed to process URL {idx}: {e}")
                traceback.print_exc()
                results.append({
                    "url": url,
                    "index": idx,
                    "pipeline_rc": -999,
                    "pipeline_ok": False,
                    "pipeline_timeout": False,
                    "pipeline_duration": 0.0,
                    "last_step": 0,
                    "last_step_name": "CRASH",
                    "error_category": "BATCH_RUNNER_ERROR",
                    "pipeline_error": str(e),
                    "repo_name": "",
                    "log_path": "",
                    "demo_exists": False,
                    "venv_python_exists": False,
                    "demo_rc": None,
                    "demo_ok": False,
                    "demo_duration": 0.0,
                    "demo_timeout": False,
                    "demo_error_summary": "",
                    "demo_error_type": "",
                })

    finally:
        total_duration = time.time() - start_time
        
        metadata = {
            "start_time": start_time_str,
            "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_duration": round(total_duration, 2),
            "total_papers": len(PAPER_URLS),
            "processed_papers": len(results),
            "pipeline_timeout": PIPELINE_TIMEOUT,
            "demo_timeout": DEMO_TIMEOUT,
        }
        
        write_results_csv(results)
        write_results_json(results, metadata)
        write_summary_report(results, metadata)


if __name__ == "__main__":
    main()