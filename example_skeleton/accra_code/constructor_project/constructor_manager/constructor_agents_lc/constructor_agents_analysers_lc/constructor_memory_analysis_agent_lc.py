import os

from accra_code.constructor_project.constructor_github_project.constructor_github_project_profiles_analysers.github_project_memory_analyser_static import \
    GitHubProjectMemoryAnalyserStatic
from accra_code.constructor_project.constructor_github_project.github_project import GitHubProject


class ConstructorMemoryAnalysisAgentLC:
    """
    Agent wrapper for memory analysis
    """

    def run(self, project_data: dict, required_packages: list) -> dict:
        """
        Run memory analysis on the project

        Returns:
            Memory analysis results
        """
        if not project_data:
            return {}

        # Create a minimal GitHubProject instance for the analyzer
        project = GitHubProject(
            project_url=project_data.get("project_details", {}).get("repo_url"),
            project_name=project_data.get("repo_name"),
            import_directory=os.path.dirname(project_data.get("path", ""))
        )
        project.project_data = project_data

        # Run the static analyzer
        analyzer = GitHubProjectMemoryAnalyserStatic(project)
        try:
            analyzer.analyze()
            return project.project_data.get("project_details", {}).get("memory_profile", {})
        finally:
            analyzer.finalize()

