import operator
from typing import TypedDict, Annotated


class ConstructorLanggraphState(TypedDict):
    """State schema for the constructor workflow"""
    # Input
    pdf_path: str
    repo_url: str | None
    user_interaction: bool
    reuse_existing: bool

    # Paper extraction results
    github_urls: list[str]

    # Repository profiling results
    project_data: dict | None

    # Technical requirements
    required_packages: list[str]
    python_versions: list[str]

    # Analysis results
    size_analysis: dict | None
    memory_analysis: dict | None
    network_analysis: dict | None
    load_analysis: dict | None
    parallelism_analysis: dict | None

    # Final results
    dimensions: dict | None
    result: dict | None

    # Error tracking
    errors: Annotated[list[str], operator.add]

    # Control flow
    analysis_complete: bool
