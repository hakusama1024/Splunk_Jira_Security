import argparse
import datetime
import json

import multiprocessing
import time

from retrying import retry
from copy import deepcopy
from collections import defaultdict
from dateutil.relativedelta import relativedelta, SA
from multiprocessing import Pool
import jira
import requests
import sys 


from app import settings
from app.utils import get_key_from_dictionary, get_attribute_value, get_products_dict

requests.packages.urllib3.disable_warnings()
logger = settings.configure_logging()
config = settings.config

BU_MAPPING = config.jira.project_mapping
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%f+0000"
INDEX = config.splunk[config.environment].index or ""
JIRA_PROJECTS = defaultdict(lambda: None)
SSO_NAME_MAPPINGS = defaultdict(lambda: None)
REQUIRED_FIELDS = ["Assignee", "Created", "Defect Type (TES)", "IssueType", "Key", "Priority",
                   "Project", "Reporter", "Resolution", "Resolved", "SDLC Phase", "Status", "Summary",
                   "Severity", "When Detected"]
SP_ENDPOINT = config.splunk[config.environment].host
SP_HEADER = {"Authorization": "Splunk {}".format(config.splunk[config.environment].token)}

jira_client = jira.JIRA(config.jira.host, basic_auth=(config.jira.username, config.jira.password))
jira_field_mapping = {field['name']: field['id'] for field in jira_client.fields() if field['name'] in REQUIRED_FIELDS}
jira_projects = jira_client.projects()

host = config.splunk[config.environment].splunk_host

product_dic = get_products_dict()
print(product_dic)


def jira_obj_to_dict(issue, date):
    """
    Converts a JIRA objects to a dictionary with a report_date of 'date'
    """



    product_name = ""
    if type(issue.fields.components) == list:
        for i in issue.fields.components:
            s = str(i)
            print(s)
            if s in product_dic:
                product_name = s
                break
    else:
        product_name = str(issue.fields.components)

    dev_owner = ""
    qe_owner = ""

    if product_name in product_dic:
       _, __, dev_owner, qe_owner = product_dic[product_name]

    jira_dict = {
        "assignee": issue.fields.assignee.displayName if issue.fields.assignee else None,
        "business_unit": get_key_from_dictionary(issue.fields.project.key, BU_MAPPING),
        "created": issue.fields.created,
        "issue_type": issue.fields.issuetype.name,
        "jira_project": issue.fields.project.key,
        "product_name": product_name,
        "dev_owner": dev_owner,
        "qe_owner": qe_owner,
        "key": issue.key,
        "link": "https://jira.rax.io/browse/"+issue.key,
        "project_name": issue.fields.project.name,
        "priority": issue.fields.priority.name,
        "reporter": issue.fields.reporter.displayName,
        "report_date": date,
        "resolution": issue.fields.resolution.name if issue.fields.resolution else None,
        "resolved": get_attribute_value(issue.fields, str(jira_field_mapping['Resolved'])),
        "status": issue.fields.status.name,
        "summary": issue.fields.summary,
        "when_detected": get_attribute_value(
            get_attribute_value(issue.fields, str(jira_field_mapping['When Detected'])), "value"),
        "defect_type": get_attribute_value(
            get_attribute_value(issue.fields, str(jira_field_mapping['Defect Type (TES)'])), "value"),
        "severity": get_attribute_value(
            get_attribute_value(issue.fields, str(jira_field_mapping['Severity'])), "value"),
        "sdlc_phase": get_attribute_value(
            get_attribute_value(issue.fields, str(jira_field_mapping['SDLC Phase'])), "value")
    }

    print(jira_dict)

    return jira_dict


def create_defect(jira_dict, issue):
    """
    Correctly formats all data in defect prior to pushing to Splunk
    """
    defect = deepcopy(jira_dict)

    if jira_dict["sdlc_phase"].lower() == "closed":
        created_dt = datetime.datetime.strptime(defect["created"], DATE_FORMAT)
        resolved_dt = datetime.datetime.strptime(defect["resolved"], DATE_FORMAT)

        if (resolved_dt - created_dt).days == 0:
            defect["age"] = 0 if (resolved_dt.month == created_dt.month and
                                  resolved_dt.day == created_dt.day) else 1
        else:
            timedelta = resolved_dt - created_dt
            defect["age"] = int(round(float((timedelta.days*86400 + timedelta.seconds)/(86400)), 0))
    else:
        timedelta = datetime.datetime.strptime(defect["report_date"], DATE_FORMAT) - datetime.datetime.strptime(defect["created"], DATE_FORMAT)
        defect["age"] = int(round(float((timedelta.days*86400 + timedelta.seconds)/(86400)), 0))

    return defect


