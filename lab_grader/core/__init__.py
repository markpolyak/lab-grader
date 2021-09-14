import logging
import logging.config
from lab_grader import load_config, PathConfig
import lab_grader.utils.mailbox as mailbox
import lab_grader.utils.google_sheets as google_sheets
import lab_grader.core.common as common
import datetime
from dateutil.parser import isoparse, parse
import math
import os
import time
import uuid

import collections

import mosspy
from mossum import mossum

from lab_grader.core.services_api import ServicesApi


# logger = logging.getLogger(__name__)


class Grader:
    config = dict()

    def __init__(self, course_config=None, dry_run=False, logs_vv=None):
        self.paths = PathConfig()
        self.__auth_config = load_config(path_to_yaml=self.paths.auth_config)
        self.course_config = course_config
        self.__class__.config.update(self.__auth_config)
        if self.course_config or not isinstance(course_config, dict):
            self.course_config = load_config(path_to_yaml="{}/{}".format(self.paths.courses_path, course_config))
            self.__class__.config.update(self.course_config)
        else:
            raise ValueError("Expect course config as dict")
        self.api = ServicesApi(auth_config=self.__auth_config)
        self.logfile_uuid = self.__setup_logging()
        self.dry_run = dry_run
        self.logs_vv = logs_vv

    # config getter for external methods
    def get_config(self) -> dict:
        return self.__class__.config

    def __setup_logging(self) -> str:
        base_loglevel = getattr(logging, 'WARNING')
        verbosity = 2 if self.logs_vv else 0
        default_loglevel = base_loglevel - (verbosity * 10)

        formatter = logging.Formatter(
            "%(asctime)s - [%(levelname)s] -  %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s")
        root = logging.getLogger()
        root.setLevel(default_loglevel)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(default_loglevel)
        root.addHandler(stream_handler)

        logfile_uuid = str()
        if self.logs_vv:
            logfile_uuid = str(uuid.uuid4())
            log_file = "{}/{}.log".format(self.paths.log_path, logfile_uuid)
            file_handler = logging.handlers.WatchedFileHandler(log_file, 'w')
            file_handler.setFormatter(formatter)
            file_handler.setLevel(default_loglevel)
            root.addHandler(file_handler)

        return logfile_uuid

    def update_students(self, imap_conn, spreadsheet):
        """
        """

        def get_valid_subjects(course_config):
            return [course_config['name'], course_config['alt-names']]

        logger = logging.getLogger(__name__)
        # read all new letters in mailbox and extract student info
        logger.info("Processing mailbox...")
        students = mailbox.process_students(imap_conn,
                                            get_valid_subjects(course_config=self.course_config))

        logger.debug("New students from mailbox: %s", students)
        # validate student info and add to data
        for student in students:
            try:
                # GitHub API has a rate limit of 10 queries per minute for
                # unauthenticated users and 30 queries per minute for auth users,
                # see https://docs.github.com/en/free-pro-team@latest/rest/reference/search#rate-limit # noqa
                time.sleep(2.1)
                # check if github user exists (e.g. there are no obvious typos)
                if not self.api.github.github_user_exists(student['github']):
                    raise ValueError(
                        "User '{}' not found on GitHub. Check your spelling or contact course staff.".format(
                            student['github']))
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
                recepients = [student['email'], self.course_config['email']]
                if not self.dry_run:
                    # send a report
                    mailbox.send_email(recepients, errmsg, email_text, self.__class__.config['auth']['email'])
                    # flag the message, but leave it as read since we don't want
                    # another report to be sent when the script is run next time
                    mailbox.mark_flagged(imap_conn, student['uid'])
                else:
                    logger.warning("An email would have been sent to %s. Subject: %s. Text: %s", recepients, errmsg,
                                   email_text)
                    # print("An email would have been sent to {}. Subject: {}. Text: {}".format(recepients, errmsg, email_text))
                    # set a message as unseen (unread)
                    mailbox.mark_unread(imap_conn, student['uid'])
            else:
                if self.dry_run:
                    # set a message as unseen (unread)
                    mailbox.mark_unread(imap_conn, student['uid'])
        return spreadsheet.data_update

    # no usage of method found
    """def create_appveyor_projects(self, dry_run):
        # must use yaml confif here, not settings !
        task3_repos = common.get_github_repo_names(settings.github_organization, prefix='os-task3', private=False)
        # print(task3_repos)
        # zz = common.get_appveyor_project_repo_names()
        new_projects = common.add_appveyor_projects_safely(list(task3_repos), trigger_build=True, dry_run=dry_run)
        return new_projects"""

    def check_lab(self, lab_id, groups, spreadsheet):
        """
        """
        logger = logging.getLogger(__name__)
        logger.info("Performing check on lab %s", lab_id)
        prefix = self.course_config['labs'][lab_id]['github-prefix']
        repos = self.api.github.get_github_repo_names(self.course_config['github']['organization'], prefix)
        logger.debug("Found %d repos with %s prefix: %s", len(repos), prefix, repos)
        deadlines = {}
        lab_id_int = int(lab_id)
        lab_id_column = self.course_config['labs'][lab_id].get('short-name', lab_id_int)
        for group in groups:
            deadline_str = spreadsheet.get_lab_deadline(group, lab_id_column)
            if deadline_str:
                # add year if it is missing
                if len(deadline_str.split('.')) == 2:
                    deadline_str += '.{}'.format(datetime.datetime.now().year)
                # add hours, minutes and seconds based on Moscow time
                deadline_str += ' 23:59:59 ' + self.course_config.get('timezone', 'UTC')
                # print(deadline_str)
            try:
                deadlines[group] = parse(deadline_str, dayfirst=True)
            except (ValueError, TypeError):
                deadlines[group] = None
        # if logger.isEnabledFor(logging.DEBUG):
        #     logger.debug("Deadlines for lab %s are: %s", lab_id, {k:v.isoformat() for (k, v) in deadlines.items()})
        for repo in repos:
            github_account = repo.split('/')[1][len(prefix) + 1:]
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
            if "repo_requirements" in self.course_config['labs'][lab_id]:
                grade_coefficient: float = 0.0

                # computing grade coefficient by commits
                commit_grade_coefficient = self.api.github.get_repo_commit_grade_coefficient(self.course_config, repo,
                                                                                             lab_id)
                if commit_grade_coefficient is not None:
                    grade_coefficient += commit_grade_coefficient

                # computing grade coefficient by issues
                issues_grade_coefficient = self.api.github.get_repo_issues_grade_coefficient(self.course_config, repo,
                                                                                             lab_id)
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
            # TODO: we should iterate over all ci services found in the config, but for now only the first ci service is processed
            # ci_service = course_config['labs'][lab_id].get('ci', [''])[0]
            for ci_service in self.course_config['labs'][lab_id].get('ci', ['']):
                logger.debug("Performing check for '%s' data in %s", ci_service, repo)
                completion_date = None
                log = None
                # TODO: check_run names should come from course yaml file. Replace the lists below with this parameter
                if ci_service == 'appveyor':
                    completion_date = self.api.github.get_successfull_status_info(repo).get("updated_at")
                    if completion_date:
                        log = self.api.appveyor.get_appveyor_log(repo)
                elif ci_service == 'travis':
                    completion_date = self.api.github.get_successfull_build_info(repo, ["Travis CI"]).get("completed_at")
                    if completion_date:
                        log = self.api.github.get_travis_log(repo, ["Travis CI"])
                elif ci_service == 'workflows':
                    completion_date = self.api.github.get_successfull_build_info(
                        repo, ["Autograding", "test", "build"], all_successfull=True
                    ).get("completed_at")
                    if completion_date:
                        log = self.api.github.get_github_workflows_log(repo, ["Autograding", "test", "build"])
                # TODO: add support for not using any CI/CD service at all, e.g.:
                elif ci_service == '':
                    # do something
                    pass
                else:
                    raise ValueError(f"Unsupported CI/CD service '{ci_service}' for lab {lab_id} found")
                logger.debug("Completion date for %s with %s is %s", repo, ci_service, completion_date)
                # check if tests were completed successfully and tests should not be ignored
                if completion_date and \
                        not self.course_config['labs'][lab_id].get('ignore-completion-date', False):
                    # calculate correct TASKID
                    student_task_id = int(spreadsheet.get_student_task_id(student))
                    student_task_id += self.course_config['labs'][lab_id].get('taskid-shift', 0)
                    student_task_id = student_task_id % self.course_config['labs'][lab_id]['taskid-max']
                    if student_task_id == 0:
                        student_task_id = self.course_config['labs'][lab_id]['taskid-max']
                    # check TASKID from logs
                    if common.get_task_id(log) != student_task_id and \
                            not self.course_config['labs'][lab_id].get('ignore-task-id', False):
                        spreadsheet.set_student_lab_status(student, lab_id_column, "?! Wrong TASKID!")
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
                        penalty_suffix = ""
                        # BUG: TypeError: can't compare offset-naive and offset-aware datetimes
                        # if student_dt > deadlines[student['group']]:
                        print(student_dt)
                        print(deadlines[student['group']])
                        if student_dt.replace(tzinfo=None) > deadlines[student['group']].replace(tzinfo=None):
                            overdue = student_dt.replace(tzinfo=None) - deadlines[student['group']].replace(tzinfo=None)
                            penalty = math.ceil((overdue.days + overdue.seconds / 86400) / 7)
                            # TODO: check that penalty does not exceed maximum grade points for that lab
                            penalty = min(penalty,
                                          self.course_config['labs'][lab_id].get('penalty-max', 0))
                            if penalty > 0:
                                penalty_suffix = "-{}".format(penalty)
                            # print(f"{student_dt}, {deadlines[student['group']]}")
                            # print(f"{overdue}, {penalty}")
                        # update status
                        lab_status = "v{}{}".format(grade_reduction_suffix, penalty_suffix)
                        logger.debug("New status for lab '%s' by student '%s' is '%s' from CI service '%s'", lab_id,
                                     student, lab_status, ci_service)
                        spreadsheet.set_student_lab_status(
                            student, lab_id_column, lab_status,
                        )
                    # correct solution found, don't iterate over other ci services
                    break
                else:
                    logger.debug("No valid solution found for lab '%s' by student %s with CI service '%s'", lab_id,
                                 student,
                                 ci_service)
        return spreadsheet.data_update

    def check_plagiarism(self, lab_id, local_path):
        """
        """
        # TODO: this is unfinished function
        prefix = self.course_config['labs'][lab_id]['github-prefix']
        # get a list of repositories
        repos = self.api.github.get_github_repo_names(
            self.course_config['github']['organization'], prefix)
        # initialize MOSS
        moss_settings = self.course_config['labs'][lab_id].get('moss', {})
        moss = mosspy.Moss(
            self.__auth_config['moss_userid'],
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
                file_contents = self.api.github.github_get_file(repo, filename)
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
            github_account = repo.split('/')[1][len(prefix) + 1:]
            for filename in self.course_config['labs'][lab_id].get('files', []):
                try:
                    file_contents = self.api.github.github_get_file(repo, filename)
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
                dt = self.api.github.github_get_latest_commit_date(repo)
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

    def spreadsheet_update(self, spreadsheet, data_update):
        logger = logging.getLogger()
        # update Google SpreadSheet
        if len(data_update) > 0:
            info_sheet = self.course_config['google']['info-sheet']
            data_update.append({
                'range': f"'{info_sheet}'!B1",
                # 'majorDimension': dimension,
                'values': [[datetime.datetime.now().isoformat()]]
            })
            logger.info("Data update: %s", data_update)
            # print(data_update)
            if not self.dry_run:
                updated_cells = spreadsheet.batch_update()
                if updated_cells != len(data_update):
                    raise ValueError(
                        f"Number of updated cells ({updated_cells}) differs "
                        "from expected ({len(data_update)})! Check the data "
                        "manually. Data update: {data_update}")

    def check_emails(self):
        logger = logging.getLogger()
        # connect to Google Sheets API
        spreadsheet = google_sheets.GoogleSheet(self.__class__.config)

        # connect to IMAP
        imap_conn = mailbox.get_imap_connection(self.__class__.config)
        # process INBOX and update spreadsheet
        data_update = self.update_students(imap_conn, spreadsheet)

        self.spreadsheet_update(spreadsheet, data_update)

        handlers = list(logger.handlers)
        for hand in handlers:
            logger.removeHandler(hand)
            hand.flush()
            hand.close()

        return self.logfile_uuid

    def check_labs(self, labs_count):
        base_loglevel = getattr(logging, 'WARNING')
        verbosity = 2 if self.logs_vv else 0
        loglevel = base_loglevel - (verbosity * 10)
        logger = logging.getLogger(loglevel)

        data_update = []
        # connect to Google Sheets API
        spreadsheet = google_sheets.GoogleSheet(self.__class__.config)
        # load data from Google Sheets

        if labs_count == 'all' or labs_count == '*':
            labs_count = self.course_config['labs'].keys()

        # check labs
        for lab_id in labs_count:
            data_update = self.check_lab(
                lab_id, spreadsheet.sheets[:-1], spreadsheet)

        self.spreadsheet_update(spreadsheet, data_update)

        handlers = list(logger.handlers)
        for hand in handlers:
            logger.removeHandler(hand)
            hand.flush()
            hand.close()

        return self.logfile_uuid
