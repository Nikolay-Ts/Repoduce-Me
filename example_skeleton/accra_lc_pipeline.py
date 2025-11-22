import argparse
import os
import yaml
from urllib.parse import urlparse
import requests
from accra_code.constructor_project.constructor_manager.constructor_manager_lc import (
    ConstructorManagerLC,
)
from constructor_adapter.constructor_stateless_adapter import (
    StatelessConstructorAdapter,
)

def format_result_to_facts(result: dict) -> dict:
    project = result.get("result", {})
    project_data = project.get("project_data", {})

    facts = {
        "Repository name": project_data.get("repo_name"),
    }
    
    if "path" in project_data and project_data["path"]:
        facts["Project Path"] = project_data["path"]
    if "example_filename" in project_data and project_data["example_filename"]:
        facts["Example File"] = project_data['example_filename']
    if "repo_url" in result and result["repo_url"]:
        facts["Repository URL"] = result['repo_url']

    dimensions = project.get("dimensions", {})
    if "CPUs" in dimensions and dimensions["CPUs"] is not None:
        facts["CPU Usage"] = f"{dimensions['CPUs']:.1f}"
    if "GPUs" in dimensions and dimensions["GPUs"] is not None:
        facts["GPU Usage"] = f"{dimensions['GPUs']:.1f}"
    if "RAM" in dimensions and dimensions["RAM"] is not None:
        facts["RAM Usage"] = f"{dimensions['RAM']:.1f}"
    if "Storage" in dimensions and dimensions["Storage"] is not None:
        facts["Storage Usage (GB)"] = f"{dimensions['Storage']}"
    if "NetworkBandwidth" in dimensions and dimensions["NetworkBandwidth"] is not None:
        facts["Network Bandwidth Usage"] = f"{dimensions['NetworkBandwidth']}"

    details = project_data.get("project_details", {})
    if "github_owner" in details and details["github_owner"]:
        facts["Repository Owner"] = details["github_owner"]
    if "github_user" in details and details["github_user"]:
        facts["Repository User"] = details["github_user"]
    if "created_at" in details and details["created_at"]:
        facts["Repository creation Date"] = details["created_at"]
    if "language" in details and details["language"]:
        facts["Repository programming Language"] = details["language"]
    if "license" in details and details["license"]:
        facts["Repository License"] = details["license"]
        
    return facts

def is_valid_file_or_url(paper_url):
    if os.path.isfile(paper_url):
        return True

    # Check if it's a valid URL and accessible
    parsed = urlparse(paper_url)
    is_valid = False
    if parsed.scheme in ("http", "https"):
        try:
            response = requests.head(paper_url, timeout=10)
            is_valid = response.status_code == 200
        except requests.RequestException as e:
            print(f"Error in head request: {e}")
    return is_valid

def main(
    paper_url, user_interaction, *, repo_url=None, upload_to_km, reuse_existing=False
):
    manager = ConstructorManagerLC(
        user_interaction, repo_url=repo_url, reuse_existing=reuse_existing
    )
    result = manager.run(paper_url)

    print("\n========== ANALYSIS RESULT ==========")
    # result is a dict containing repository info and its analysis/dimensions
    # The structure should be (from ConstructorRepositoryProfilerAgentLC):
    # {
    #   "repo": ...,
    #   "project_data": ...,
    #   "dimensions": ...
    # }
    print(yaml.dump(result, default_flow_style=False))

    if upload_to_km:
        adapter = StatelessConstructorAdapter()       
        adapter.add_facts(format_result_to_facts(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run ACCRa to analyze a scientific paper and the related GitHub repository."
    )
    parser.add_argument(
        "paper_url", help="URL or local path to the scientific paper (PDF)"
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Enable interactive mode for user input",
    )
    parser.add_argument("--repo_url", help="Git repo url to be used")
    parser.add_argument(
        "--upload-to-km",
        action="store_true",
        help="Upload the generated markdown analysis to Constructor Knowledge Model (requires CONSTRUCTOR_API_KEY and CONSTRUCTOR_KM_ID in .env)",
    )
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="Reuse previously downloaded project folder instead of creating a new one (e.g., project.1, project.2). Warning: Previous runs may have modified the folder state.",
    )
    args = parser.parse_args()

    if not is_valid_file_or_url(args.paper_url):
        print(f"Error: '{args.paper_url}' is not a valid file path or a reachable URL.")
        exit(1)

    exit(
        main(
            args.paper_url,
            args.interactive,
            repo_url=args.repo_url,
            upload_to_km=args.upload_to_km,
            reuse_existing=args.reuse_existing,
        )
    )