def jira_for_date(issue, changelog, date):
    """
    Gets the state of a JIRA issue for a specific date
    """
    new_issue = deepcopy(issue)
    changes = sorted([history for history in changelog.histories
        if datetime.datetime.strptime(history.created, DATE_FORMAT) < datetime.datetime.strptime(new_issue["report_date"], DATE_FORMAT) and
        datetime.datetime.strptime(history.created, DATE_FORMAT) > date], key=lambda x: x.created, reverse=True)

    back_to_v1 = False
    for change in changes:
        for item in change.items:
            field = item.field.lower().replace(' ', '_')
            if field in new_issue.keys():
                if field == "severity" or field == "when_detected" or field == "defect_type":
                    continue
                new_issue[field] = item.fromString
                if field == 'status':
                    if back_to_v1:
                        new_issue["sdlc_phase"] = get_key_from_dictionary(new_issue['status'].lower(),
                                                                          config.jira.status_mapping)
                elif field == 'sdlc_phase' and not back_to_v1:
                    if new_issue["sdlc_phase"] is None:
                        new_issue["sdlc_phase"] = get_key_from_dictionary(new_issue['status'].lower(),
                                                                          config.jira.status_mapping)
                        back_to_v1 = True

    new_issue["report_date"] = date.strftime(DATE_FORMAT)

    return new_issue


def push_current_data(project):
    """
    Loads all current JIRA data into Splunk
    """
    defects = []

    logger.info("Starting {}...".format(project))
    jira_issues = get_jira_defects(project)
    now = datetime.datetime.utcnow().strftime(DATE_FORMAT)
    logger.debug("Fetched  {} issues successfully for {}".format(len(jira_issues), project))

    # Each issue fetched is being generated with our schema.
    for issue in jira_issues:
        try:
            jira_dict = jira_obj_to_dict(issue, now)
            defect = create_defect(jira_dict, issue)
            defects.append(defect)
        except Exception as e:
            logger.debug("Exception processing {} {}".format(issue.key, e))
            logger.debug("Missing values {}".format(str(jira_dict)))
            pass
    if len(defects) < len(jira_issues):
        logger.debug("{delta} defects not added in the {} report".format(project, delta=len(jira_issues) - len(defects)))

    return post_defects(project, jira_issues, defects)


def push_historic_data(project):
    """
    Loads all current and historic JIRA data into Splunk
    """
    defects = []

    logger.info("Starting {}...".format(project))
    jira_issues = get_jira_defects(project)
    last_upload = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + relativedelta(weekday=SA(-1))
    logger.debug("Fetched  {} issues successfully for {}".format(len(jira_issues), project))
    for issue in jira_issues:
        try:
            created = datetime.datetime.strptime(issue.fields.created, DATE_FORMAT)
            jira_dict = jira_obj_to_dict(issue, datetime.datetime.utcnow().strftime(DATE_FORMAT))

            historic_data = []
            # Last Friday of the report ran
            report_date = last_upload
            while(report_date > created):
                jira_dict = jira_for_date(jira_dict, issue.changelog, report_date)
                historic_data.insert(0, create_defect(jira_dict, issue))
                report_date -= datetime.timedelta(weeks=1)
            defects.append(historic_data)
        except Exception as e:
            logger.debug("Exception processing {} {}".format(jira_dict["key"], e))
            logger.exception("Exception")
            logger.debug("Missing values {}".format(str(jira_dict)))
            pass
    if len(defects) < len(jira_issues):
        logger.debug("{delta} defects not added in the {} report".format(project, delta=len(jira_issues) - len(defects)))
    defects_as_list = []
    for defect in defects:
        defects_as_list.extend(defect)
    return post_defects(project, jira_issues, defects_as_list)



def get_jira_defects(project):
    """
    Get the initial set of JIRA issues for a project
    """
    return get_jira_issues('project = "{}" AND filter = 19589'.format(project))


