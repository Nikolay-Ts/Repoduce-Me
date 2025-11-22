import shutil
import tempfile
import urllib.request
from .paper_analyser import PaperAnalyser
import pymupdf
import re
from pdfminer.high_level import extract_text as extract_pdf_text
import pdfplumber
import os
from PIL import Image
from io import BytesIO



class PaperAnalyserPDF(PaperAnalyser):

    def __init__(self, paper:str, textual_file:str):
        super().__init__(paper,textual_file)
        # the following two are to move to the superclass once implemented also in medium
        self.paper_tables = self.extract_tables(textual_file)
        self.extract_images(textual_file)


    def extract_text(self, textual_file: str = None):
        # Helper: check if string is a URL
        def is_url(path):
            return path.lower().startswith(("http://", "https://", "ftp://"))

        pdf_path = self.paper

        temp_file_path = None
        try:
            # Download if URL
            if pdf_path and is_url(pdf_path):
                # Add https:// if missing
                if not pdf_path.lower().startswith(("http://", "https://", "ftp://")):
                    pdf_url = "https://" + pdf_path.lstrip("/")
                else:
                    pdf_url = pdf_path
                # Download to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpf:
                    print(f"Downloading PDF from {pdf_url} to {tmpf.name}")
                    with urllib.request.urlopen(pdf_url) as response, open(tmpf.name, 'wb') as out_file:
                        shutil.copyfileobj(response, out_file)
                    temp_file_path = tmpf.name
                pdf_path = temp_file_path
                self.actual_paper = pdf_path
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from the supplied name ({textual_file}): {e}")

        if not pdf_path or not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file '{pdf_path}' not found.")

        try:
            # Extract plain text with pdfminer
            text = extract_pdf_text(pdf_path)

            if textual_file:
                with open(textual_file, 'w', encoding='utf-8') as f:
                    f.write(text)

            return text

        except Exception as e:
            raise RuntimeError(f"Failed to extract text from PDF: {e}")

    def extract_tables(self, textual_file: str = None):
        print(f"Extracting tables from PDF: {self.actual_paper}")
        if not self.actual_paper or not os.path.exists(self.actual_paper):
            raise FileNotFoundError(f"PDF file '{self.actual_paper}' not found.")

        try:
            with pdfplumber.open(self.actual_paper) as pdf:
                textual_tables = ""
                for i, page in enumerate(pdf.pages):
                    print(f"Extracting tables in page {i} from PDF: {self.actual_paper}")
                    tables = page.extract_tables()
                    for j, table in enumerate(tables):
                        print(f"Found table in page {i+1} from PDF: {self.actual_paper}")
                        if table:
                            textual_tables += f"\n\n--- Table from page {i+1}, table {j+1} ---\n"
                            for row in table:
                                # Format each row nicely
                                row_line = " | ".join(cell.strip() if cell else "" for cell in row)
                                textual_tables += row_line + "\n"

            if textual_file:
                tables_file = textual_file+".tables.txt"
                with open(tables_file, 'w', encoding='utf-8') as f:
                    f.write(textual_tables)

            return textual_tables

        except Exception as e:
            raise RuntimeError(f"Failed to extract tables from PDF: {e}")

    def extract_images(self, textual_file: str = None):
        if not self.actual_paper or not os.path.exists(self.actual_paper):
            raise FileNotFoundError(f"PDF file '{self.actual_paper}' not found.")

        try:
            # Extract images
            with pdfplumber.open(self.actual_paper) as pdf:
                image_index = 1
                for i, page in enumerate(pdf.pages):
                    for image in page.images:
                        # Get image bytes
                        print(f"Found image number {image} in page {i+1} from PDF: {self.actual_paper}")
                        x0, top, x1, bottom = image['x0'], image['top'], image['x1'], image['bottom']
                        cropped = page.within_bbox((x0, top, x1, bottom)).to_image(resolution=600)
                        img = cropped.original.convert("RGB")

                        # Convert to PIL Image and save
                        img_bytes = BytesIO()
                        img.save(img_bytes, format='PNG')
                        pil_img = Image.open(BytesIO(img_bytes.getvalue()))
                        # Save image file
                        if textual_file:
                            base = os.path.splitext(textual_file)[0]
                            img_path = f"{base}.images.{image_index}.png"
                            pil_img.save(img_path)
                            image_index += 1
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from PDF: {e}")

    def extract_urls(self):
        """
        Extract both clickable and plain-text URLs directly from the PDF using PyMuPDF.
        Handles:
        - URLs with http/https
        - URLs starting with www.
        - Bare domains like github.com/user/repo
        """
        urls = set()
        try:
            doc = pymupdf.open(self.actual_paper)

            for page in doc:
                # (1) Clickable links
                for link in page.get_links():
                    uri = link.get("uri", None)
                    if uri:
                        urls.add(uri.strip())

                # (2) Plaintext URLs (http/https/www./bare)
                raw_text = page.get_text()
                pattern = r'\b(?:https?://|www\.)?[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s)>\]]*)?'
                matches = re.findall(pattern, raw_text)
                for match in matches:
                    urls.add(match.strip().rstrip(".,);:!?\"'"))

            doc.close()
            return urls

        except Exception as e:
            raise RuntimeError(f"Failed to extract URLs from PDF: {e}")

    def extract_github_references(self):
        urls = self.extract_urls()
        self.github_references = {url for url in urls if 'github.com' in url.lower()}
        return self.github_references