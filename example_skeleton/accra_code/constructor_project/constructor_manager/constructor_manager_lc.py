import os.path
from langgraph.graph import StateGraph

from .constructor_agents_lc.constructor_paper_agent_lc import ConstructorPaperAgentLC
from accra_code.constructor_project.constructor_github_project.github_project import GitHubProject
from ..constructor_github_project.constructor_github_project_profiles_analysers.github_project_example_finder import GithubProjectExampleFinder
from accra_code.constructor_project.constructor_github_project.constructor_github_project_errors_analysers.error_manager import ErrorManager

class ConstructorManagerLC:
    def __init__(self, user_interaction=False, *, repo_url=None, reuse_existing=False):
        self.user_interaction = user_interaction
        self.repo_url = repo_url
        self.reuse_existing = reuse_existing
        self.graph = StateGraph(dict)
        self._build_graph()
        self.compiled_graph = self.graph.compile()

    def _build_graph(self):
        self.paper_agent = ConstructorPaperAgentLC()
        self.error_handler = ErrorManager()

        def paper_parser(state: dict):
            if self.repo_url:
                return {"repo_url": self.repo_url}
            pdf_path = state["pdf_path"]
            out = self.paper_agent.run(pdf_path, self.user_interaction)
            state.update(out)
            return state

        # We now build the GitHubProject directly here
        def build_project(state: dict):
            repo_url = (state["repo_url"] or "").strip().rstrip("/")
            # URL conversion
            repo_path = (
                repo_url.strip()
                .replace("https://github.com/", "")
                .replace("github.com/", "")
            )
            # GitHubProject object
            project = GitHubProject(
                project_url=repo_url,
                project_name=os.path.basename(repo_path),
                github_owner=os.path.dirname(repo_path),
                github_path=repo_path,
                reuse_existing=self.reuse_existing,
            )
            state["project"] = project
            
            return state

        # Separate function to create the profile
        def manage_project_profile_creation(state: dict):
            project: GitHubProject = state["project"]
            if not project:
                state["error"] = "No project to profile"
                return state
            # analyses project and creates metadata
            project.create_project_profile()
            state["project_data"] = project.project_data
            return state

        # Integration of example finder
        def example_finder(state: dict):
            project: GitHubProject = state["project"]
            if not project:
                state["examples_found"] = False
                return state
            # Here we run the pipeline
            example_finder = GithubProjectExampleFinder(project)
            found = example_finder.analyze()

            # We add the results to the state (a bool)
            state["examples_found"] = found
            return state

        def log_result(state: dict):
            print("-"*5, "STATE\n", state, "-"*5)
            return state

        self.graph.add_node("PaperAgent", paper_parser)
        self.graph.add_node("ProjectBuilder", build_project)
        self.graph.add_node("CreateProjectProfile", manage_project_profile_creation)
        self.graph.add_node("ExampleFinder", example_finder)
        self.graph.add_node("LogAgent", log_result)

        self.graph.add_conditional_edges(
            "PaperAgent",
            lambda s: bool(s["repo_url"]),
            {
                True: "ProjectBuilder", # continue workflow
                False: "LogAgent" # stop early
            }
        )
        self.graph.add_edge("ProjectBuilder", "CreateProjectProfile")
        self.graph.add_edge("CreateProjectProfile", "ExampleFinder")
        self.graph.add_edge("ExampleFinder", "LogAgent")

        self.graph.set_entry_point("PaperAgent")
        self.graph.set_finish_point("LogAgent")

    def run(self, pdf_path: str):
        state = self.compiled_graph.invoke({"pdf_path": pdf_path})
        return {
            k: v for k, v in state.items()
            if k not in ("project", "error_handler")
        }
