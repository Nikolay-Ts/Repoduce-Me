from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .constructor_agents_lc.constructor_paper_agent_lc import ConstructorPaperAgentLC
from .constructor_agents_lc.constructor_repository_profiler_agent_lc import ConstructorRepositoryProfilerAgentLC
from .constructor_agents_lc.constructor_requirements_agent_lc import ConstructorRequirementsAgentLC
from .constructor_agents_lc.constructor_analysis_coordinator_agent_lc import ConstructorAnalysisCoordinatorAgentLC
from .constructor_agents_lc.constructor_size_analysis_agent_lc import ConstructorSizeAnalysisAgentLC
from .constructor_agents_lc.constructor_agents_analysers_lc.constructor_memory_analysis_agent_lc import ConstructorMemoryAnalysisAgentLC
from .constructor_agents_lc.constructor_agents_analysers_lc.constructor_network_analysis_agent_lc import ConstructorNetworkAnalysisAgentLC
from .constructor_agents_lc.constructor_agents_analysers_lc.constructor_load_analysis_agent_lc import ConstructorLoadAnalysisAgentLC
from .constructor_agents_lc.constructor_agents_analysers_lc.constructor_parallelism_analysis_agent_lc import ConstructorParallelismAnalysisAgentLC
from accra_code.constructor_project.constructor_github_project.constructor_github_project_errors_analysers.error_manager import \
    ErrorManager
from .constructor_langgraph_state import ConstructorLanggraphState


