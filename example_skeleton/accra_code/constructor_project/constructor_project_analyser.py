import sys
from abc import ABC, abstractmethod
import os
from contextlib import contextmanager

from accra_code.constructor_project.constructor_project import Project


class ProjectAnalyser(ABC):
    def __init__(self, project: Project):
        self.project = project

    def finalize(self):
        """Override in subclasses if any cleanup is needed."""
        pass

    @abstractmethod
    def analyze(self):
        """Analyze generic behavior of the given GitHub project."""
        """Stores the data in project_data."""
        pass

    @contextmanager
    def change_dir(self, path_new_dir):
        """ Temporarily change the current working directory. """
        old_dir = os.getcwd()
        try:
            print(f"changing working directory from {old_dir} to {path_new_dir}", file=sys.stderr)
            os.chdir(path_new_dir)
            yield
        finally:
            print(f"restore working directory to {old_dir}", file=sys.stderr)
            os.chdir(old_dir)

