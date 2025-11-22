from src.paper_extracter import PaperParser

meow = PaperParser("../paper1.pdf")
print(meow.extract_github_link())

meow = PaperParser("../paper2.pdf")
print(meow.extract_github_link())