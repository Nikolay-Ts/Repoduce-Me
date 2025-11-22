import json
import os
import subprocess
import sys
import tempfile
import traceback  # noqa: F401

from .github_project_parallelism_analyser import GitHubProjectParallelismAnalyser
from ..github_project_helper import *  # noqa: F403
from ..temporary_package_manager import TemporaryPackageManager
from ...constructor_project_analyser import ProjectAnalyser
from ...constructor_project import Project

class GitHubProjectParallelismAnalyserStatic(GitHubProjectParallelismAnalyser):

    def __init__(self, project:Project):
        ProjectAnalyser.__init__(self, project)
        self.tmp_package_manager = TemporaryPackageManager(destination_folder=os.path.dirname(project.project_data["path"]))
        self.tmp_package_manager.initialize_existing_packages()


    def analyze(self):
        """
        Runs both threading and multiprocessing reflection and stores the results
        in project_data["project_details"] as separate entries.
        """
        print("\nRunning Parallelism profile analysis...")
        multiprocessing_info, threading_info = self.get_multiprocessing_and_threading_info()
        self.tmp_package_manager.cleanup()

        if "project_details" not in self.project.project_data:
            self.project.project_data["project_details"] = {}
        self.project.project_data["project_details"]["threading_requirements"] = {
            "used": bool(threading_info),
            "files": threading_info
        }
        self.project.project_data["project_details"]["multiprocessing_requirements"] = multiprocessing_info

        print("Threading Requirements:")
        print(threading_info)
        print("Multiprocessing Requirements:")
        print(multiprocessing_info)

    def get_multiprocessing_and_threading_info(self):
        """
        Dynamically imports each Python file in the project and inspects its globals
        to detect objects from multiprocessing-related libraries and threading-related modules.
        Returns a dictionary mapping file paths to multiprocessing-related
        and a dictionary threading-related objects.
        """
        multiprocessing_indicators = [
            "multiprocessing",
            "ProcessPoolExecutor",
            "concurrent.futures.process",
            "joblib",
            "dask.distributed",
            "pathos",
            "ray",
            "celery",
            "billiard",
            "mpire",
        ]
        # Extensive list of indicators for threading-related libraries
        threading_indicators = [
            "threading",  # Standard threading module
            "concurrent.futures.threadpool",  # Sometimes ThreadPoolExecutor is in this module
            "ThreadPoolExecutor",  # Direct usage from concurrent.futures
            "gevent",  # gevent monkey-patches threading
            "eventlet",  # eventlet uses green threads
            "twisted.internet",  # Twisted networking uses its own event loop (similar concurrency)
            "asyncio",  # Although asyncio is asynchronous, it is often used with threads
            "multiprocessing.dummy",  # This is a wrapper around threading
        ]

        threading_usage = {}
        multiprocessing_usage = {}

        for root, _, files in os.walk(self.project.project_data["path"]):
            for filename in files:
                if not filename.endswith(".py"):
                    continue

                file_path = os.path.join(root, filename)

                if _should_skip_file(file_path):  # noqa: F405
                    continue

                required = _extract_imports_from_file(file_path)  # noqa: F405
                self.tmp_package_manager.ensure_packages(required)

                with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as f:
                    storage = f.name

                cmd = [
                    self.tmp_package_manager.py_venv_exe,
                    os.path.join(os.path.dirname(__file__), "run_external_file.py"),
                    file_path,
                    "--output",
                    storage
                ]

                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=self.project.accra_timeout)
                    with open(storage, "r") as f:
                        data = json.load(f)
                    entries = []
                    if isinstance(data, list):
                        entries = data
                    elif isinstance(data, dict):
                        entries = data.get("result", [])
                    else:
                        print(f"[Warning] Unexpected JSON as result of run_external_file with {file_path}: {type(data)}",file=sys.stderr)
                        continue

                    # Filter out only those names/modules that match a multiprocessing and threading indicator
                    found_mp = []
                    found_ti = []
                    for entry in entries:
                        mod = entry.get("module", "").lower()
                        if any(ind.lower() in mod for ind in multiprocessing_indicators):
                            found_mp.append(entry)
                        if any(ind.lower() in mod for ind in threading_indicators):
                            found_ti.append(entry)

                    if found_mp:
                        multiprocessing_usage[file_path] = found_mp
                    if found_ti:
                        threading_usage[file_path] = found_ti

                except FileNotFoundError as e:
                    print(f"[Skip] File not found/bad path: {file_path}: {e}", file=sys.stderr)
                    continue
                except subprocess.CalledProcessError as e:
                    print(f"error launching the command: {cmd}:\n{e.stderr.strip()}")
                    continue
                except json.JSONDecodeError as e:
                    print(f"Error with json decode for file {file_path}: {e}", file=sys.stderr)
                    continue
                except Exception as e:
                    print(f"[Error] Unexpected exception launching subprocess for {file_path}:\n{e}",    file=sys.stderr)
                    continue
                finally:
                    if 'storage' in locals() and os.path.exists(storage):
                        os.remove(storage)

        return _extract_multiprocessing_elements(multiprocessing_usage), threading_usage  # noqa: F405
