from typing import List, Optional, Dict
import subprocess
import os
import sys
from enum import StrEnum
import time
import traceback
import argparse
import gc

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from accra_code.constructor_project.constructor_manager.constructor_agents_lc.constructor_paper_agent_lc import ConstructorPaperAgentLC
from accra_code.constructor_project.constructor_github_project.github_project import GitHubProject


from accra_code.constructor_project.constructor_github_project.constructor_github_project_profiles_analysers.github_project_network_analyser_static import GitHubProjectNetworkAnalyserStatic
from accra_code.constructor_project.constructor_github_project.constructor_github_project_profiles_analysers.github_project_memory_analyser_static import GitHubProjectMemoryAnalyserStatic
from accra_code.constructor_project.constructor_github_project.constructor_github_project_profiles_analysers.github_project_load_analyser_static import GitHubProjectLoadAnalyserStatic
from accra_code.constructor_project.constructor_github_project.constructor_github_project_profiles_analysers.github_project_example_finder import GithubProjectExampleFinder
from accra_code.constructor_project.constructor_paper_analyser.paper_analyser_pdf import PaperAnalyserPDF

all_analysers = {
    "network": ("Network analyser", GitHubProjectNetworkAnalyserStatic),
    "memory" : ("Memory analyser",  GitHubProjectMemoryAnalyserStatic),
    "load"   : ("Load analyser",    GitHubProjectLoadAnalyserStatic),
    "example": ("Example finder",   GithubProjectExampleFinder)
}

class Flags:
    def __init__(self):
        parser = argparse.ArgumentParser(
            description="Test ACCRa capabilities"
        )

        parser.add_argument(
            "--begin",
            help="Test from this project",
            type=int,
            action="store",
            nargs="?",
            default=0
        )
        parser.add_argument(
            "--end",
            help="Test up to this project",
            type=int,   
            action="store",
            nargs="?",
            default=None
        )
        parser.add_argument(
            "--timeout",
            help="ACCRA timeout",
            type=int,
            nargs="?",
            default=int(os.getenv("ACCRA_TIMEOUT", 60))
        )
        parser.add_argument(
            "--no-rm",
            action="store_true",
            help="Remove project directory after it has been tested",
        )
        parser.add_argument(
            "--analysers",
            nargs="+",
            default=["all"],
            choices=list(all_analysers.keys()) + ["all"],
            help="List of analysers to run. Default is \"all\".",
        )
        
        args = parser.parse_args()

        self.begin         : int       = args.begin
        self.end           : int       = args.end
        self.timeout       : int       = args.timeout
        self.no_rm         : bool      = args.no_rm
        self.reuse_existing: bool      = args.no_rm
        self.analysers     : List[str] = args.analysers
flags = Flags() # Global flags

class ProjectStatus(StrEnum):
    NOT_SET      = "Not set"
    OK           = "Ok"
    ERROR        = "Error"
    WRONG_GIVEN  = "Given URL, if any, outside of found set"
    NO_REPOS     = "No repositories found in paper"
    NO_EXEC      = "No Url given to run on Accra"
    TEST_URL_AI  = "Test URL given by AI"
    TEST_URL_SRC = "Test URL taken from source"
    
    NO_PARA_TH   = "The parallelism test was inconclusive in the threading part "
    NO_PARA_MULT = "The parallelism test was inconclusive in the multiprocessing part"
    NO_NET       = "The network test was inconclusive"
    NO_MEM       = "The memory test was inconclusive"
    NO_LOAD      = "The load test was inconclusive"
    NO_EXAMPLE   = "No example found"

ErrorState : List[ProjectStatus]
ErrorState = [ProjectStatus.ERROR, ProjectStatus.NO_EXEC, ProjectStatus.NO_REPOS]

def State_Check(func):
    def wrapper(self, *args, **kwargs):
        if self.status in ErrorState:
            res = None
        else:
            res = func(self, *args, **kwargs)
        return res
    return wrapper

