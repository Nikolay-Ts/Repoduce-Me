import re
import sys
from pathlib import Path

from PyPDF2 import PdfReader


class PaperParser(): 
    def __init__(self, paper_filepath: str):
        self.paper_filepath = paper_filepath

    def extract_github_link(self) -> str:
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
