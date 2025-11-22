import os
import re
from .github_project_network_analyser import GitHubProjectNetworkAnalyser
from ..github_project_helper import *  # noqa: F403

class GitHubProjectNetworkAnalyserStatic(GitHubProjectNetworkAnalyser):
    NETWORK_KEYWORDS = [
        "socket", "requests", "httpx", "urllib", "ftplib",
        "telnetlib", "httplib", "smtplib", "poplib", "imaplib"
    ]

    def analyze(self):
        """
        Analyze the project for network-related requirements and store results in project_data.
        """
        print("\n Gathering Network Requirements...")

        network_packages = {"requests", "httpx", "urllib3", "socket", "paramiko", "asyncio", "ftplib"}
        web_frameworks = {"flask", "django", "fastapi", "tornado", "pyramid", "bottle"}
        network_patterns = [
            r"requests\.(get|post|put|delete|patch|head)",
            r"httpx\.(get|post|put|delete|patch|head)",
            r"urllib\.request\.(urlopen|Request)",
            r"socket\.(connect|send|recv|bind|listen|accept)",
            r"ftplib\.(FTP|connect|login)",
        ]

        detected_packages, detected_imports, detected_api_calls, detected_frameworks = set(), {}, {}, {}

        for root, _, files in os.walk(self.project.project_data["path"]):
            for file in files:
                file_path = os.path.join(root, file)

                if file in ["requirements.txt", "setup.py", "pyproject.toml"]:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read().lower()
                        detected_packages.update({pkg for pkg in network_packages if pkg in content})

                # Scan .py files
                if file.endswith(".py"):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                        # Detect imports
                        found_imports = {mod for mod in network_packages if
                                         re.search(fr"\bimport {mod}|\bfrom {mod} import", content)}
                        if found_imports:
                            detected_imports[file_path] = list(found_imports)

                        # Detect API calls
                        found_api_calls = {pattern for pattern in network_patterns if re.search(pattern, content)}
                        if found_api_calls:
                            detected_api_calls[file_path] = list(found_api_calls)

                        # Detect web frameworks
                        found_frameworks = [fw for fw in web_frameworks if
                                            re.search(fr"\bimport {fw}|\bfrom {fw} import", content)]
                        if found_frameworks:
                            detected_frameworks[file_path] = found_frameworks

        # Store network analysis results
        cleaned_detected_imports = _extract_library_counts(detected_imports)  # noqa: F405
        cleaned_detected_api_calls = _extract_library_counts(detected_api_calls)  # noqa: F405
        cleaned_detected_frameworks = _extract_library_counts(detected_frameworks)  # noqa: F405

        network_data = {
            "requires_network": bool(
                detected_packages or detected_imports or detected_api_calls or detected_frameworks),
            "dependencies": list(detected_packages),
            "imports": cleaned_detected_imports,
            "api_calls": cleaned_detected_api_calls,
            "web_frameworks": cleaned_detected_frameworks,
        }

        if "project_details" not in self.project.project_data:
            self.project.project_data["project_details"] = {}

        self.project.project_data["project_details"]["network_requirements"] = network_data
        print(network_data)