class Project:
    @staticmethod
    def __selected_analysers() -> list[tuple[str, type]]:
        if "all" in flags.analysers:
            return list(all_analysers.values())
        result: list[tuple[str, type]] = []
        for analyser in flags.analysers:
            if all_analysers[analyser] not in result:
                result.append(all_analysers[analyser])
        return result
        
    analysers = __selected_analysers()

    def __init__(self, title: str, paper_url: str, specific_url: str, github_url: str):
        self.title             : str           = title
        self.paper_url         : Optional[str] = paper_url
        self.specific_url      : Optional[str] = specific_url
        self.github_url        : Optional[str] = github_url
        self.AI_url            : Optional[str] = None
        self.test_url          : Optional[str] = None
        self.repositories      : List[str]     = []
        self.status            : ProjectStatus = ProjectStatus.NOT_SET
        self.test_status       : ProjectStatus = ProjectStatus.NOT_SET
        self.error_msg         : Optional[str] = None
        self.error_trace       : Optional[str] = None
        self.exec_time         : float         = 0.0
        self.exec_output       : str           = "No Output generated yet"
        self.exce_error        : Optional[str] = None
        self.project_dir       : Optional[str] = None
        self.analysers_results : Dict          = { analyser:{} for analyser, _ in Project.analysers }
            


    def __str__(self):
        return (
            f"Title       : {self.title}\n"
            f"Paper URL   : {self.paper_url}\n"
            f"Specific URL: {self.specific_url}\n"
            f"Github URL  : {self.github_url}\n"
            f"Repositories: {self.repositories}\n"
            f"AI URL      : {self.AI_url}\n" 
            f"Status      : {self.status}\n"
            f"Finished in : {self.exec_time}"
            + (f"\nError      : {self.error_msg}" if self.status == ProjectStatus.ERROR else "")
        )
    
    def set_status_to_error(self, e: Exception):
        self.status = ProjectStatus.ERROR
        self.error_msg = str(e)
        self.error_trace = ''.join(traceback.format_exception(e))
    
    def set_analysers_status_to_error(self, e: Exception, type: str):
        self.analysers_results[type]["status"]      = ProjectStatus.ERROR
        self.analysers_results[type]["error_msg"]   = str(e)
        self.analysers_results[type]["error_trace"] = ''.join(traceback.format_exception(e))

    @staticmethod
    def csv_headers() -> str:
        h = []
        h.append("Title")
        h.append("Paper URL")
        h.append("Specific URL")
        h.append("Github URL")
        h.append("Repositories")
        h.append("AI URL")
        h.append("Test URL")
        h.append("Test status")
        h.append("Status")
        h.append("Error message")
        h.append("Error trace")
        h.append("Total Execution time")

        for analyser, _ in Project.analysers:
            h.append(f'"{analyser}:\nStatus"')
            h.append(f'"{analyser}:\nOut"')
            h.append(f'"{analyser}:\nError message"')
            h.append(f'"{analyser}:\nError trace"')
            h.append(f'"{analyser}:\nExec time"')

        return ','.join(h) + '\n'

    def to_csv(self) -> str:
        no_dquotes = str.maketrans("","",'"')
        fields = []
        fields.append(self.title)
        fields.append(self.paper_url)
        fields.append(self.specific_url)
        fields.append(self.github_url)
        fields.append('"[' + ','.join(self.repositories) + ']"')
        fields.append(self.AI_url)
        fields.append(self.test_url)
        fields.append('"' + self.test_status + '"')
        fields.append('"' + self.status + '"')
        fields.append(self.error_msg and '"' + self.error_msg.translate(no_dquotes) + '"')
        fields.append(self.error_trace and '"' + self.error_trace.translate(no_dquotes) + '"')
        fields.append(f"{self.exec_time:.4f}")

        for analyser, _ in Project.analysers:
            analyser_status = self.analysers_results[analyser].get("status")
            fields.append(analyser_status and '"' + analyser_status + '"')
            
            analyser_out = self.analysers_results[analyser].get("out")
            fields.append(analyser_out and '"' + str(analyser_out).translate(no_dquotes) + '"')
            
            analyser_error_message = self.analysers_results[analyser].get("error_msg")
            fields.append(analyser_error_message and '"'+ analyser_error_message.translate(no_dquotes) + '"')
            
            analyser_error_trace = self.analysers_results[analyser].get("error_trace")
            fields.append(analyser_error_trace and '"' + analyser_error_trace.translate(no_dquotes) + '"')
            
            analyser_exec_time = self.analysers_results[analyser].get("exec_time")
            fields.append(analyser_exec_time and f"{analyser_exec_time:.4f}")

        field_str = [f"{x}" if x else "" for x in fields]
        return ",".join(field_str) + '\n'
        
    @State_Check
    def analyse(self):
        print("analysing...")
        self.test_status = ProjectStatus.TEST_URL_SRC if self.github_url else ProjectStatus.TEST_URL_AI
        
        self.test_url = self.github_url if self.test_status is ProjectStatus.TEST_URL_SRC else self.AI_url
        
        tmp = self.test_url
        tmp = tmp.strip().rstrip("/")
        github_path = (
            tmp.strip()
            .replace("https://github.com/", "")
            .replace("github.com/", "")
        )
        
        github_project = GitHubProject(
            project_url      = self.test_url,
            project_name     = os.path.basename(github_path),
            github_path      = github_path,
            github_owner     = os.path.dirname(github_path),
            accra_timeout    = flags.timeout,
            reuse_existing   = flags.reuse_existing,
        )
        self.project_dir = os.path.join(github_project.import_directory, ("project_" + github_project.project_name)) 
       
        original_sys_path = list(sys.path)

        pkg_mng = None
        try:
            github_project.fetch_project_data()
            
            pkg_mng = github_project.body_create_project_profile()

            for _, analyser in Project.analysers:
                github_project.analysers.append(analyser(github_project))

            for i,analyser in enumerate(github_project.analysers):
                analyser_name = Project.analysers[i][0]
                analyser_time_start = time.time()
                try:
                    analyser.analyze()
                except Exception as e:
                    self.set_analysers_status_to_error(e, analyser_name)
                finally:
                    analyser.finalize()
                    self.analysers_results[analyser_name]["exec_time"] = time.time() - analyser_time_start
                    
        except Exception as e:
            self.set_status_to_error(e)
            return
        finally:
            if flags.reuse_existing:
                github_project.finalize_create_project_profile(original_sys_path, tmp_pkg_mng=None)
            else:
                github_project.finalize_create_project_profile(original_sys_path, tmp_pkg_mng=pkg_mng)
        
        for i, analyser in enumerate(github_project.analysers):
            analyser_name = Project.analysers[i][0]
            if self.analysers_results[analyser_name].get("status") == ProjectStatus.ERROR:
                continue
            
            match analyser_name:
                case "Parallelism analyser":
                    self.analysers_results[analyser_name]["out"] = {}
                    if not github_project.project_data["project_details"].get("threading_requirements"):
                        self.analysers_results[analyser_name]["status"] = ProjectStatus.NO_PARA_TH
                    else:
                        self.analysers_results[analyser_name]["status"] = ProjectStatus.OK
                        self.analysers_results[analyser_name]["out"]["threading_requirements"] = github_project.project_data["project_details"]["threading_requirements"]
                    
                    if not github_project.project_data["project_details"].get("multiprocessing_requirements"):
                        self.analysers_results[analyser_name]["status"] += ProjectStatus.NO_PARA_MULT
                    else:
                        self.analysers_results[analyser_name]["status"] = ProjectStatus.OK
                        self.analysers_results[analyser_name]["out"]["multiprocessing_requirements"] = github_project.project_data["project_details"]["multiprocessing_requirements"]

                case "Network analyser":
                    if not github_project.project_data["project_details"].get("network_requirements"):
                        self.analysers_results[analyser_name]["status"] = ProjectStatus.NO_NET
                    else:
                        self.analysers_results[analyser_name]["status"] = ProjectStatus.OK
                        self.analysers_results[analyser_name]["out"]    = github_project.project_data["project_details"]["network_requirements"]

                case "Memory analyser":
                    if not github_project.project_data["project_details"].get("memory_profile"):
                        self.analysers_results[analyser_name]["status"] = ProjectStatus.NO_MEM
                    else:
                        self.analysers_results[analyser_name]["status"] = ProjectStatus.OK
                        self.analysers_results[analyser_name]["out"]    = github_project.project_data["project_details"]["memory_profile"]
                
                case "Load analyser":
                    if not github_project.project_data["project_details"].get("load_profile"):
                        self.analysers_results[analyser_name]["status"] = ProjectStatus.NO_LOAD
                    else:
                        self.analysers_results[analyser_name]["status"] = ProjectStatus.OK
                        self.analysers_results[analyser_name]["out"]    = github_project.project_data["project_details"]["load_profile"]

                case "Example finder":
                    if not github_project.project_data.get("example_filename"):
                        self.analysers_results[analyser_name]["status"] = ProjectStatus.NO_EXAMPLE
                    else:
                        self.analysers_results[analyser_name]["status"] = ProjectStatus.OK
                        self.analysers_results[analyser_name]["out"]    = github_project.project_data["example_filename"]

                case _:
                    print(f"ERROR: could not match analyser `{analyser_name}`")
                    sys.exit()

            if self.analysers_results[analyser_name]["status"] is not ProjectStatus.OK:
                if not (hasattr(analyser, "err_mng") and analyser.err_mng.error_caught):
                    continue
                errors = analyser.err_mng.error_caught
                self.analysers_results[analyser_name]["error_msg"]   = f'\n{"~"*50}\n'.join([str(e) for e in errors])
                self.analysers_results[analyser_name]["error_trace"] = f'\n{"~"*50}\n'.join([''.join(traceback.format_exception(e)) for e in errors])
                analyser.err_mng.error_caught.clear()
            
    def parse_paper(self):
        print("parsing...")

        url = self.specific_url or self.paper_url
        if not url: 
            self.status = ProjectStatus.NO_EXEC
            return
        
        github_urls: Optional[List[str]]
        github_urls = None
        paper_agent = ConstructorPaperAgentLC()
        textual_file = paper_agent.get_local_textual_file(url)
        try:
            paper_analyser = PaperAnalyserPDF(paper=url, textual_file=textual_file)
        except Exception as e:
            self.set_status_to_error(e)
            return
        
        try:
            github_urls = list(paper_analyser.extract_github_references())
        except Exception as e:
            self.set_status_to_error(e)
            return
        
        if not github_urls:
            self.status = ProjectStatus.NO_REPOS
            return
        
        self.repositories = github_urls
        self.match_url()
        try:
            self.AI_url = paper_agent.get_url_by_llm(paper_analyser.actual_paper,github_urls)
        
        except Exception as e:
            self.set_status_to_error(e)
            return

    def test(self):
        time_start = time.time()
        self.parse_paper()
        self.analyse()
        self.exec_time = time.time() - time_start
    
    @State_Check
    def match_url(self):
        if self.github_url and (self.github_url in self.repositories):
            self.status = ProjectStatus.OK
        else:
            self.status = ProjectStatus.WRONG_GIVEN
    
    def remove_dir(self):
        if not self.project_dir:
            return
        cmd = ["rm", "-rf", self.project_dir.lstrip("/")]
        print(f"removing project folder with: `{' '.join(cmd)}`")
        subprocess.run(cmd)
        
