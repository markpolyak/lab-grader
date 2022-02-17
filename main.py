#!/usr/bin/env python3

import logging
import logging.config
import mailbox
import google_sheets
import common
import settings
import datetime
from dateutil.parser import isoparse, parse
import math
import yaml
import sys
import os
import time
import argparse

import collections

import mosspy
from mossum import mossum


# setup logging
def setup_logging(
    default_path='logging.yaml', default_level=logging.INFO, env_key='LOG_CFG'
):
    if not sys.warnoptions:
        # Route warnings through python logging
        logging.captureWarnings(True)
    # find logging config file
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)
    # set logging level for the root logger
    logging.getLogger().setLevel(default_level)


def _parse_args():
    """
    Internal function intended to parse command line arguments
    """
    parser = argparse.ArgumentParser(
        description="Process student updates from email and GitHub")
    # arguments
    parser.add_argument(
        '-c', '--course-config', dest='course_config', action='store',
        required=True,
        help="course config file",
    )
    parser.add_argument(
        '-u', '--update', dest='update_action',
        action='store', default=['all'],
        choices=['all', 'email', 'labs', 'appveyor', 'moss'],
        nargs='+',
        help="action to be taken: "
             "perform ALL updates, read EMAILs only, check LABs only, "
             "add new APPVEYOR projects only, run MOSS plagiarism check;\n"
             "use a combination of flags, e.g. 'email labs' to read emails "
             "and check labs, without doing other updates",
    )
    parser.add_argument(
        '-l', '--labs', dest='labs',
        action='store', nargs='+', default='all',
        help="choose labs to be processed, default is all",
    )
    parser.add_argument(
        '-a', '--auth', dest='authentication_config', action='store',
        default=os.path.join(os.path.dirname(os.path.realpath(__file__)),
                             'auth.yaml'),
        help="authentication config file",
    )
    # parser.add_argument(
    #     '--plagiarism', '--moss' dest='moss',
    #     action='store_true',
    #     help="check for plagiarism",
    # )
    parser.add_argument(
        '--dry-run', dest='dry_run',
        action='store_true',
        help="do not update any real data, do not send any emails "
             "or save any results, just print to console",
    )
    # parser.add_argument(
    #     '--ignore-email', dest='ignore_email',
    #     action='store_true',
    #     help="do not check for new emails",
    # )
    parser.add_argument(
        '--logging-config', dest='logging_config', action='store',
        default=os.path.join(os.path.dirname(os.path.realpath(__file__)),
                             'logging.yaml'),
        help='set logging config file',
    )
    parser.add_argument(
        '-v', '--verbose', dest='verbosity',
        action='count', default=0,
        help="verbose output (repeat for increased verbosity)"
    )
    return parser.parse_args()


def update_students(
    imap_conn, spreadsheet, dry_run=False,
    valid_subjects=[], email_config={}, return_address=''
):
    """
    """
    logger = logging.getLogger(__name__)
    # read all new letters in mailbox and extract student info
    logger.info("Processing mailbox...")
    students = mailbox.process_students(imap_conn, valid_subjects)
    logger.debug("New students from mailbox: %s", students)
    # validate student info and add to data
    for student in students:
        try:
            # GitHub API has a rate limit of 10 queries per minute for
            # unauthenticated users and 30 queries per minute for auth users,
            # see https://docs.github.com/en/free-pro-team@latest/rest/reference/search#rate-limit # noqa
            time.sleep(2.1)
            # check if github user exists (e.g. there are no obvious typos)
            if not common.github_user_exists(student['github']):
                raise ValueError("User '{}' not found on GitHub. Check your spelling or contact course staff.".format(student['github']))
            # Try to set student's github. This will raise an exception if:
            # - group or name are not found (i.e. invalid)
            # - this student already has a github account (changing github
            # account is done by course staff only to prohibit cheating)
            # - this github account is already used by another student (most
            # likely a cheating attempt)
            data_update = spreadsheet.set_student_github(student)
        except ValueError as e:
            errmsg = "Unable to process request from student '{}'".format(student['name'])
            logger.error("%s", errmsg)
            logger.exception(e)
            # print(errmsg)
            # print(e)
            email_text = (
                "{}\n\nSubject: {}\nDate received: {}\nGroup: {} (raw: {})\nStudent: {}\nGitHub account: {}".format(
                    str(e),
                    student['email_subject'],
                    student['email_timestamp'],
                    student['group'],
                    student['raw_group'],
                    student['name'],
                    student['github'],
                )
            )
            # set a message as unseen (unread)
            # mailbox.mark_unread(imap_conn, student['uid'])
            recepients = [student['email'], return_address]
            if not dry_run:
                # send a report
                mailbox.send_email(recepients, errmsg, email_text, email_config)
                # flag the message, but leave it as read since we don't want
                # another report to be sent when the script is run next time
                mailbox.mark_flagged(imap_conn, student['uid'])
            else:
                logger.warning("An email would have been sent to %s. Subject: %s. Text: %s", recepients, errmsg, email_text)
                # print("An email would have been sent to {}. Subject: {}. Text: {}".format(recepients, errmsg, email_text))
                # set a message as unseen (unread)
                mailbox.mark_unread(imap_conn, student['uid'])
        else:
            if dry_run:
                # set a message as unseen (unread)
                mailbox.mark_unread(imap_conn, student['uid'])
    return spreadsheet.data_update


