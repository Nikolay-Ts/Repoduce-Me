import re
from accra_code.constructor_project.constructor_paper_analyser.paper_analyser_pdf import PaperAnalyserPDF
import os
import tempfile
from constructor_adapter import StatefulConstructorAdapter

MAX_ATTEMPT = 3

class ConstructorPaperAgentLC:
    """
    Agent to extract GitHub URLs from a PDF paper.
    """
    @staticmethod
    def get_local_textual_file(pdf_path: str) -> str:
        # If it's a URL, generate a temp filename for the txt output
        if pdf_path.startswith("http://") or pdf_path.startswith("https://") or pdf_path.startswith("ftp://"):
            # Or you can use NamedTemporaryFile for safety if you want it auto-deleted
            # with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            #     return tmp.name
            txt_name = os.path.basename(pdf_path).replace(".pdf", ".txt")
            return os.path.join(tempfile.gettempdir(), txt_name)
        # Otherwise, normal local PDF path
        return pdf_path.replace(".pdf", ".txt")

    @staticmethod
    def define_prompt(name_paper_uploaded, list_github_urls) -> str:
        """Returns the prompt for url extraction adapted on name_paper_uploaded and list_github_urls"""
        if not name_paper_uploaded or not list_github_urls:
            raise RuntimeError("parameters name_paper_uploaded or list_github_urls are missing")
        return f"""
                You are an expert in software engineering.
                You are provided with a list of GitHub URLs extracted from the research paper uploaded as '{name_paper_uploaded}'.
                The list of URLs is: {list_github_urls}
                Your task is to choose the single URL that most likely corresponds to the main code repository of the project discussed in the paper.
                Guidelines:
                - The correct URL is typically the one hosting the source code, not documentation, forks, or unrelated tools.
                - Use any context from the paper to make your decision.
                - Usually is https://github.com/[name_author]/[name_project]
                IMPORTANT:
                Your answer must contain the the following strict format: "url: [actual_url]"
                [actual_url] must be one of the URLs from the provided list.
                Do not include any other explanation, text, formatting, or backticks.
                If no suitable repository is found in the list, return: "url: None"
                """

    @staticmethod
    def get_stateful_adapter_by_model_id(id_model:str = None):
        """Return a stateful adapter between those available. If id_model is provided and is present, it will be used,
        otherwise the stateful adapter will use the first model available"""
        adapter_stateful = StatefulConstructorAdapter()
        available_llms_stateful = adapter_stateful.get_available_llms()
        if len(available_llms_stateful) == 0:
            raise RuntimeError("No LLMs Stateful available")
        model2use = next((model for model in available_llms_stateful if model["id"] == id_model), available_llms_stateful[0]) # first model available as default
        return StatefulConstructorAdapter(llm_alias=model2use["alias"])

    @staticmethod
    def parse_ai_answer(answer, github_urls):
        pattern = r"['\"(]?(https?://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+|github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)['\".,;:)]?"
        url2use = re.search(pattern, answer, re.IGNORECASE)
        if url2use:
            actual_url = url2use.group(1)
            if not any(actual_url in url for url in github_urls):
                raise RuntimeError(f"The url found {actual_url} is not present in the urls extracted in the paper:\n{github_urls}")
        else:
            raise RuntimeError(f"no url found by the LLM")  # noqa: F541
        return actual_url

    def get_url_by_llm(self, path_actual_paper: str, github_urls: list[str]):
        """
            Ask an LLM to select the proper url of the project related to the paper
            uploaded from a list. If the chosen url is in the original list then
            it will be returned, otherwise raise an error
        """
        model_stateful = self.get_stateful_adapter_by_model_id("gpt-4.1-mini") # insert id_model for a specific model, otherwise will get the first one
        # model_stateful.delete_all_documents() # clean the memory
        model_stateful.add_document(path_actual_paper)
        attempt = 1
        url2use = None
        while attempt < MAX_ATTEMPT+1:
            try:
                print(f"model interrogation, attempt n. {attempt}")
                response = model_stateful.query(self.define_prompt(os.path.basename(path_actual_paper), github_urls))
                print(f"AI answer: {response}")
                url2use = self.parse_ai_answer(response.strip(), github_urls)
                break
            except Exception as e:
                print(f"error during model interrogation: {e}")
            attempt = attempt + 1
        if url2use is None:
            raise RuntimeError(f"cannot extract the url from the paper")  # noqa: F541

        if os.path.exists(path_actual_paper):
            os.remove(path_actual_paper)

        return url2use


    def run(self, pdf_path: str, user_interaction):
        textual_file = self.get_local_textual_file(pdf_path)
        paper_analyser = PaperAnalyserPDF(paper=pdf_path, textual_file=textual_file)
        github_urls = list(paper_analyser.extract_github_references())

        if not github_urls:
            print(f"No GitHub URLs found in {pdf_path}")
            return {"repo_url": None}

        print(f"repositories found in the paper:\n{github_urls}")
        url2use = self.user_url_selection(github_urls) if user_interaction \
            else self.get_url_by_llm(paper_analyser.actual_paper, github_urls)

        return {"repo_url": url2use}

    @staticmethod
    def user_url_selection(urls):
        """Prints the github repositories found and waits for the selection from user"""
        print("the github repository found are: ")
        for i, choice in enumerate(urls, 1):
            print(f"{i}. {choice}")

        selected = False
        url2use = ""
        while not selected:
            raw = input(f"Select an option (insert a number between 1 and {len(urls)}: ").strip()
            try:
                idx = int(raw) - 1
            except ValueError:
                print(f"“{raw}” is not a number, please try again.")
                continue
            if 0 <= idx < len(urls):
                url2use = urls[idx]
                selected = True
            else:
                print(f"please enter a number between 1 and {len(urls)}.")

        return url2use