class ConstructorManagerLangGraph2:
    """
    Main orchestrator using LangGraph 2 for the Constructor project.
    Organizes the workflow into distinct nodes for:
    1. URL extraction from paper
    2. Technical requirements determination
    3. Multiple analysis types (size, memory, network, load, parallelism)
    """

    def __init__(self, user_interaction=False, *, repo_url=None, reuse_existing=False):
        self.user_interaction = user_interaction
        self.repo_url = repo_url
        self.reuse_existing = reuse_existing

        # Initialize agents
        self.paper_agent = ConstructorPaperAgentLC()
        self.repo_profiler_agent = ConstructorRepositoryProfilerAgentLC()
        self.requirements_agent = ConstructorRequirementsAgentLC()
        self.analysis_coordinator = ConstructorAnalysisCoordinatorAgentLC()
        self.size_agent = ConstructorSizeAnalysisAgentLC()
        self.memory_agent = ConstructorMemoryAnalysisAgentLC()
        self.network_agent = ConstructorNetworkAnalysisAgentLC()
        self.load_agent = ConstructorLoadAnalysisAgentLC()
        self.parallelism_agent = ConstructorParallelismAnalysisAgentLC()
        self.error_handler = ErrorManager()

        # Build the graph
        self.graph = self._build_graph()
        self.compiled_graph = self.graph.compile(checkpointer=MemorySaver())

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(ConstructorLanggraphState)

        # Add nodes
        workflow.add_node("extract_url", self._extract_url_node)
        workflow.add_node("determine_requirements", self._determine_requirements_node)
        workflow.add_node("profile_repository", self._profile_repository_node)
        workflow.add_node("analyze_size", self._analyze_size_node)
        workflow.add_node("analyze_memory", self._analyze_memory_node)
        workflow.add_node("analyze_network", self._analyze_network_node)
        workflow.add_node("analyze_load", self._analyze_load_node)
        workflow.add_node("analyze_parallelism", self._analyze_parallelism_node)
        workflow.add_node("aggregate_results", self._aggregate_results_node)
        workflow.add_node("log_results", self._log_results_node)

        # Set entry point
        workflow.set_entry_point("extract_url")

        # Define edges
        workflow.add_conditional_edges(
            "extract_url",
            self._should_continue_after_url_extraction,
            {
                "profile": "profile_repository",
                "end": "log_results"
            }
        )

        workflow.add_edge("profile_repository", "determine_requirements")

        workflow.add_conditional_edges(
            "determine_requirements",
            self._should_run_analyses,
            {
                "analyze": "analyze_size",
                "skip": "aggregate_results"
            }
        )

        # Analysis pipeline - run in sequence
        workflow.add_edge("analyze_size", "analyze_memory")
        workflow.add_edge("analyze_memory", "analyze_network")
        workflow.add_edge("analyze_network", "analyze_load")
        workflow.add_edge("analyze_load", "analyze_parallelism")
        workflow.add_edge("analyze_parallelism", "aggregate_results")

        workflow.add_edge("aggregate_results", "log_results")
        workflow.add_edge("log_results", END)

        return workflow

    # ==================== Node Functions ====================

    def _extract_url_node(self, state: ConstructorLanggraphState) -> dict:
        """Node 1: Extract GitHub URL from paper"""
        print("\n" + "=" * 50)
        print("NODE: Extract URL from Paper")
        print("=" * 50)

        if self.repo_url:
            print(f"Using provided repo URL: {self.repo_url}")
            return {"repo_url": self.repo_url, "errors": []}

        try:
            result = self.paper_agent.run(state["pdf_path"], self.user_interaction)
            print(f"Extracted repo URL: {result.get('repo_url')}")
            return {
                "repo_url": result.get("repo_url"),
                "github_urls": result.get("github_urls", []),
                "errors": []
            }
        except Exception as e:
            error_msg = f"Error extracting URL: {str(e)}"
            print(f"ERROR: {error_msg}")
            self.error_handler.handle_error(e)
            return {"repo_url": None, "errors": [error_msg]}

    def _profile_repository_node(self, state: ConstructorLanggraphState) -> dict:
        """Node 2: Profile the repository (clone, basic info)"""
        print("\n" + "=" * 50)
        print("NODE: Profile Repository")
        print("=" * 50)

        try:
            result = self.repo_profiler_agent.run(
                state["repo_url"],
                reuse_existing=self.reuse_existing
            )
            print(f"Repository profiled: {result.get('repo')}")
            return {
                "project_data": result.get("project_data"),
                "errors": []
            }
        except Exception as e:
            error_msg = f"Error profiling repository: {str(e)}"
            print(f"ERROR: {error_msg}")
            self.error_handler.handle_error(e)
            return {"project_data": None, "errors": [error_msg]}

    def _determine_requirements_node(self, state: ConstructorLanggraphState) -> dict:
        """Node 3: Determine technical requirements (packages, Python version)"""
        print("\n" + "=" * 50)
        print("NODE: Determine Technical Requirements")
        print("=" * 50)

        try:
            result = self.requirements_agent.run(state["project_data"])
            print(f"Found {len(result.get('required_packages', []))} required packages")
            print(f"Python versions: {result.get('python_versions', [])}")
            return {
                "required_packages": result.get("required_packages", []),
                "python_versions": result.get("python_versions", []),
                "errors": []
            }
        except Exception as e:
            error_msg = f"Error determining requirements: {str(e)}"
            print(f"ERROR: {error_msg}")
            self.error_handler.handle_error(e)
            return {
                "required_packages": [],
                "python_versions": [],
                "errors": [error_msg]
            }

    def _analyze_size_node(self, state: ConstructorLanggraphState) -> dict:
        """Node 4: Analyze project size"""
        print("\n" + "=" * 50)
        print("NODE: Analyze Size")
        print("=" * 50)

        try:
            result = self.size_agent.run(state["project_data"])
            print(f"Size analysis complete: {result.get('total_size_mb', 0)} MB")
            return {"size_analysis": result, "errors": []}
        except Exception as e:
            error_msg = f"Error in size analysis: {str(e)}"
            print(f"ERROR: {error_msg}")
            self.error_handler.handle_error(e)
            return {"size_analysis": None, "errors": [error_msg]}

    def _analyze_memory_node(self, state: ConstructorLanggraphState) -> dict:
        """Node 5: Analyze memory requirements"""
        print("\n" + "=" * 50)
        print("NODE: Analyze Memory")
        print("=" * 50)

        try:
            result = self.memory_agent.run(
                state["project_data"],
                state["required_packages"]
            )
            print("Memory analysis complete")
            return {"memory_analysis": result, "errors": []}
        except Exception as e:
            error_msg = f"Error in memory analysis: {str(e)}"
            print(f"ERROR: {error_msg}")
            self.error_handler.handle_error(e)
            return {"memory_analysis": None, "errors": [error_msg]}

    def _analyze_network_node(self, state: ConstructorLanggraphState) -> dict:
        """Node 6: Analyze network requirements"""
        print("\n" + "=" * 50)
        print("NODE: Analyze Network")
        print("=" * 50)

        try:
            result = self.network_agent.run(state["project_data"])
            print("Network analysis complete")
            return {"network_analysis": result, "errors": []}
        except Exception as e:
            error_msg = f"Error in network analysis: {str(e)}"
            print(f"ERROR: {error_msg}")
            self.error_handler.handle_error(e)
            return {"network_analysis": None, "errors": [error_msg]}

    def _analyze_load_node(self, state: ConstructorLanggraphState) -> dict:
        """Node 7: Analyze CPU/GPU load"""
        print("\n" + "=" * 50)
        print("NODE: Analyze Load")
        print("=" * 50)

        try:
            result = self.load_agent.run(
                state["project_data"],
                state["required_packages"]
            )
            print("Load analysis complete")
            return {"load_analysis": result, "errors": []}
        except Exception as e:
            error_msg = f"Error in load analysis: {str(e)}"
            print(f"ERROR: {error_msg}")
            self.error_handler.handle_error(e)
            return {"load_analysis": None, "errors": [error_msg]}

    def _analyze_parallelism_node(self, state: ConstructorLanggraphState) -> dict:
        """Node 8: Analyze parallelism (threading/multiprocessing)"""
        print("\n" + "=" * 50)
        print("NODE: Analyze Parallelism")
        print("=" * 50)

        try:
            result = self.parallelism_agent.run(
                state["project_data"],
                state["required_packages"]
            )
            print("Parallelism analysis complete")
            return {
                "parallelism_analysis": result,
                "analysis_complete": True,
                "errors": []
            }
        except Exception as e:
            error_msg = f"Error in parallelism analysis: {str(e)}"
            print(f"ERROR: {error_msg}")
            self.error_handler.handle_error(e)
            return {
                "parallelism_analysis": None,
                "analysis_complete": True,
                "errors": [error_msg]
            }

    def _aggregate_results_node(self, state: ConstructorLanggraphState) -> dict:
        """Node 9: Aggregate all analysis results"""
        print("\n" + "=" * 50)
        print("NODE: Aggregate Results")
        print("=" * 50)

        try:
            dimensions = self.analysis_coordinator.aggregate_dimensions(
                size=state.get("size_analysis"),
                memory=state.get("memory_analysis"),
                network=state.get("network_analysis"),
                load=state.get("load_analysis"),
                parallelism=state.get("parallelism_analysis")
            )

            result = {
                "repo": state.get("repo_url"),
                "project_data": state.get("project_data"),
                "dimensions": dimensions,
                "analyses": {
                    "size": state.get("size_analysis"),
                    "memory": state.get("memory_analysis"),
                    "network": state.get("network_analysis"),
                    "load": state.get("load_analysis"),
                    "parallelism": state.get("parallelism_analysis")
                }
            }

            print(f"Aggregated dimensions: {dimensions}")
            return {"dimensions": dimensions, "result": result, "errors": []}
        except Exception as e:
            error_msg = f"Error aggregating results: {str(e)}"
            print(f"ERROR: {error_msg}")
            return {"dimensions": None, "result": None, "errors": [error_msg]}

    def _log_results_node(self, state: ConstructorLanggraphState) -> dict:
        """Node 10: Log final results"""
        print("\n" + "=" * 50)
        print("NODE: Log Results")
        print("=" * 50)
        print("Final State Summary:")
        print(f"  Repo URL: {state.get('repo_url')}")
        print(f"  Dimensions: {state.get('dimensions')}")
        print(f"  Errors: {len(state.get('errors', []))}")
        if state.get('errors'):
            print(f"  Error details: {state['errors']}")
        print("=" * 50 + "\n")
        return {}

    # ==================== Conditional Edge Functions ====================

    def _should_continue_after_url_extraction(self, state: ConstructorLanggraphState) -> Literal["profile", "end"]:
        """Decide whether to continue after URL extraction"""
        if state.get("repo_url"):
            return "profile"
        return "end"

    def _should_run_analyses(self, state: ConstructorLanggraphState) -> Literal["analyze", "skip"]:
        """Decide whether to run analyses"""
        if state.get("project_data") and state.get("required_packages") is not None:
            return "analyze"
        return "skip"

    # ==================== Public API ====================

    def run(self, pdf_path: str, config: dict = None):
        """
        Run the complete workflow

        Args:
            pdf_path: Path to the PDF paper
            config: Optional configuration for the graph execution

        Returns:
            Final state with all results
        """
        initial_state = {
            "pdf_path": pdf_path,
            "repo_url": self.repo_url,
            "user_interaction": self.user_interaction,
            "reuse_existing": self.reuse_existing,
            "github_urls": [],
            "project_data": None,
            "required_packages": [],
            "python_versions": [],
            "size_analysis": None,
            "memory_analysis": None,
            "network_analysis": None,
            "load_analysis": None,
            "parallelism_analysis": None,
            "dimensions": None,
            "result": None,
            "errors": [],
            "analysis_complete": False
        }

        if config is None:
            config = {"configurable": {"thread_id": "1"}}

        result_state = self.compiled_graph.invoke(initial_state, config)
        return result_state

    def stream(self, pdf_path: str, config: dict = None):
        """
        Stream the workflow execution for real-time updates

        Args:
            pdf_path: Path to the PDF paper
            config: Optional configuration for the graph execution

        Yields:
            State updates as the workflow progresses
        """
        initial_state = {
            "pdf_path": pdf_path,
            "repo_url": self.repo_url,
            "user_interaction": self.user_interaction,
            "reuse_existing": self.reuse_existing,
            "github_urls": [],
            "project_data": None,
            "required_packages": [],
            "python_versions": [],
            "size_analysis": None,
            "memory_analysis": None,
            "network_analysis": None,
            "load_analysis": None,
            "parallelism_analysis": None,
            "dimensions": None,
            "result": None,
            "errors": [],
            "analysis_complete": False
        }

        if config is None:
            config = {"configurable": {"thread_id": "1"}}

        for event in self.compiled_graph.stream(initial_state, config):
            yield event

