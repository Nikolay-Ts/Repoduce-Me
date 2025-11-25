import re
from pathlib import Path
from typing import List
import json

from PyPDF2 import PdfReader
from constructor_model import ConstructorModel


class PaperParser:
    """A parser to extract GitHub links from the pdf provided"""

    def __init__(self, paper_filepath: str = ""):
        self.paper_filepath = paper_filepath
        self.llm = ConstructorModel(model="gpt-5.1")


    def _extract_paper_title(self, reader: PdfReader) -> str:
        """Return the first non-empty line of the first page."""
        if not reader.pages:
            return ""

        first_page = reader.pages[0]
        text = first_page.extract_text() or ""

        for line in text.splitlines():
            line = line.strip()
            if line:
                return line

        return ""


    def _search_web(self, paper_name: str) -> str:
        """
        Query LLM to search for GitHub repo based on paper title.
        Returns raw LLM response (should be JSON-like).
        """
        prompt = (
            "You are a very good researcher. "
            f"Based on this paper name '{paper_name}', search GitHub "
            "for a repository with a similar name. The output should be as follows "
            "{ github_link: [actual_github_link] }"
        )

        response = self.llm.invoke(prompt)
        return getattr(response, "content", str(response))

    def extract_github_link(self, paper_filepath: str = "") -> List[str]:
        """
        Return a list of GitHub links. If no links are found the list is empty.
        
        IMPORTANT: Always returns a List[str], never a single string.
        """
        if paper_filepath:
            self.paper_filepath = paper_filepath

        pdf_path = Path(self.paper_filepath)

        if not pdf_path.exists():
            raise FileNotFoundError(f"File not found: {pdf_path}")

        reader = PdfReader(pdf_path)

        github_links: List[str] = []
        
        # Combine all lines from all pages
        all_lines = []
        for page in reader.pages:
            all_lines.extend((page.extract_text() or "").splitlines())

        # Repair broken URLs across lines
        repaired_lines = []
        i = 0
        while i < len(all_lines):
            current_line = all_lines[i].strip()
            
            if (current_line.endswith('/') or current_line.endswith('-')) and i + 1 < len(all_lines):
                next_line = all_lines[i+1].strip()
                joined_line = current_line + next_line
                repaired_lines.append(joined_line)
                i += 2  
            else:
                repaired_lines.append(current_line)
                i += 1

        continuous_text = " ".join(repaired_lines)
        
        # Extract GitHub URLs
        pattern = re.compile(r"https?://github\.com/[^\s)\"'>]+")
        matches = pattern.findall(continuous_text)

        for m in matches:
            clean = m.rstrip('.,);:\'"')
            # Sanitize: remove /tree/, /blob/, /issues/, etc. to get root repo
            clean = re.sub(r'/(tree|blob|issues|pull|wiki|releases|commit)/.*$', '', clean)
            github_links.append(clean)
        
        # Deduplicate while preserving order
        seen = set()
        unique_links: List[str] = []
        for link in github_links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)

        # If no links found in PDF, try LLM search
        if not unique_links:
            paper_title = self._extract_paper_title(reader)
            if paper_title:
                try:
                    llm_response = self._search_web(paper_title)
                    # Try to parse JSON response
                    paper_result = json.loads(llm_response)
                    
                    # Handle various response formats
                    if isinstance(paper_result, dict):
                        link = paper_result.get('github_link')
                        if link and isinstance(link, str):
                            unique_links.append(link)
                        elif link and isinstance(link, list) and link:
                            unique_links.extend([l for l in link if isinstance(l, str)])
                    
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    print(f"[WARNING] Could not parse LLM response for GitHub link: {e}")

        return unique_links