def parse_projects_from_csv(csv_path: str) -> List[Project]:
    projects: List[Project] = []
    with open(csv_path) as projects_list_file:
        projects_list = [line.strip().split(',') for line in projects_list_file]
        headers = projects_list[0]
        projects_list = projects_list[1:]
        for project in projects_list:
            for j in range(len(headers)):
                if len(project) <= j:
                    project.append(None)
                elif not project[j].strip():
                    project[j] = None
                else:
                    project[j] = project[j].strip()
            projects.append(Project(*project))
    return projects

                
    

if __name__ == "__main__":
    os.chdir("..")

    projects: List[Project] = parse_projects_from_csv("./accra_test/projects_list.csv")
    csv_path: str = "./accra_test/result_test.csv"

    with open(csv_path, "w") as csv_file:
        csv_file.write(Project.csv_headers())
        csv_file.flush()
        projects = list(reversed(projects[flags.begin:flags.end]))
        i:int    = 1
        while projects:
            project = projects.pop()
            print(f"Testing project {i}/{len(projects)} `{project.title}`...\n")
            i += 1
            
            project.test()
            csv_file.write(project.to_csv())
            csv_file.flush()
            if not flags.no_rm:
                project.remove_dir()
            print(project)
            print("-"*50)
            
            del project
            gc.collect()