def create_appveyor_projects(dry_run):
    """
    """
    task3_repos = common.get_github_repo_names(settings.github_organization, prefix='os-task3', private=False)
    # print(task3_repos)
    # zz = common.get_appveyor_project_repo_names()
    new_projects = common.add_appveyor_projects_safely(list(task3_repos), trigger_build=True, dry_run=dry_run)
    return new_projects


def check_lab(lab_id, groups, spreadsheet, course_config={}):
    """
    """
    logger = logging.getLogger(__name__)
    logger.info("Performing check on lab %s", lab_id)
    prefix = course_config['labs'][lab_id]['github-prefix']
    repos = common.get_github_repo_names(course_config['github']['organization'], prefix)
    logger.debug("Found %d repos with %s prefix: %s", len(repos), prefix, repos)
    deadlines = {}
    lab_id_int = int(lab_id)
    lab_id_column = course_config['labs'][lab_id].get('short-name', lab_id_int)
    for group in groups:
        deadline_str = spreadsheet.get_lab_deadline(group, lab_id_column)
        if deadline_str:
            # add year if it is missing
            if len(deadline_str.split('.')) == 2:
                deadline_str += '.{}'.format(datetime.datetime.now().year)
            # add hours, minutes and seconds based on Moscow time
            deadline_str += ' 23:59:59 ' + course_config.get('timezone', 'UTC')
            # print(deadline_str)
        try:
            deadlines[group] = parse(deadline_str, dayfirst=True)
        except (ValueError, TypeError):
            deadlines[group] = None
    # if logger.isEnabledFor(logging.DEBUG):
    #     logger.debug("Deadlines for lab %s are: %s", lab_id, {k:v.isoformat() for (k, v) in deadlines.items()})
    for repo in repos:
        github_account = repo.split('/')[1][len(prefix)+1:]
        try:
            student = spreadsheet.find_student_by_github(github_account)
        except ValueError as e:
            # student not found, probably he/she forgot to send a letter with GitHub account info
            logger.warning(e)
            # print(e)
            continue
        # check if this lab is already accounted for
        current_status = spreadsheet.get_student_lab_status(student, lab_id_column)
        if current_status is not None and not current_status.startswith('?'):
            logger.debug("Student %s is skipped. Current lab status is '%s'", student, current_status)
            # this lab is already accounted for, skip it
            continue

        # check existence of repo_requirements node for lab_id
        if "repo_requirements" in course_config['labs'][lab_id]:
            grade_coefficient: float = 0.0

            # computing grade coefficient by commits
            commit_grade_coefficient = common.get_repo_commit_grade_coefficient(repo, lab_id)
            if commit_grade_coefficient is not None:
                grade_coefficient += commit_grade_coefficient

            # computing grade coefficient by issues
            issues_grade_coefficient = common.get_repo_issues_grade_coefficient(repo, lab_id)
            if issues_grade_coefficient is not None:
                grade_coefficient += issues_grade_coefficient

            if grade_coefficient > 0.0:
                spreadsheet.set_student_lab_status(
                    student,
                    lab_id_column,
                    "?v*{0:g}".format(grade_coefficient)
                )
            else:
                # calculated coefficient for this lab is zero, skip it
                continue

        # check if tests have passed successfully
        for ci_service in course_config['labs'][lab_id].get('ci', ['']):
            logger.debug("Performing check for '%s' data in %s", ci_service, repo)
            completion_date = None
            log = None
            # TODO: check_run names should come from course yaml file. Replace the lists below with this parameter
            if ci_service == 'appveyor':
                completion_date = common.get_successfull_status_info(repo).get("updated_at")
                if completion_date:
                    log = common.get_appveyor_log(repo)
            elif ci_service == 'travis':
                completion_date = common.get_successfull_build_info(repo, ["Travis CI"]).get("completed_at")
                if completion_date:
                    log = common.get_travis_log(repo, ["Travis CI"])
            elif ci_service == 'workflows':
                try:
                    ci_jobs = course_config['labs'][lab_id]['ci'].get(ci_service)
                except (AttributeError, TypeError): 
                    # AttributeError in case there is no .get method and TypeError in case get is not callable
                    ci_jobs = ["Autograding", "test", "build"]
                    logger.debug("No GitHub Actions jobs specified. Fall back to default %s", ci_jobs)
                # ci_jobs = course_config['labs'][lab_id]['ci'][ci_service]
                completion_date = common.get_successfull_build_info(
                    repo, ci_jobs, all_successfull=True
                ).get("completed_at")
                if completion_date:
                    log = common.get_github_workflows_log(repo, ci_jobs)
            # TODO: add support for not using any CI/CD service at all, e.g.:
            elif ci_service == '':
                # do something
                pass
            else:
                raise ValueError(f"Unsupported CI/CD service '{ci_service}' for lab {lab_id} found")
            logger.debug("Completion date for %s with %s is %s", repo, ci_service, completion_date)
            # check if tests were completed successfully and tests should not be ignored
            if completion_date and not course_config['labs'][lab_id].get('ignore-completion-date', False):
                # calculate correct TASKID
                student_task_id = int(spreadsheet.get_student_task_id(student))
                student_task_id += course_config['labs'][lab_id].get('taskid-shift', 0)
                student_task_id = student_task_id % course_config['labs'][lab_id]['taskid-max']
                if student_task_id == 0:
                    student_task_id = course_config['labs'][lab_id]['taskid-max']
                # check TASKID from logs
                if common.get_task_id(log) != student_task_id and not course_config['labs'][lab_id].get('ignore-task-id', False):
                    spreadsheet.set_student_lab_status(student, lab_id_column, "?! Wrong TASKID!")
                    # print(common.get_task_id(log), student_task_id)
                    # print(log)
                else:
                    # everything looks good, go on and update lab status
                    # get grading points (if any) from the logs
                    grading_points = common.get_grading_points(log)
                    if grading_points is not None:
                        grade_points_suffix = f"@{grading_points}"
                    else:
                        grade_points_suffix = ""
                    # calculate grade reduction coefficient
                    reduction_coefficient_str = common.get_grade_reduction_coefficient(log)
                    if reduction_coefficient_str is not None:
                        grade_reduction_suffix = "*{}".format(reduction_coefficient_str)
                    else:
                        grade_reduction_suffix = ""
                    # calculate deadline penalty
                    student_dt = isoparse(completion_date)
                    penalty_suffix = ""
                    if student_dt > deadlines[student['group']]:
                        overdue = student_dt - deadlines[student['group']]
                        penalty = math.ceil((overdue.days + overdue.seconds / 86400) / 7)
                        # TODO: check that penalty does not exceed maximum grade points for that lab
                        penalty = min(penalty, 
                            course_config['labs'][lab_id].get('penalty-max', 0))
                        if penalty > 0:
                            penalty_suffix = "-{}".format(penalty)
                        # print(f"{student_dt}, {deadlines[student['group']]}")
                        # print(f"{overdue}, {penalty}")
                    # update status
                    lab_status = "v{}{}{}".format(grade_points_suffix, grade_reduction_suffix, penalty_suffix)
                    logger.debug("New status for lab '%s' by student '%s' is '%s' from CI service '%s'", lab_id, student, lab_status, ci_service)
                    spreadsheet.set_student_lab_status(
                        student, lab_id_column, lab_status,
                    )
                # correct solution found, don't iterate over other ci services
                break
            else:
                logger.debug("No valid solution found for lab '%s' by student %s with CI service '%s'", lab_id, student, ci_service)
    return spreadsheet.data_update