@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000, stop_max_attempt_number=5)
def get_jira_issues(query):
    """
    Get all JIRA issues matching the query
    """
    jira_issues = []
    defects = []
    count, maxlen = 0, 1
    while count < maxlen:
        issues = jira_client.search_issues(query, startAt=count, maxResults=50, expand='changelog')
        jira_issues.extend(issues)
        count = len(jira_issues)
        maxlen = issues.total

    return jira_issues


@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000, stop_max_attempt_number=5)
def post_to_splunk(payload, *args, **kwargs):
    response = requests.post(SP_ENDPOINT, headers=SP_HEADER, data=payload, verify=False)
    if response.status_code != 200:
        raise RuntimeError("Splunk Event Collector returned {}, expected 200\nResponse: {}.format(".format(response.status_code,
                                                                                                           response.text))

    return response


def post_defects(project, jira_issues, defects):
    """
    Posts defects to Splunk
    """
    payload = ""
    for defect in defects:
        #TODO: this is a hack which can be removed once, excel docs are done away with.
        if defect["assignee"] == "Unassigned":
            defect["assignee"] = None

        data = {"host": host,
                "time": int(datetime.datetime.strptime(defect["report_date"], DATE_FORMAT).strftime("%s")) * 1000,
                "event": defect,
                "index": INDEX,
                "source": "defect"}
        if config.splunk[config.environment].payload_limit and len(payload) + len(data) >= config.splunk[config.environment].payload_limit:
            logger.info("Reached length: {}, Restarting".format(len(payload)))
            rsp = post_to_splunk(payload=payload)
            logger.info("Successfully posted batched data to Splunk {}".format(project))
            payload = "{}".format(json.dumps(data))
        else:
            payload += " {}".format(json.dumps(data))

    rsp = post_to_splunk(payload=payload)
    logger.info("Successfully posted data to splunk for {}".format(project))
    return {project: rsp.status_code, "defects_require_fixing": str(len(jira_issues) - len(defects))}


def verify_project(project):
    errors = []
    issues = get_jira_issues("project = {} and issuetype = Bug".format(project))
    if len(issues) != 0:
        errors.append("Found {} bugs on the project, expected none".format(len(issues)))

    issues = get_jira_issues("project = {} and issuetype = Defect".format(project))
    defect_count = len(issues)
    if defect_count == 0:
        errors.append("Expected Defects on the project, found none")

        for field in ["Defect Type (TES)", "Severity", "When Detected", "SDLC Phase"]:
            issues = get_jira_issues("project = {} and issuetype = Defect AND \"{}\" is empty".format(project, field))
            if len(issues) != 0:
                errors.append("Found {} defects with missing '{}' field, expected none".format(len(issues), field))

    if len(errors) == 0:
        print("SUCCESS")
    else:
        print("FAILED")
        print('\n'.join(errors))


def main():
    global host, VERSION

    parser = argparse.ArgumentParser(description="CLI to push JIRA metrics to splunk.")
    parser.add_argument('--mode', help='Run in current or parsecsv mode.', choices=["current", "historic"])
    parser.add_argument('--project', help="Run the cli for this single project. Eg: ETA")
    parser.add_argument('--host', help="Overrides the host data is loaded to in Splunk.")
    parser.add_argument('--verify', help="Verifies that a project has properly transitioned to v2 JIRA.")

    args = parser.parse_args()
    start = time.time()

    if args.host:
        host = args.host

    if args.verify:
        verify_project(args.verify)
    elif args.project:
        function = push_historic_data if args.mode == "historic" else push_current_data
        result = function(project=args.project)
        end = time.time()
        logger.debug("Project {} results {}".format(args.project, result))
        logger.info("Took {} seconds".format(str(end - start)))

    elif args.mode == "current" or args.mode == "historic":
        function = push_historic_data if args.mode == "historic" else push_current_data
        multiprocessing.log_to_stderr()
        for k, v in BU_MAPPING.items():
            pool = multiprocessing.Pool(len(v))
            results = pool.map(function, v)
            pool.close()
            pool.join()
            logger.debug("Project {} results {}".format(k, results))
        end = time.time()
        logger.info("{} Mode run took {} seconds".format(args.mode.capitalize(), str(end - start)))

    else:
        print("Provide either a mode or a project. Use --help for more info")
