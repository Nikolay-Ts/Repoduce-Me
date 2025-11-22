import re
from abc import ABC, abstractmethod

class PaperAnalyser(ABC):

    def __init__(self, paper:str=None, resulting_file:str=None):
        self.paper = paper
        self.actual_paper = self.paper
        self.resulting_file = resulting_file
        self.paper_text = self.extract_text(self.resulting_file)
        self.github_references = set()
        self.paper_tables = None


    @abstractmethod
    def extract_text(self, resulting_file:str = None):
        pass

    def extract_github_references(self):
        """
        Extract all GitHub repository URLs from the paper text and store them in self.github_references.
        """
        if not self.paper_text:
            print("No paper text provided")
            return

        print("Extracting GitHub References from paper text")
        print(self.paper_text)
        # Regex to match GitHub repository URLs (https://github.com/owner/repo)
        github_url_pattern = r'github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+'

        matches = re.findall(github_url_pattern, self.paper_text)
        for match in matches:
            print("found GitHub References: " + match)

        self.github_references = set(matches)