def check_plagiarism(lab_id, local_path, moss_user_id, course_config={}):
    """
    """
    # TODO: this is unfinished function
    prefix = course_config['labs'][lab_id]['github-prefix']
    # get a list of repositories
    repos = common.get_github_repo_names(
        course_config['github']['organization'], prefix)
    # initialize MOSS
    moss_settings = course_config['labs'][lab_id].get('moss', {})
    moss = mosspy.Moss(
        settings.moss_userid,
        moss_settings.get('language')
    )
    if moss_settings.get('max-matches'):
        moss.setIgnoreLimit(moss_settings['max-matches'])
    if moss_settings.get('directory'):
        moss.setDirectoryMode(moss_settings['directory'])
    for basefile in moss_settings.get('basefiles', []):
        if isinstance(basefile, collections.Mapping):
            repo = basefile['repo']
            filename = basefile['filename']
            file_contents = common.github_get_file(repo, filename)
            local_dir = os.path.join(
                local_path,
                *repo.split('/'),
                *filename.split('/')[:-1] if '/' in filename else ""
            )
            os.makedirs(local_dir, exist_ok=True)
            local_filename = os.path.join(local_dir, filename.split('/')[-1])
            with open(local_filename, "wb") as f:
                f.write(file_contents)
        elif isinstance(basefile, str):
            local_filename = basefile
        else:
            raise ValueError(
                "Unknown basefile value type. "
                "Value '{}' of type '{}' is not supported.".format(
                    str(basefile),
                    type(basefile)
                )
            )
        moss.addBaseFile(local_filename)
    # download specific files from repositories
    file_count = 0
    for repo in repos:
        github_account = repo.split('/')[1][len(prefix)+1:]
        for filename in course_config['labs'][lab_id].get('files', []):
            try:
                file_contents = common.github_get_file(repo, filename)
            except:
                continue
            local_dir = os.path.join(
                local_path,
                # repo,
                # "{}-{}".format(prefix, github_account),
                *repo.split('/'),
            )
            # print(local_dir)
            # print(*repo.split('/'))
            print(
                "Downloading file '{}' from GitHub repo '{}' "
                "to directory '{}'...".format(
                    filename,
                    repo,
                    local_dir
                )
            )
            os.makedirs(local_dir, exist_ok=True)
            local_filename = os.path.join(local_dir, filename)
            with open(local_filename, "wb") as f:
                f.write(file_contents)
            dt = common.github_get_latest_commit_date(repo)
            display_name = (f"{lab_id}_{github_account}_"
                f"{filename}_{dt:%Y-%m-%d}")
            moss.addFile(local_filename, display_name)
            file_count += 1
    print(f"Total {file_count} files were downloaded. Sending them to MOSS...")
    # send data to MOSS server
    url = moss.send()
    print("Report URL: " + url)
    # Save report file
    submission_path = os.path.join(local_path, "submission")
    os.makedirs(submission_path, exist_ok=True)
    dt = datetime.datetime.now()
    moss.saveWebPage(
        url,
        os.path.join(submission_path, f"report_{dt:%Y-%m-%d_%H%M%S}.html")
    )
    report_dir = os.path.join(submission_path, f"report_{dt:%Y-%m-%d_%H%M%S}")
    mosspy.download_report(
        url,
        report_dir,
        connections=8,
        log_level=logging.DEBUG
    )
    with open(os.path.join(report_dir, "_link.txt"), 'w') as f:
        # f.write(f"{url}\n")
        print(url, file=f)
    # mossum
    # cli: mossum -m -p 10 -l 10 -a -o lab1/moss_$(date +%Y-%m-%d_%H%M%S) http://moss.stanford.edu/results/3/4482533404111 # noqa
    mossum.args = mossum.parser.parse_args([
        '-m', '-p', '10', '-l', '10',
        '-o', os.path.join(
            local_path,
            f'moss_{dt:%Y-%m-%d_%H%M%S}'
        ),
        url
    ])
    all_res = []
    all_res.append(mossum.get_results(url))
    merged = mossum.merge_results(all_res)
    mossum.image(merged)
    # raise NotImplementedError("This function is not implemented yet!")


