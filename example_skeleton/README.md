# ACCRa
ACCRa -- Auto-Configuration of the Constructor Research Platform

**Objective**: The automation of the overall set-up and configuration of the Constructor Research Platform, analyzing source code and configuration files present in a GitHub-style or an Amazon-style repository or described in a research paper, thus dramatically simplifying the adoption process by users.

**Data Sources**:
Possible data sources for this project include:
- Sample project repository configurations and research papers
- Available additional requirements for similar projects
- Information on available system resources
- Possible error logs and system status

**Workflow**:
1. Given a url of a scientific paper it downloads it
2. The paper is parsed in search of a gitHub repository
3. Clones the repository
4. Creates a virtual environment associated to that project which could use every python interpreter (ACCRa has its own virtual environment with python 3.12) 
5. The projects get initialized and installs all required packages into that venv 
6. The code's project is analyzed by four aspects: Parallelism, Network, Memory, Load

### Building and running ACCRa application
Inside docker_compose.env you have to insert:
```
# Here below the connection to the training.constructor
CONSTRUCTOR_KM_ID="get the id for the team in discord"
CONSTRUCTOR_API_KEY="get the key from the team in discord"
CONSTRUCTOR_API_URL="https://training.constructor.app/api/platform-kmapi/v1/"
```

### Run the tool in docker compose
The whole project can be run in docker compose.

Create the `ImportedProjects` folder and make the docker `appuser` user the owner
using user's uid.

``` bash
mkdir ImportedProjects
chown 10001:10001 ImportedProjects/
```

Start the project

``` bash
docker compose up
```

While compose is running you can log into the running container

``` bash
docker compose exec accra /bin/bash
```

To run accra use the command:
```bash 
python accra_lc_pipeline.py path/scientific/paper
```
where:
the `path/scientific/paper` path can be both a URL (e.g. https://arxiv.org/pdf/1907.10902) or a path to an existing files (/ACCRa/deepHyper.pdf) 

### Run Jupyter notebook
Docker compose is configured to pass-through the Jupyter app ports (`8888`).

To start Jupyter

Run compose if it is not running yet
``` bash
docker compose up
```

Log into the running container

``` bash
docker compose exec accra /bin/bash
```

Run Jupyter Lab binding the loopback ip

``` bash
jupyter-lab --ip=0.0.0.0
```

The output of the last command will have a link in the format of

```
[I 2025-11-20 09:57:34.139 ServerApp] Jupyter Server 2.17.0 is running at:
[I 2025-11-20 09:57:34.139 ServerApp] http://397af88c607f:8888/lab?token=1559b4...
[I 2025-11-20 09:57:34.139 ServerApp]     http://127.0.0.1:8888/lab?token=1559b4...
```

Click the link starting with `127.0.0.1` to open the application in your browser.

Since jupyter is running as the image's user, it does not have the permission
to write to the main code files. Similarly to the `ImportedProjects` folder,
we can give access to a specific folder.

``` bash
chown 10001:10001 notebooks
```

You can create and run new notebooks in the `notebooks` folder.


### Disable other analysers
There are several analysers in the project. Since you are interested mainly
in the `GithubProjectExampleFinder` which is responsible for generating
the example script, you might want to disable other analysers to save execution time.

You can disable the other analysers by commenting `project.create_project_profile()` call in `accra_code/constructor_project/constructor_manager/constructor_manager_lc.py`
on line 58:
``` python
        # Separate function to create the profile
        def manage_project_profile_creation(state: dict):
            project: GitHubProject = state["project"]
            if not project:
                state["error"] = "No project to profile"
                return state
            # analyses project and creates metadata
            project.create_project_profile() # <-- Comment this call
            state["project_data"] = project.project_data
            return state
```
