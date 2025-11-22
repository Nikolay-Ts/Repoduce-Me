from abc import ABC, abstractmethod
import logging


class Project(ABC):
    """
    Base class for adapting external platforms to the Constructor Research Platform.
    Provides a unified interface for interacting with external projects.
    """

    def __init__(self, project_url: str = None, project_name: str = None, import_directory: str = None, accra_timeout: int = None):
        """
        Initialize the ExternalProject with a accra_code URL.

        :param project_url: URL of the external accra_code (e.g., GitHub repo, Amazon resource).
        """
        print("ExternalProject___init__")
        self.project_url = project_url
        self.project_name = project_name
        self.project_data = None  # Will hold parsed accra_code-specific data
        self.project_dimension_prediction = None   # Will hold the end prediction of the dimensions
        self.import_directory = import_directory
        self.accra_timeout = accra_timeout
        logging.info(f"Initialized ExternalProject for {self.project_url}")

    @abstractmethod
    def fetch_project_data(self):
        """
        Fetch accra_code-specific data from the external platform.
        Must be implemented by subclasses.
        """
        pass

    @abstractmethod
    def predict_project_dimension(self):
        """
        Compute from project_data the specific dimension prediction.
        The dimensions is store in project_dimension_prediction.
        """
        pass


    @abstractmethod
    def adapt_to_constructor(self):
        """
        Convert accra_code-specific data to a format suitable for Constructor Platform.
        Must be implemented by subclasses.
        """
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(project_url={self.project_url})"

    def export_project_data(self, filename :str = None):
        pass