def main():
    # parse command line parameters
    params = _parse_args()
    # Python log levels go from 10 (DEBUG) to 50 (CRITICAL),
    # our verbosity argument goes from 0 to 2 (-vv).
    # We never want to suppress error and critical messages,
    # and default to use 30 (WARNING). Hence:
    base_loglevel = getattr(logging, 'WARNING')
    params.verbosity = min(params.verbosity, 2)
    loglevel = base_loglevel - (params.verbosity * 10)
    setup_logging(params.logging_config, default_level=loglevel)
    logger = logging.getLogger(__name__)
    # logger.setLevel(loglevel)
    # load authentication data
    try:
        with open(params.authentication_config) as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)
    except FileNotFoundError:
        logger.warning("Authentication config file '%s' does not exist",
            params.authentication_config)
        config = {}
    # load course description
    try:
        with open(params.course_config, encoding="utf8") as f:
            course_config = yaml.load(f, Loader=yaml.SafeLoader)
    except FileNotFoundError:
        logger.critical("Course config file '%s' does not exist",
            params.course_config)
        # course_config = {}
        raise
    else:
        config.update(course_config)
    if not config.get('auth'):
        raise ValueError("No authentication data found in course config and auth config files")
    # check arguments
    if params.labs == 'all' or params.labs == '*':
        params.labs = config['course']['labs'].keys()
    logger.info(params)
    # perform action
    if "moss" not in params.update_action:
        # initialization
        data_update = []
        # connect to Google Sheets API
        spreadsheet = google_sheets.GoogleSheet(config)
        # # load data from Google Sheets
        # sheets = spreadsheet.get_sheet_names(gs, config)
        # # print(sheets)
        # sheets = ["'{}'".format(s) for s in sheets]
        # data = google_sheets.get_multiple_sheets_data(gs, sheets, config)
        # check email
        if "all" in params.update_action or "email" in params.update_action:
            # connect to IMAP
            imap_conn = mailbox.get_imap_connection(config)
            # process INBOX and update spreadsheet
            data_update = update_students(
                imap_conn, spreadsheet,
                dry_run=params.dry_run,
                valid_subjects=(
                    [config['course']['name']]
                    + config['course']['alt-names']),
                email_config=config['auth']['email'],
                return_address=config['course']['email'])
        # check labs
        if "all" in params.update_action or "labs" in params.update_action:
            for lab_id in params.labs:
                data_update = check_lab(
                    lab_id, spreadsheet.sheets[:-1], spreadsheet,
                    course_config=config['course']
                )
        # update Google SpreadSheet
        if len(data_update) > 0:
            info_sheet = config['course']['google']['info-sheet']
            data_update.append({
                'range': f"'{info_sheet}'!B1",
                # 'majorDimension': dimension,
                'values': [[datetime.datetime.now().isoformat()]]
            })
            logger.info("Data update: %s", data_update)
            # print(data_update)
            if not params.dry_run:
                updated_cells = spreadsheet.batch_update()
                if updated_cells != len(data_update):
                    raise ValueError(
                        f"Number of updated cells ({updated_cells}) differs "
                        "from expected ({len(data_update)})! Check the data "
                        "manually. Data update: {data_update}")
        # add all new repos to AppVeyor
        if ("all" in params.update_action 
            or "appveyor" in params.update_action
        ):
            new_projects = create_appveyor_projects(params.dry_run)
            projects_count = len(new_projects)
            if params.dry_run:
                projects_msg_part = "" if projects_count == 1 else "s"
                projects_msg_part += " would have been"
            else:
                projects_msg_part = " was" if projects_count == 1 else "s were"
            logger.info("%d new AppVeyour project%s "
                  "added: %s", projects_count, projects_msg_part, ';'.join(new_projects))
        # close IMAP connections
        try:
            imap_conn.close()
            imap_conn.logout()
        except Exception:
            pass
    elif "moss" in params.update_action:
        # check labs
        for lab_id in params.labs:
            check_plagiarism(
                lab_id, "lab{}".format(lab_id), 
                moss_user_id=config['auth']['moss']['user-id'],
                course_config=config['course'])


if __name__ == '__main__':
    main()
