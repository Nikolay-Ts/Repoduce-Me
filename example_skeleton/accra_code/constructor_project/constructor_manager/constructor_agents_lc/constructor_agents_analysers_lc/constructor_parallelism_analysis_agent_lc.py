import os

from accra_code.constructor_project.constructor_github_project.constructor_github_project_profiles_analysers.github_project_parallelism_analyser_static import \
    GitHubProjectParallelismAnalyserStatic
from accra_code.constructor_project.constructor_github_project.github_project import GitHubProject


class ConstructorParallelismAnalysisAgentLC:
    """
    Agent wrapper for parallelism (threading/multiprocessing) analysis
    """

    def run(self, project_data: dict, required_packages: list) -> dict:
        """
        Run parallelism analysis on the project

        Returns:
            Parallelism analysis results
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
        analyzer = GitHubProjectParallelismAnalyserStatic(project)
        try:
            analyzer.analyze()
            return {
                "threading": project.project_data.get("project_details", {}).get("threading_requirements", {}),
                "multiprocessing": project.project_data.get("project_details", {}).get("multiprocessing_requirements",
                                                                                       {})
            }
        finally:
            analyzer.finalize()