import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "src"))
from paper_extracter import PaperParser


meow = PaperParser(str(ROOT / "test/paper1.pdf"))
print(meow.extract_github_link())

meow = PaperParser(str(ROOT / "test/paper2.pdf"))
print(meow.extract_github_link())

print(meow.extract_github_link(str(ROOT / "test/paper4.pdf")))