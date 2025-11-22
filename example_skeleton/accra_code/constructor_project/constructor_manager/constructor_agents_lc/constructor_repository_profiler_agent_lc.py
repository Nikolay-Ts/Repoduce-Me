import os.path

from accra_code.constructor_project.constructor_github_project.github_project import GitHubProject

class ConstructorRepositoryProfilerAgentLC:
    """
    Agent to analyze a GitHub repository.
    """

    def run(self, repo_url: str, reuse_existing: bool = False):
        repo_url = repo_url.strip().rstrip("/")
        repo_path = (
            repo_url.strip()
            .replace("https://github.com/", "")
            .replace("github.com/", "")
        )
        project = GitHubProject(
            project_url=repo_url,
            project_name=os.path.basename(repo_path),
            github_owner=os.path.dirname(repo_path),
            github_path=repo_path,
            reuse_existing=reuse_existing,
        )
        project.create_project_profile()
        dimensions = project.predict_project_dimension()
        return {
            "repo": repo_url,
            "project_data": project.project_data,
            "dimensions": dimensions,
        }
