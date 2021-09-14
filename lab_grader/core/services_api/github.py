import sys
import requests

from lab_grader.core.common import requests_retry_session

import json
import datetime
from oauth2client.service_account import ServiceAccountCredentials
# import gspread
from lab_grader import load_config


class GitHub:
    def __init__(self, requests_timeout, auth: dict):
        self.token = None
        self.requests_timeout = requests_timeout
        self.__dict__.update(**auth)
        self.travis_token = self.__get_travis_token()

    # get a token for Travis API v 2.1 using an existing GitHub token
    def __get_travis_token(self, private=True):
        api_url = "https://api.travis-ci.{}/auth/github"
        travis_token_request = {
            "github_token": self.token
        }
        res = requests.post(
            api_url.format("com" if private else "org"),
            data=travis_token_request
        )
        if res.status_code != 200:
            raise Exception(
                "Travis API reported an error while trying to get a {} API token using GitHub token authentication! Message is '{}' ({}).".format(
                    "private" if private else "public", res.reason, res.status_code))
        return json.loads(res.content).get("access_token")

    # get repository list from github
    def get_github_repos(self, org, prefix=None, private=None, verbose=False):
        all_repos_list = []
        page_number = 1
        request_headers = {
            "User-Agent": "GitHubRepoLister/1.0",
            "Authorization": "token " + self.token,
        }
        while True:
            if verbose:
                sys.stdout.write('../..')
                sys.stdout.flush()
            repos_page = requests_retry_session().get(
                "https://api.github.com/orgs/{}/repos?page={}".format(
                    org, page_number
                ),
                headers=request_headers,
                timeout=self.requests_timeout
            )
            page_number = page_number + 1
            if repos_page.status_code != 200:
                print(repos_page.status_code)
                print(repos_page.content)
                raise Exception("Failed to load repos from GitHub: " + str(repos_page.content))
                # exit(1)
            repos_page_json = repos_page.json()
            if len(repos_page_json) == 0:
                # print(" Done.")
                break
            all_repos_list = all_repos_list + repos_page.json()
        if verbose:
            sys.stdout.write('\n')
        if private is not None:
            all_repos_list = [x for x in all_repos_list if x['private'] == private]
        if prefix is not None:
            filtered_repo_list = [x for x in all_repos_list if x['name'].startswith(prefix)]
            return filtered_repo_list
        else:
            return all_repos_list
        # for repo in all_repos_list:
        #     print(repo['name'])
        # print( "%d of %d repos start with %s" % (len(filteredRepoList), len(allReposList), githubPrefix))

    # get a set of github repository names with a given prefix
    def get_github_repo_names(self, org, prefix=None, private=None):
        repos = self.get_github_repos(org, prefix, private)
        return set([x['full_name'] for x in repos])

    def get_github_repo_default_branch(self, repo):
        """
        Retrieves default branch name for repository from GitHub

        :param repo: repository name (with organization/owner prefix)
        :returns: default branch name
        """
        default_branch_headers = {
            "User-Agent": "GitHubDefaultBranchDetector/1.0",
            "Authorization": "token " + self.token,
            "Accept": "application/vnd.github.antiope-preview+json",
        }
        res = requests_retry_session().get(
            "https://api.github.com/repos/{}".format(
                repo
            ),
            headers=default_branch_headers,
            timeout=self.requests_timeout
        )
        if res.status_code != 200:
            raise Exception(
                "GitHub API reported an error while trying to get info for repository '{}'! Message is '{}' ({}).".format(
                    repo, res.reason, res.status_code))
        return json.loads(res.content).get("default_branch")

    def github_user_exists(self, username):
        """
        Check if a GitHub user exists

        :param username: github username to search for
        :returns: True if user exists, False otherwise
        """
        # https://api.github.com/search/users?q=user:username
        request_headers = {
            "User-Agent": "GitHubUserValidator/1.0",
            "Authorization": "token " + self.token,
        }
        res = requests_retry_session().get(
            'https://api.github.com/search/users?q=user:{}'.format(username),
            headers=request_headers,
            timeout=self.requests_timeout
        )
        if res.status_code != 200:
            raise ValueError("Failed to load user '{}' from GitHub: {}".format(username, res.content))
            # return False
        data = json.loads(res.content)
        if data.get('total_count') == 1:
            return True
        else:
            return False

    #
    def get_github_check_runs(self, repo):
        check_runs_headers = {
            "User-Agent": "GitHubCheckRuns/1.0",
            "Authorization": "token " + self.token,
            "Accept": "application/vnd.github.antiope-preview+json",
        }
        default_branch = self.get_github_repo_default_branch(repo)
        res = requests_retry_session().get(
            "https://api.github.com/repos/{}/commits/{}/check-runs".format(
                repo, default_branch
            ),
            headers=check_runs_headers,
            timeout=self.requests_timeout
        )
        if res.status_code != 200:
            raise Exception(
                "GitHub API reported an error while trying to get check run info for repository '{}'! Message is '{}' ({}).".format(
                    repo, res.reason, res.status_code))
        return json.loads(res.content).get("check_runs")

    #
    def get_github_commits_by_branch(self, repo: str, branch: str = "master"):
        """
        get commit list from GitHub for provided repository and branch

        :param repo: repository name (with organization/owner prefix)
        :param branch: git branch name (default - "master")
        :return: list of commits, constructed from response JSON
        """
        commits_headers = {
            "User-Agent": "GitHubCommits/1.0",
            "Authorization": "token " + self.token,
            "Accept": "application/vnd.github.v3+json",
        }
        res = requests_retry_session().get(
            "https://api.github.com/repos/{}/commits?sha={}".format(repo, branch),
            headers=commits_headers,
            timeout=self.requests_timeout
        )
        if res.status_code != 200:
            raise Exception(
                "GitHub API reported an error while trying to get commits for repository '{}' at branch '{}'! Message is '{}' ({}).".format(
                    repo, branch, res.reason, res.status_code))
        return json.loads(res.content)

    #
    def get_github_commit_by_sha(self, repo: str, sha: str):
        """
        get commit from GitHub for provided repository and commit sha

        :param repo: repository name (with organization/owner prefix)
        :param sha: sha of commit
        :return: commit object, constructed from response JSON
        """
        commit_headers = {
            "User-Agent": "GitHubCommits/1.0",
            "Authorization": "token " + self.token,
            "Accept": "application/vnd.github.v3+json",
        }
        res = requests_retry_session().get(
            "https://api.github.com/repos/{}/commits/{}".format(repo, sha),
            headers=commit_headers,
            timeout=self.requests_timeout
        )
        if res.status_code != 200:
            raise Exception(
                "GitHub API reported an error while trying to get commit for repository '{}' by sha '{}'! Message is '{}' ({}).".format(
                    repo, sha, res.reason, res.status_code))
        return json.loads(res.content)

    #
    def get_github_issues(self, repo: str):
        """
        get issues from GitHub for provided repository (exclude pull requests)

        :param repo: repository name (with organization/owner prefix)
        :return: list of issues, constructed from response JSON
        """
        issues_headers = {
            "User-Agent": "GitHubIssues/1.0",
            "Authorization": "token " + self.token,
            "Accept": "application/vnd.github.v3+json",
        }
        res = requests_retry_session().get(
            "https://api.github.com/repos/{}/issues".format(repo),
            headers=issues_headers,
            timeout=self.requests_timeout
        )
        if res.status_code != 200:
            raise Exception(
                "GitHub API reported an error while trying to get issues for repository '{}'! Message is '{}' ({}).".format(
                    repo, res.reason, res.status_code))
        # removing pull requests from issue list
        return [issue for issue in json.loads(res.content) if 'pull_request' not in issue]

    #
    def get_github_issue_events(self, repo: str, issue_number: str):
        """
        get issue events from GitHub for provided repository by issue number

        :param repo: repository name (with organization/owner prefix)
        :param issue_number: number of issue
        :return: list of issue events, constructed from response JSON
        """
        issue_events_headers = {
            "User-Agent": "GitHubIssueEvents/1.0",
            "Authorization": "token " + self.token,
            "Accept": "application/vnd.github.v3+json",
        }
        res = requests_retry_session().get(
            "https://api.github.com/repos/{}/issues/{}/events".format(repo, issue_number),
            headers=issue_events_headers,
            timeout=self.requests_timeout
        )
        if res.status_code != 200:
            raise Exception(
                "GitHub API reported an error while trying to get issue #{} events for repository '{}'! Message is '{}' ("
                "{}).".format(
                    issue_number, repo, res.reason, res.status_code))
        return json.loads(res.content)

    #
    def get_github_issue_referenced_events(self, repo: str, issue_number: str):
        """
        get issue events with referenced (commit linking) type from GitHub for provided repository by issue number

        :param repo: repository name (with organization/owner prefix)
        :param issue_number: number of issue
        :return: list of referenced type issue events, constructed from response JSON
        """
        events = self.get_github_issue_events(repo, issue_number)
        return [event for event in events if event['event'] == "referenced"]

    #
    def get_successfull_build_info(self, repo, check_run_names, all_successfull=False):
        check_runs = self.get_github_check_runs(repo)
        latest_check_run = {}
        for check_run in check_runs:
            if all_successfull and check_run.get("conclusion") != "success":
                return {}
            if (
                    any(name in check_run.get("name") for name in check_run_names)
                    and check_run.get("conclusion") == "success"
                    and check_run.get("completed_at", "") > latest_check_run.get("completed_at", "")
            ):
                # return check_run
                latest_check_run = check_run
        return latest_check_run

    #
    def get_github_workflows_log(self, repo, check_run_names):
        """
        get log from github workflows

        :param repo: repository name (with organization/owner prefix)
        :return: log
        """
        # from observation of GitHub API output the 'id' parameter of a check run
        # is identical to the job id of a corresponding workflow;
        # so, instead of doing the following sequence:
        # - retrieving a list of action runs from
        # https://api.github.com/repos/{repo}/actions/runs
        # - looking for a job id for the most recent workflow run
        # and retrieving it from "jobs_url" of the workflow run
        # https://api.github.com/repos/{repo}/actions/runs/{workflow_run_id}/jobs # noqa
        # - retrieving a log URL from "Location" header in response to the query
        # https://api.github.com/repos/{repo}/actions/jobs/{job_id}/logs
        # - downloading the log from the URL in the "Location" header above;
        # we get the check run id and use it instead of the job id,
        # skipping several steps.
        # WARNING! This is undocumented by GitHub and
        # might stop working in the future
        job_id = self.get_successfull_build_info(repo, check_run_names).get("id")
        if not job_id:
            raise Exception("Unable to get job id from GitHub API check runs")
        workflows_headers = {
            "User-Agent": "GitHubWorkflowsLog/1.0",
            "Authorization": "token " + self.token,
            "Accept": "application/vnd.github.v3+json",
        }
        res = requests_retry_session().get(
            "https://api.github.com/repos/{}/actions/jobs/{}/logs".format(
                repo, job_id
            ),
            headers=workflows_headers,
            timeout=self.requests_timeout
        )
        # # no need to run the code below, because if 'Location' header is present,
        # # requests will automatically redirect and load logs from that URL
        # if res.status_code != 302:
        #     raise Exception(
        #         "GitHub API reported an error while trying to get "
        #         "workflow run job {} for repository '{}'! Message is '{}' ("
        #         "{}).".format(
        #             job_id, repo, res.reason, res.status_code))
        # logs_url = res.headers.get('Location')
        # if not logs_url:
        #     raise Exception(
        #         "Logs for job {} in repository '{}' not found!".format(
        #             job_id, repo))
        #
        # res = requests_retry_session().get(
        #     logs_url,
        #     headers=workflows_headers,
        #     timeout=self.requests_timeout
        # )
        if res.status_code == 410:
            # log already deleted
            # TODO: logger.warning()
            return ""
        if res.status_code != 200:
            raise Exception(
                "GitHub API reported an error while trying to get "
                "build log for job {} for repository '{}'! "
                "Message is '{}' ({}).".format(
                    job_id, repo, res.reason, res.status_code))
        return res.content.decode('utf-8')

    #
    def get_travis_log(self, repo, check_run_names):
        # check_runs_headers = {
        #     "User-Agent": "GitHubCheckRuns/1.0",
        #     "Authorization": "token " + self.token,
        # }
        # res = requests.get(
        #     "https://api.github.com/repos/{}/commits/master/check-runs".format(repo),
        #     headers=check_runs_headers
        # )
        # if res.status_code != 200:
        #     raise Exception("GitHub API reported an error while trying to get check run info for repository '{}'! Message is '{}' ({}).".format(repo, res.reason, res.status_code))
        # check_runs = json.loads(res.content).get("check_runs", [])
        # check_runs = get_github_check_runs(repo)
        # travis_build = None
        # completion_time = None
        # for check_run in check_runs:
        #     if (
        #         "Travis CI" in check_run.get("name")
        #         and check_run.get("conclusion") == "success"
        #     ):
        #         travis_build = check_run.get("external_id")
        #         completion_time = check_run.get("completed_at")
        #         break
        travis_build = self.get_successfull_build_info(repo, check_run_names).get("external_id")
        if not travis_build:
            return None
        #
        # travis_token = get_travis_token()
        #
        travis_headers = {
            "Travis-API-Version": "3",
            "User-Agent": "API Explorer",
            "Authorization": "token " + self.travis_token,
        }
        res = requests.get(
            "https://api.travis-ci.com/build/{}".format(travis_build),
            headers=travis_headers
        )
        if res.status_code != 200:
            raise Exception(
                "Travis API reported an error while trying to get build info for build {} (repository '{}')! Message is '{}' ({}).".format(
                    travis_build, repo, res.reason, res.status_code))
        job_id = json.loads(res.content).get("jobs", [{}])[-1].get("id")
        if job_id is None:
            raise Exception("No valid job ID found for build {} (repository '{}').".format(travis_build, repo))
        res = requests.get(
            "https://api.travis-ci.com/job/{}/log".format(job_id),
            headers=travis_headers
        )
        if res.status_code != 200:
            raise Exception(
                "Travis API reported an error while trying to get build log for job {} (build {} for repository '{}')! Message is '{}' ({}).".format(
                    job_id, travis_build, repo, res.reason, res.status_code))
        return json.loads(res.content).get("content")

    def get_successfull_status_info(self, repo):
        """
        Extract info about successfull AppVeyor build from GitHub repository

        :param repo: github repository
        :returns: repository status info for successfull AppVeyor build
        """
        status_headers = {
            "User-Agent": "GitHubCheckRuns/1.0",
            "Authorization": "token " + self.token,
            "Accept": "application/vnd.github.antiope-preview+json",
        }
        res = requests_retry_session().get(
            "https://api.github.com/repos/{}/commits/master/status".format(repo),
            headers=status_headers,
            timeout=self.requests_timeout
        )
        if res.status_code != 200:
            raise Exception(
                "GitHub API reported an error while trying to get status info "
                "for repository '{}'! Message is '{}' ({}).".format(
                    repo, res.reason, res.status_code
                )
            )
        status = json.loads(res.content)
        if status["state"] != "success":
            return {}
        for st in status["statuses"]:
            if st["state"] == "success" and "AppVeyor" in st["description"]:
                return st
        return {}

    #
    def get_repo_issues_grade_coefficient(self, course_config, repo: str, lab_id: str):
        """
        get grade coefficient for provided repository and lab id by checking repository issues requirements

        :param repo: repository name (with organization/owner prefix)
        :param lab_id: id of lab
        :return: None or float coefficient (which can be 0.0)
        """

        if "issue" not in course_config.os_labs[lab_id]['repo_requirements']:
            return None

        # get prefix
        if "github-prefix" in course_config['labs'][lab_id]:
            prefix = course_config['labs'][lab_id]['github-prefix']
        else:
            prefix = None

        # get linked commit message part
        if "linked_commit_msg_part" in course_config.os_labs[lab_id]['repo_requirements']['issue']:
            linked_commit_msg_part = course_config.os_labs[lab_id]['repo_requirements']['issue']['prefix']
        else:
            linked_commit_msg_part = None

        # get issues min quantity from settings (mandatory)
        if "min_quantity" in course_config.os_labs[lab_id]['repo_requirements']['issue']:
            min_quantity = course_config.os_labs[lab_id]['repo_requirements']['issue']['min_quantity']
        else:
            min_quantity = None

        # get grade percent from settings (mandatory)
        if "grade_percent" in course_config.os_labs[lab_id]['repo_requirements']['issue']:
            grade_percent = course_config.os_labs[lab_id]['repo_requirements']['issue']['grade_percent']
        else:
            grade_percent = None

        # check acquired lab settings
        if grade_percent is None or min_quantity is None:
            return None

        # get repo issues from github
        if prefix is None:
            repo_issues = self.get_github_issues(repo)
        else:
            repo_issues = [issue for issue in self.get_github_issues(repo) if issue['title'].startswith(prefix)]

        # if issues number less than required quantity -> return 0.0
        if len(repo_issues) < int(min_quantity):
            return 0.0

        correct_issue_number: int = 0
        for repo_issue in repo_issues:
            # get current issue number
            current_issue_number: str = str(repo_issue['number'])

            # get referenced (commit) events for current issue with next checks:
            # 1) event actor's login is not belongs to teacher
            # 2) "commit_id" field is not empty (contains SHA of the commit)
            # 3) provided repo name contains in commit URL
            student_commit_events_for_issue = [event for event in
                                               self.get_github_issue_referenced_events(repo, current_issue_number)
                                               if event['actor']['login'] not in course_config.teacher_github_logins
                                               and event['commit_id'] is not None
                                               and repo in event['commit_url']]
            if len(student_commit_events_for_issue) == 0:
                student_commit_events_for_issue = [

                ]

            if len(student_commit_events_for_issue) >= 1:
                if linked_commit_msg_part is not None:
                    linked_commits_sha = [event['commit_id'] for event in student_commit_events_for_issue]
                    linked_commits = [commit for commit in
                                      [self.get_github_commit_by_sha(repo, sha) for sha in linked_commits_sha]
                                      if linked_commit_msg_part in commit['commit']['message']]
                    if len(linked_commits) >= 1:
                        correct_issue_number += 1
                else:
                    correct_issue_number += 1

        if correct_issue_number >= int(min_quantity):
            return float(int(grade_percent) / 100)
        else:
            return 0.0

    #
    def get_repo_commit_grade_coefficient(self, course_config, repo: str, lab_id: str):
        """
        get grade coefficient for provided repository and lab id by checking repository commits requirements

        :param repo: repository name (with organization/owner prefix)
        :param lab_id: id of lab
        :return: None or float coefficient (which can be 0.0)
        """

        if "commit" not in course_config.os_labs[lab_id]['repo_requirements']:
            return None

        # get commit message part
        if "msg_part" in course_config.os_labs[lab_id]['repo_requirements']['commit']:
            msg_part = course_config.os_labs[lab_id]['repo_requirements']['commit']['msg_part']
        else:
            msg_part = None

        # get issues min quantity from settings
        if "min_quantity" in course_config.os_labs[lab_id]['repo_requirements']['commit']:
            min_quantity = course_config.os_labs[lab_id]['repo_requirements']['commit']['min_quantity']
        else:
            min_quantity = None

        # get grade percent
        if "grade_percent" in course_config.os_labs[lab_id]['repo_requirements']['commit']:
            grade_percent = course_config.os_labs[lab_id]['repo_requirements']['commit']['grade_percent']
        else:
            grade_percent = None

        # check acquired lab settings
        if grade_percent is None or min_quantity is None:
            return None

        # get repo commits from github
        repo_commits = self.get_github_commits_by_branch(repo)

        # get commits and removing authored by teacher
        student_commits = [commit for commit in repo_commits
                           if commit['author']['login'] not in course_config.teacher_github_logins]

        if msg_part is not None:
            commits_with_prefix = [commit for commit in student_commits if msg_part in commit['commit']['message']]
            commits_number: int = len(commits_with_prefix)
        else:
            commits_number: int = len(student_commits)

        if commits_number >= int(min_quantity):
            return float(int(grade_percent) / 100)
        else:
            return 0.0

    def github_get_file(self, repo, filepath):
        """
        get a single file from GitHub

        :param repo: repository name (with organization/owner prefix)
        :param filepath: path and file name of the file to be retrieved
        :returns: file contents as a bytes string
        """
        # https://gist.github.com/Integralist/9482061
        status_headers = {
            "User-Agent": "GitHubGetFile/1.0",
            "Authorization": "token " + self.token,
            "Accept": "application/vnd.github.v3.raw",
        }
        res = requests_retry_session().get(
            "https://api.github.com/repos/{}/contents/{}".format(repo, filepath),
            headers=status_headers,
            timeout=self.requests_timeout
        )
        if res.status_code != 200:
            raise Exception(
                "GitHub API reported an error while trying to get file '{}' from repository '{}'! Message is '{}' ({}).".format(
                    filepath, repo, res.reason, res.status_code))
        return res.content

    def github_get_latest_commit_date(self, repo):
        """
        get the latest commit timestamp to a GitHub repository

        :param repo: repository name (with organization/owner prefix)
        :returns: date of the latest commit
        """
        status_headers = {
            "User-Agent": "GitHubGetLatestCommitDate/1.0",
            "Authorization": "token " + self.token,
            "Accept": "application/vnd.github.v3.raw",
        }
        res = requests_retry_session().get(
            "https://api.github.com/repos/{}".format(repo),
            headers=status_headers,
            timeout=self.requests_timeout
        )
        if res.status_code != 200:
            raise Exception(
                "GitHub API reported an error while trying to get info about repository '{}'! Message is '{}' ({}).".format(
                    repo, res.reason, res.status_code))
        pushed_at = json.loads(res.content).get("pushed_at")
        return datetime.datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))