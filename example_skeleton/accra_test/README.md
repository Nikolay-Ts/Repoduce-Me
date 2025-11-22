# ACCRa Testing Tool

This tool is designed to test the capabilities of ACCRa:

At the moment it checks for the Github URLs found by the program and runs the ExampleFinder analyser,
outputting a CSV file that reports the final status of each project, their eventual errors and other useful statistics. 

**Warning!**

The tool has not yet implemented a housekeeping feature i.e. it does not yet `rm -r app/ImportedProjects/` while running
so the directory can get quite heavy.

### Run the testing tool in docker compose
The whole project can be run in docker compose.

While compose is running you can log into the running container

``` bash
docker compose exec accra /bin/bash
```
Move to accra_test

``` bash
cd accra_test/
```

And launch the test

``` bash
python testing_tool.py
```

This will create a result.csv file in the current directory with the test results 

To avoid any problems with directory permissions and such we recommend 

``` bash
chown 10001:10001 accra_test/result_test.csv
```

