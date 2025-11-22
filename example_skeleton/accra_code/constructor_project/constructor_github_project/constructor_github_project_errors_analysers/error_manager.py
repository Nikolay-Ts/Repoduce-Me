import json
import re
import subprocess
from constructor_adapter import StatefulConstructorAdapter


CONTEXT_PROMPT = """
You are an expert in software engineering, you have a deep understanding of design patterns and python language. You have worked in several big projects and know the best practices for coding in a clean, efficient and reliable way. 
I am working on a project, called ACCRa, which automatically: 
1. given an url of a scientific paper it download it
2. the paper is parsed in search of a github repository
3. clones a repository of a github project related to the scientific article
4. creates a virtual environment associated to that project which could use every python interpreter (ACCRa has its own virtual environment with python 3.12) 
5. all the packages needed in the project get installed in the venv created 
6. the code's project is analyzed by four classes: GitHubProjectParallelismAnalyserStatic, GitHubProjectNetworkAnalyserStatic, GitHubProjectMemoryAnalyserStatic, GitHubProjectLoadAnalyserStatic.

The structure of the ACCRa project is:
    - .venv (directory)
    - accra_code  (directory)
    - ImportedProjects  (directory)
    - accra_main.py
    - Other files such as requirements.txt, setup.py, setupEnvironment.zsh

In ImportedProjects there are subdirectories named “project_[project_name]” which contains the .venv-py[python_version] directory and the [project_name] cloned repository. For example, in ImportedProjects may be present the directory “project_fastapi” which contains “.venv-py312” and “fastapi”, related to the repository https://github.com/fastapi/fastapi."

You will be implied to classify and provide suggestion on how to solve the errors that we could face. 
"""

class ErrorManager():
    """
    Analyze errors, determine the root cause, and trigger remediation actions with the use of AI
    """

    def __init__(self):
        self.ai_model = StatefulConstructorAdapter()
        self.error_classified = dict()
        self.error_caught     = []

    def define_error_prompt(self, cmd, error: str):
        """
        Defines the prompt for classifying the error and suggesting a command for fixing it, giving the command and error
        """
        return CONTEXT_PROMPT + f"""
        {f"During the execution of the following command: {cmd}" if cmd else "During the execution of a command which you could understand from the context"}
        We got the following error from the stderr: {error}
        
        I want you to classify the error and provide a brief description of it that will be used for updating the python dictionary 'error_classified'.
        The structure of the 'error_classified' dictionary should have a key which represents the type of error and as value the brief description of it. 
        For example, considering the failed installation of the package grpc:
        {{ "grpc_failed_installation" : "the attempt to install the package grpc failed because the official installation suggest to use 'pip install grpcio' instead of 'pip install grpc'." }}
        {f"Until now, the 'error_classified' has the following elements: {self.error_classified}" if self.error_classified else "Until now, the 'error_classified' is empty"}
        
        The output I want from you is:
        1. The string "*** {{"name_classified_error": "description of the error"}} ***", use 3 stars symbols (*) to express the start and the end of the json object for an easier parsing. Enclose the key and the value in double quotes.
        2. The string "@@@ XXX @@@" where XXX is YES or NO, if the error could not be resolved by a command launched through the terminal do not suggest a single line command. Use 3 at sign (@) to contain the answer. 
        3. If in the previous string you inserted "YES", suggest a single line command which is likely to resolve the error. If more commands are required, use the semicolon operator (;) to run multiple commands on a single line. Put it inside 3 plus symbols (+) for an easier parsing. For example: +++ path_to_python_interpreter -m pip install grpcio +++. If in the previous string you inserted "NO", do not insert the +++ answer +++   
        """

    @staticmethod
    def parse_llm_answer(llm_response):
        """
        Parse the llm output to extract the *** {"[name_classified_error]": "[description of the error]"} *** for
        updating the error_classified dict and the +++ command +++ to fix resolve the error
        """
        error_pattern = r"\*\*\*\s*(\{.*?\})\s*\*\*\*"
        suggest_need_pattern = r"\@\@\@\s*(\{.*?\})\s*\@\@\@"
        command_pattern = r"\+\+\+\s*(.*?)\s*\+\+\+"

        # Find the error classified
        error_match = re.search(error_pattern, llm_response, re.DOTALL)
        error_dict = {}
        if error_match:
            try:
                tmp = json.loads(error_match.group(1).strip())
                if isinstance(tmp, dict):
                    print(f"the model classified the error as: {tmp}")
                    error_dict = tmp
                else:
                    print("parsed JSON is not a dictionary.")
            except json.JSONDecodeError as e:
                print(f"failed to parse error classification JSON: {str(e)}")
        else: 
            print("could not find the error classified by the model")

        suggestion_match = re.search(suggest_need_pattern, llm_response, re.DOTALL)
        suggested_command = None
    
        if suggestion_match and suggestion_match.group(1).strip().lower() == "yes":
            command_match = re.search(command_pattern, llm_response, re.DOTALL)
            if command_match:
                suggested_command = command_match.group(1).strip()
            else:
                print("could not find the suggested command in the LLM response")
        else:
            print("Could not find if the command is needed")
        return error_dict, suggested_command

    def handle_error(self, error: Exception, cmd = None):
        """
        Given a cmd and an error, enquiry the ai model available for classifying the error and suggesting a fix.
        The dictionary error_classified gets updated.
        The command suggested is run in the shell if and only if the user agrees to.
        """
        self.error_caught.append(error)
        result = self.ai_model.query(self.define_error_prompt(cmd, str(error)))
        new_error, suggestion = self.parse_llm_answer(result)
        self.error_classified.update(new_error)
        print("AI didn't recommended any commands" if suggestion is None else f"AI command proposal: {suggestion}")
        if suggestion:
            tmp = input(f"Do you want to run the command: \"{suggestion}\" ? Type Y or N\n")
            if tmp.lower() == "y":
                self.run_fix(suggestion)
            else:
                print("command not executed")

    @staticmethod
    def run_fix(command: str) -> bool:
        """Utility to run shell commands"""
        is_suggestion_successfully = False
        print(f"[Shell] Executing: {command}")
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            print(result.stdout)
            is_suggestion_successfully = True
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"error in the execution of {command}") from e

        return is_suggestion_successfully

