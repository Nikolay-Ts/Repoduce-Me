import re
import sys
from pathlib import Path

from PyPDF2 import PdfReader

class PaperParser(): 
    'A parser to extract github links from the pdf provided'
    def __init__(self, paper_filepath: str):
        self.paper_filepath = paper_filepath

    def extract_github_link(self, paper_filepath: str = '') -> list[str]:
        'if no links are found the array will be empty'
        if paper_filepath != '':
            self.paper_filepath = paper_filepath

        pdf_path = Path(self.paper_filepath)

        if not pdf_path.exists():
            raise FileNotFoundError(f"File not found: {pdf_path}")

        reader = PdfReader(pdf_path)

        github_links: list[str] = []

        pattern = re.compile(r"https?://github\.com[^\s)\"'>]+")

        for page in reader.pages:
            text = page.extract_text() or ""
            matches = pattern.findall(text)
            github_links.extend(matches)

        return github_links 
