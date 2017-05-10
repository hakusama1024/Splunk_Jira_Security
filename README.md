# Splunk-Jira CLI

This CLI can be used to ingest jira metrics into splunk. It is developed with the aim of pushing existing JIRA metrics into splunk or historical jira metrics as sourced from a csv file.

### Installation
It is recommended that this project be installed inside a python virtualenv. After setting up a new 3.5.x python env , clone this project from github.

```sh
$ cd splunk-jira
$ pip install .
```

Alternatively

```sh
$ cd splunk-jira
$ python setup.py install
```

On successful installation, splunk-jira alias will be added to your shell and you could verify that  by typing  `splunk-jira --help` in your shell.

### Usage
The following files will need to be added before the cli fully functional.
+ Using the config/config.yaml.default as a template create a config/config.yaml and edit the changeme sections.
+ The cli can be configured to post splunk data to one of 
	1. Local splunk instance.
	2. QE splunk instance
    3. SAAC splunk instance. 
***Note**: The environment should be changed in the config.yaml file for posting to
different splunk instances.*
+ Reach out to project members or slack channel for the authentication token details for HTTP event aggregator to QE/SAAC splunk instances.

#### Insert current data for multiple projects:
The list of projects for ingesting jira metrics is driven by configuration file under "project mapping" section. For instance, to report "RNS" project belonging to "Rackertools", the project_mapping will need the key "Rackertools" and the project RNS listed under the key. Once the config file is set up,

```sh
$ splunk-jira --mode current
```
will insert the data for all the projects specified under projects_mapping.

#### Insert historical data for multiple projects:
To gather  timeline based metrics, the cli can be run in historic mode. 

```sh
$ splunk-jira --mode historic
```
will insert the historical csv based metrics data into splunk.

#### Insert current data for a single project:
To ingest the current data for a single jira project,

```sh
$ splunk-jira --mode current --project <project-jira-id>
```
will ingest the current metrics of the project into JIRA.

#### Insert data for a specific splunk host:
Splunk classifies data based on a field called "host" [[splunk-doc]](https://docs.splunk.com/Documentation/Splunk/6.5.2/Data/Overridedefaulthostassignments) which is part of each document, indexed by splunk. The config file has a default "splunk_host" variable which specifies the default host. However, this can be overriden via commandline passing in a host argument.

```sh
$ splunk-jira --mode current --host <splunk-host-id>
```

#### Sample cli commands 
 - Insert current metrics of all projects.
```
splunk-jira --mode current
```
- Insert historic metrics of all projects under v1 metrics. 
```
splunk-jira --mode historic
```

- Insert data for a specific project
```
splunk-jira --mode current --project <jira_project_id>
```

- Insert data for a specific host
```
splunk-jira --mode current --host <splunk_host_id>
```

- Insert data for a specific host & a specific project
```
splunk-jira --mode current --host <splunk_host_id> --project <jira_project_id>
```

### Dashboard installation
If you would like to see the loaded data displayed graphically you can install the sample sample dashboard app/sample_splunk_dashbord.xml.  To do so, select the "Search & Reporting" app and click on "Dashboard" in the top horizontal menu.  On the top right hand side, click on the "Create New Dashboard" button.  Enter a title for the dashboard and click on "Create Dashboard".  Click on the "Source" button.  Replace the contents on this page with the contents of app/sample_splunk_dashbord.xml.  

You need to replace the index and host names in the sample with your own.  Replace all occurrences of:

```
index="rax_temp_60" host="thom9607_2017-03-17T17:06"
```

with:

```
index="<your_index_name>" host="<your_host_name>" 
```

Once done, click on the "Save" button at the top right hand side.

### Macro installation
The sample dashboard relies on the setsorttime macro for some graphs.  Follow the instructions below to install it:

Click on "Settings" at the top right hand corner.  Click on "Advanced search" then "Search macros".  Click on the "New" button on the top left hand side.  Enter the following:

Destination app: search
Name: setsorttime(2)
Definition:
```
eval _time=strptime($sortdatetime$,"$datetimeformat$")
         | sort _time
         | addinfo
         | where _time>=info_min_time AND (_time<=info_max_time OR info_max_time="+Infinity")
```

Arguments: sortdatetime, datetimeformat

Then click "Save"

### Contact: 
Reach out to siva.sundaresan@rackspace.com, thomas.carlton@rackspace.com or #metrics_qe_team channel on slack for any questions. 
