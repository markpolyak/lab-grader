#!/usr/bin/env python3

import mailbox
import google_sheets
import common
import settings
import datetime
from dateutil.parser import isoparse, parse
import math
import logging
import logging.config
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
        '-a', '--action', dest='action',
        action='store', default='update',
        choices=['update', 'moss'],
        help="action to be taken: "
             "check for UPDATEs, run MOSS plagiarism check",
    )
    parser.add_argument(
        '-l', '--labs', dest='labs',
        action='store', nargs='+', default='all',
        help="choose labs to be processed, default is all",
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
    parser.add_argument(
        '--ignore-email', dest='ignore_email',
        action='store_true',
        help="do not check for new emails",
    )
    parser.add_argument(
        '--logging-config', dest='logging_config', action='store',
        default=os.path.join(os.path.dirname(os.path.realpath(__file__)),
                             'logging.yaml'),
        help='set logging config file',
    )
    return parser.parse_args()


def update_students(imap_conn, data, data_update=[], dry_run=False, valid_subjects=[], return_address=''):
    """
    """
    # read all new letters in mailbox and extract student info
    print("Processing mailbox...\n")
    students = mailbox.process_students(imap_conn, valid_subjects)
    print(students)
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
            data_update = google_sheets.set_student_github(data, student, data_update=data_update)
        except ValueError as e:
            errmsg = "Unable to process request from student '{}'".format(student['name'])
            print(errmsg)
            print(e)
            email_text = (
                "{}\n\nGroup: {} (raw: {})\nStudent: {}\nGitHub account: {}".format(
                    str(e), 
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
                mailbox.send_email(recepients, errmsg, email_text)
                # flag the message, but leave it as read since we don't want
                # another report to be sent when the script is run next time
                mailbox.mark_flagged(imap_conn, student['uid'])
            else:
                print("An email would have been sent to {}. Subject: {}. Text: {}".format(recepients, errmsg, email_text))
                # set a message as unseen (unread)
                mailbox.mark_unread(imap_conn, student['uid'])
        else:
            if dry_run:
                # set a message as unseen (unread)
                mailbox.mark_unread(imap_conn, student['uid'])
    return data_update


def create_appveyor_projects(dry_run):
    """
    """
    task3_repos = common.get_github_repo_names(settings.github_organization, prefix='os-task3', private=False)
    # print(task3_repos)
    # zz = common.get_appveyor_project_repo_names()
    new_projects = common.add_appveyor_projects_safely(list(task3_repos), trigger_build=True, dry_run=dry_run)
    return new_projects


def check_lab(lab_id, groups, data, data_update=[]):
    """
    """
    prefix = settings.os_labs[lab_id]['github_prefix']
    repos = common.get_github_repo_names(settings.github_organization, prefix)
    deadlines = {}
    lab_id_int = int(lab_id)
    for group in groups:
        deadline_str = google_sheets.get_lab_deadline(data, group, lab_id_int)
        if len(deadline_str.split('.')) == 2:
            deadline_str += '.{} 23:59:59 MSK'.format(datetime.datetime.now().year)
        # print(deadline_str)
        try:
            deadlines[group] = parse(deadline_str, dayfirst=True)
        except ValueError as e:
            deadlines[group] = None
    for repo in repos:
        github_account = repo.split('/')[1][len(prefix)+1:]
        try:
            student = google_sheets.find_student_by_github(data, github_account)
        except ValueError as e:
            # student not found, probably he/she forgot to send a letter with GitHub account info
            print(e)
            continue
        # check if this lab is already accounted for
        current_status = google_sheets.get_student_lab_status(data, student, lab_id_int)
        if current_status is not None and not current_status.startswith('?'):
            # this lab is already accounted for, skip it
            continue

        # check existence of repo_requirements node for lab_id
        if "repo_requirements" in settings.os_labs[lab_id]:
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
                google_sheets.set_student_lab_status(data, student, lab_id_int, "?v*{0:g}".format(grade_coefficient),
                                                     data_update=data_update)
            else:
                # calculated coefficient for this lab is zero, skip it
                continue

        # check if tests have passed successfully
        completion_date = None
        log = None
        if lab_id_int == 3:
            completion_date = common.get_successfull_status_info(repo).get("updated_at")
            if completion_date:
                log = common.get_appveyor_log(repo)
        else:
            completion_date = common.get_successfull_build_info(repo).get("completed_at")
            if completion_date:
                log = common.get_travis_log(repo)
        # check if tests were completed successfully and tests should not be ignored
        if completion_date and not settings.os_labs[lab_id].get('ignore_completion_date', False):
            # log = common.get_travis_log(repo)
            # calculate correct TASKID
            student_task_id = int(google_sheets.get_student_task_id(data, student))
            student_task_id += settings.os_labs[lab_id].get('taskid_shift', 0)
            student_task_id = student_task_id % settings.os_labs[lab_id]['taskid_max']
            if student_task_id == 0:
                student_task_id = settings.os_labs[lab_id]['taskid_max']
            # check TASKID from logs
            if common.get_task_id(log) != student_task_id:
                google_sheets.set_student_lab_status(data, student, lab_id_int, "?! Wrong TASKID!", data_update=data_update)
            else:
                # everything looks good, go on and update lab status
                # calculate grade reduction coefficient
                reduction_coefficient_str = common.get_grade_reduction_coefficient(log)
                if reduction_coefficient_str is not None:
                    grade_reduction_suffix = "*{}".format(reduction_coefficient_str)
                else:
                    grade_reduction_suffix = ""
                # calculate deadline penalty
                student_dt = isoparse(completion_date)
                if student_dt > deadlines[student['group']]:
                    overdue = student_dt - deadlines[student['group']]
                    penalty = math.ceil((overdue.days + overdue.seconds / 86400) / 7)
                    # TODO: check that penalty does not exceed maximum grade points for that lab
                    penalty = min(penalty, settings.os_labs[lab_id].get('penalty_max', 0))
                    penalty_suffix = "-{}".format(penalty)
                else:
                    penalty_suffix = ""
                # update status
                google_sheets.set_student_lab_status(data, student, lab_id_int,
                                                     "v{}{}".format(grade_reduction_suffix, penalty_suffix),
                                                     data_update=data_update)
    return data_update


def check_plagiarism(lab_id, local_path):
    """
    """
    # TODO: this is unfinished function
    prefix = settings.os_labs[lab_id]['github_prefix']
    # get a list of repositories
    repos = common.get_github_repo_names(settings.github_organization, prefix)
    # initialize MOSS
    moss_settings = settings.os_labs[lab_id].get('moss', {})
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
            raise ValueError("Unknown basefile value type. "
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
        for filename in settings.os_labs[lab_id].get('files', []):
            file_contents = common.github_get_file(repo, filename)
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
            display_name = f"{lab_id}_{github_account}_{dt:%Y-%m-%d}"
            moss.addFile(local_filename, display_name)
            file_count += 1
    print(f"Total {file_count} files were downloaded. Sending them to MOSS...")
    # send data to MOSS server
    url = moss.send() 
    print ("Report URL: " + url)
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
    # cli: mossum -m -p 10 -l 10 -a -o lab1/moss_$(date +%Y-%m-%d_%H%M%S) http://moss.stanford.edu/results/3/4482533404111
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
    # enable logging
    setup_logging(params.logging_config)
    logger = logging.getLogger(__name__)
    # load course description
    with open(params.course_config) as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    # check arguments
    if params.labs == 'all' or params.labs == '*':
        params.labs = config['course']['labs'].keys()
    # perform action
    if params.action == "update":
        # initialization
        data_update = []
        # connect to Google Sheets API
        gs = google_sheets.get_spreadsheet_instance(config)
        # load data from Google Sheets
        sheets = google_sheets.get_sheet_names(gs, config)
        # print(sheets)
        sheets = ["'{}'".format(s) for s in sheets]
        data = google_sheets.get_multiple_sheets_data(gs, sheets, config)
        if not params.ignore_email:
            # connect to IMAP
            imap_conn = mailbox.get_imap_connection(config)
            # process INBOX and update spreadsheet
            data_update = update_students(
                imap_conn, data, 
                data_update=data_update, 
                dry_run=params.dry_run,
                valid_subjects=([config['course']['name']] + config['course']['alt-names']),
                return_address=config['course']['email'])
        # check labs
        for lab_id in params.labs:
            data_update = check_lab(lab_id, sheets[:-1], data, data_update=data_update)
        # update Google SpreadSheet
        if len(data_update) > 0:
            data_update.append({
                'range': "'План'!B1",
                # 'majorDimension': dimension,
                'values': [[datetime.datetime.now().isoformat()]]
            })
            print(data_update)
            if not params.dry_run:
                updated_cells = google_sheets.batch_update(gs, data_update, config)
                if updated_cells != len(data_update):
                    raise ValueError("Number of updated cells ({}) differs from expected ({})! Check the data manually. Data update: {}".format(updated_cells, len(data_update), data_update))
        # add all new os-task3 repos to AppVeyor
        # if not params.dry_run:
        #     new_projects = create_appveyor_projects()
        #     print("{} new AppVeyour projects were added".format(len(new_projects)))
        new_projects = create_appveyor_projects(params.dry_run)
        projects_count = len(new_projects)
        if params.dry_run:
            projects_msg_part = "" if projects_count == 1 else "s"
            projects_msg_part += " would have been"
        else:
            projects_msg_part = " was" if projects_count == 1 else "s were"
        print(
            "{} new AppVeyour project{} added: {}".format(
                projects_count, 
                projects_msg_part,
                ";".join(new_projects)
            )
        )
        # if params.dry_run:
        #     print(
        #         "{} new AppVeyour projects would have been added: {}.".format(
        #             len(new_projects),
        #             ";".join(new_projects)
        #         )
        #     )
        # else:
        #     print(
        #         "{} new AppVeyour project{} added: {}".format(
        #             projects_count,
        #             " was" if projects_count == 1 else "s were",
        #             ";".join(new_projects)
        #         )
        #     )
        
        # close IMAP connections
        try:
            imap_conn.close()
            imap_conn.logout()
        except:
            pass
    elif params.action == "moss":
        # check labs
        for lab_id in params.labs:
            check_plagiarism(lab_id, "lab{}".format(lab_id))


if __name__ == '__main__':
    main()
