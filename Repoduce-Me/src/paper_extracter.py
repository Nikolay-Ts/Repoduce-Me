import re
from pathlib import Path
from typing import List

from PyPDF2 import PdfReader


class PaperParser:
    """A parser to extract GitHub links from the pdf provided"""

    def __init__(self, paper_filepath: str):
        self.paper_filepath = paper_filepath

    def extract_github_link(self, paper_filepath: str = '') -> List[str]:
        """Return a list of GitHub links. If no links are found the list is empty."""
        if paper_filepath:
            self.paper_filepath = paper_filepath

        pdf_path = Path(self.paper_filepath)

        if not pdf_path.exists():
            raise FileNotFoundError(f"File not found: {pdf_path}")

        reader = PdfReader(pdf_path)

        github_links: List[str] = []

        # Match GitHub URLs, but we will clean trailing punctuation afterward
        pattern = re.compile(r"https?://github\.com/[^\s)\"'>]+")

        for page in reader.pages:
            text = page.extract_text() or ""
            matches = pattern.findall(text)

            for m in matches:
                # Strip common trailing punctuation from the *end* of the URL
                clean = m.rstrip('.,);:\'"')
                github_links.append(clean)

        # Optional: deduplicate while preserving order
        seen = set()
        unique_links = []
        for link in github_links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)

        return unique_links