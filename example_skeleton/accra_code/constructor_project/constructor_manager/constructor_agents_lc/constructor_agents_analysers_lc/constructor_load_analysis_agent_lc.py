import os

from accra_code.constructor_project.constructor_github_project.constructor_github_project_profiles_analysers.github_project_load_analyser_static import \
    GitHubProjectLoadAnalyserStatic
from accra_code.constructor_project.constructor_github_project.github_project import GitHubProject


class ConstructorLoadAnalysisAgentLC:
    """
    Agent wrapper for load (CPU/GPU) analysis
    """

    def run(self, project_data: dict, required_packages: list) -> dict:
        """
        Run load analysis on the project

        Returns:
            Load analysis results
        """
        if not project_data:
            return {}

        # Create a minimal GitHubProject instance
        project = GitHubProject(
            project_url=project_data.get("project_details", {}).get("repo_url"),
            project_name=project_data.get("repo_name"),
            import_directory=os.path.dirname(project_data.get("path", ""))
        )
        project.project_data = project_data

        # Run the static analyzer
        analyzer = GitHubProjectLoadAnalyserStatic(project)
        try:
            analyzer.analyze()
            return project.project_data.get("project_details", {}).get("load_profile", {})
        finally:
            analyzer.finalize()
