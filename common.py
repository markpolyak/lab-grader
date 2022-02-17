import sys
import requests

from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

import json
import datetime
from oauth2client.service_account import ServiceAccountCredentials
# import gspread
import settings


APPVEYOR_PROJECTS_API_URL = "https://ci.appveyor.com/api/account/{}/projects/paged?pageIndex={}&pageSize=100"
APPVEYOR_LATEST_BUILD_API_URL = "https://ci.appveyor.com/api/projects/{}/{}"
APPVEYOR_BUILD_LOG_API_URL = "https://ci.appveyor.com/api/buildjobs/{}/log"


def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    """
    Build a retry session for requests
    """
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


# get repository list from github
def get_github_repos(org, prefix=None, private=None, verbose=False):
    all_repos_list = []
    page_number = 1
    request_headers = {
        "User-Agent": "GitHubRepoLister/1.0",
        "Authorization": "token " + settings.github_token,
    }
    while True:
        if verbose:
            sys.stdout.write('.')
            sys.stdout.flush()
        repos_page = requests_retry_session().get(
            "https://api.github.com/orgs/{}/repos?page={}".format(
                org, page_number
            ),
            headers=request_headers,
            timeout=settings.requests_timeout
        )
        page_number = page_number + 1
        if repos_page.status_code != 200:
            raise Exception("Failed to load repos from GitHub: " + repos_page.content)
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
def get_github_repo_names(org, prefix=None, private=None):
    repos = get_github_repos(org, prefix, private)
    return set([x['full_name'] for x in repos])


#
def get_github_repo_default_branch(repo):
    """
    Retrieves default branch name for repository from GitHub
    
    :param repo: repository name (with organization/owner prefix)
    :returns: default branch name
    """
    default_branch_headers = {
        "User-Agent": "GitHubDefaultBranchDetector/1.0",
        "Authorization": "token " + settings.github_token,
        "Accept": "application/vnd.github.antiope-preview+json",
    }
    res = requests_retry_session().get(
        "https://api.github.com/repos/{}".format(
            repo
        ),
        headers=default_branch_headers,
        timeout=settings.requests_timeout
    )
    if res.status_code != 200:
        raise Exception("GitHub API reported an error while trying to get info for repository '{}'! Message is '{}' ({}).".format(repo, res.reason, res.status_code))
    return json.loads(res.content).get("default_branch")



def github_user_exists(username):
    """
    Check if a GitHub user exists
    
    :param username: github username to search for
    :returns: True if user exists, False otherwise
    """
    # https://api.github.com/search/users?q=user:username
    request_headers = {
        "User-Agent": "GitHubUserValidator/1.0",
        "Authorization": "token " + settings.github_token,
    }
    res = requests_retry_session().get(
        'https://api.github.com/search/users?q=user:{}'.format(username),
        headers=request_headers,
        timeout=settings.requests_timeout
    )
    if res.status_code != 200:
        raise ValueError("Failed to load user '{}' from GitHub: {}".format(username, res.content))
        # return False
    data = json.loads(res.content)
    if data.get('total_count') == 1:
        return True
    else:
        return False


# get projects list from AppVeyor
def get_appveyor_project_repo_names():
    project_repository_names = {}
    headers = {
        "User-Agent": "AppVeyorAddRepo/1.0",
        "Authorization": "Bearer " + settings.appveyor_token,
    }
    page_index = 0;
    has_next_page = True
    while has_next_page:
        res = requests_retry_session().get(
            APPVEYOR_PROJECTS_API_URL.format(
                settings.appveyor_account,
                page_index
            ),
            headers=headers,
            timeout=settings.requests_timeout
        )
        if res.status_code != 200:
            raise Exception("AppVeyor API reported and error when fetching"
                " project list on page {}! Message is '{}' ({}).".format(
                    page_index, res.reason, res.status_code
                )
            )
            # exit(1)
        response_json = json.loads(res.text)
        for project in response_json['list']:
            # project_repository_names.add(project['repositoryName'])
            project_repository_names[project['repositoryName']] = project['slug']
        # goto next page
        page_index += 1
        has_next_page = response_json['hasNextPage']
    return project_repository_names


# add a new appveyor project
# - repo: repository name of the new appveyor project
def add_appveyor_project(repo):
    headers = {
        "User-Agent": "AppVeyorAddRepo/1.0",
        "Authorization": "Bearer " + settings.appveyor_token,
    }
    add_project_request = {
        "repositoryProvider": "gitHub",
        "repositoryName": repo,
    }
    res = requests.post('https://ci.appveyor.com/api/account/{}/projects'.format(settings.appveyor_account), data=add_project_request, headers=headers)
    if res.status_code != 200:
        raise Exception("AppVeyor API reported an error while trying to add a new project '{}'! Message is '{}' ({}).".format(repo, res.reason, res.status_code))
        # raise Exception("Appveyor API error!")
    return res.content


# trigger a new build of repo's specified branch
def trigger_appveyor_build(slug, branch="master"):
    headers = {
        "User-Agent": "AppVeyorBuildRepo/1.0",
        "Authorization": "Bearer " + settings.appveyor_token,
    }
    build_project_request = {
        "accountName": settings.appveyor_account,
        # "repositoryProvider": "gitHub",
        "projectSlug": slug,
        "branch": branch,
    }
    res = requests.post('https://ci.appveyor.com/api/account/{}/builds'.format(settings.appveyor_account), data=build_project_request, headers=headers)
    if res.status_code != 200:
        raise Exception("AppVeyor API reported an error while trying to build branch '{}' of project '{}'! Message is '{}' ({}).".format(branch, slug, res.reason, res.status_code))
        # exit(1)
    return res.content


# add repositories to appveyor if they are not already added
def add_appveyor_projects_safely(repo_list, trigger_build=False, dry_run=True):
    existing_projects_repos = get_appveyor_project_repo_names()
    new_projects = {}
    for repo in repo_list:
        if repo not in existing_projects_repos:
            if not dry_run:
                res = add_appveyor_project(repo)
                slug = json.loads(res)['slug']
                new_projects[repo] = slug
                if trigger_build:
                    trigger_appveyor_build(slug)
            else:
                new_projects[repo] = ''
    return new_projects


# get a token for Travis API v 2.1 using an existing GitHub token
def get_travis_token(private=True):
    api_url = "https://api.travis-ci.{}/auth/github"
    travis_token_request = {
        "github_token": settings.github_token
    }
    res = requests.post(
        api_url.format("com" if private else "org"),
        data=travis_token_request
    )
    if res.status_code != 200:
        raise Exception("Travis API reported an error while trying to get a {} API token using GitHub token authentication! Message is '{}' ({}).".format("private" if private else "public", res.reason, res.status_code))
    return json.loads(res.content).get("access_token")


#
def get_github_check_runs(repo):
    check_runs_headers = {
        "User-Agent": "GitHubCheckRuns/1.0",
        "Authorization": "token " + settings.github_token,
        "Accept": "application/vnd.github.antiope-preview+json",
    }
    default_branch = get_github_repo_default_branch(repo)
    res = requests_retry_session().get(
        "https://api.github.com/repos/{}/commits/{}/check-runs".format(
            repo, default_branch
        ),
        headers=check_runs_headers,
        timeout=settings.requests_timeout
    )
    if res.status_code != 200:
        raise Exception("GitHub API reported an error while trying to get check run info for repository '{}'! Message is '{}' ({}).".format(repo, res.reason, res.status_code))
    return json.loads(res.content).get("check_runs")


#
def get_github_commits_by_branch(repo: str, branch: str = "master"):
    """
    get commit list from GitHub for provided repository and branch

    :param repo: repository name (with organization/owner prefix)
    :param branch: git branch name (default - "master")
    :return: list of commits, constructed from response JSON
    """
    commits_headers = {
        "User-Agent": "GitHubCommits/1.0",
        "Authorization": "token " + settings.github_token,
        "Accept": "application/vnd.github.v3+json",
    }
    res = requests_retry_session().get(
        "https://api.github.com/repos/{}/commits?sha={}".format(repo, branch),
        headers=commits_headers,
        timeout=settings.requests_timeout
    )
    if res.status_code != 200:
        raise Exception(
            "GitHub API reported an error while trying to get commits for repository '{}' at branch '{}'! Message is '{}' ({}).".format(
                repo, branch, res.reason, res.status_code))
    return json.loads(res.content)


#
def get_github_commit_by_sha(repo: str, sha: str):
    """
    get commit from GitHub for provided repository and commit sha

    :param repo: repository name (with organization/owner prefix)
    :param sha: sha of commit
    :return: commit object, constructed from response JSON
    """
    commit_headers = {
        "User-Agent": "GitHubCommits/1.0",
        "Authorization": "token " + settings.github_token,
        "Accept": "application/vnd.github.v3+json",
    }
    res = requests_retry_session().get(
        "https://api.github.com/repos/{}/commits/{}".format(repo, sha),
        headers=commit_headers,
        timeout=settings.requests_timeout
    )
    if res.status_code != 200:
        raise Exception(
            "GitHub API reported an error while trying to get commit for repository '{}' by sha '{}'! Message is '{}' ({}).".format(
                repo, sha, res.reason, res.status_code))
    return json.loads(res.content)


#
def get_github_issues(repo: str):
    """
    get issues from GitHub for provided repository (exclude pull requests)

    :param repo: repository name (with organization/owner prefix)
    :return: list of issues, constructed from response JSON
    """
    issues_headers = {
        "User-Agent": "GitHubIssues/1.0",
        "Authorization": "token " + settings.github_token,
        "Accept": "application/vnd.github.v3+json",
    }
    res = requests_retry_session().get(
        "https://api.github.com/repos/{}/issues".format(repo),
        headers=issues_headers,
        timeout=settings.requests_timeout
    )
    if res.status_code != 200:
        raise Exception(
            "GitHub API reported an error while trying to get issues for repository '{}'! Message is '{}' ({}).".format(
                repo, res.reason, res.status_code))
    # removing pull requests from issue list
    return [issue for issue in json.loads(res.content) if 'pull_request' not in issue]


#
def get_github_issue_events(repo: str, issue_number: str):
    """
    get issue events from GitHub for provided repository by issue number

    :param repo: repository name (with organization/owner prefix)
    :param issue_number: number of issue
    :return: list of issue events, constructed from response JSON
    """
    issue_events_headers = {
        "User-Agent": "GitHubIssueEvents/1.0",
        "Authorization": "token " + settings.github_token,
        "Accept": "application/vnd.github.v3+json",
    }
    res = requests_retry_session().get(
        "https://api.github.com/repos/{}/issues/{}/events".format(repo, issue_number),
        headers=issue_events_headers,
        timeout=settings.requests_timeout
    )
    if res.status_code != 200:
        raise Exception(
            "GitHub API reported an error while trying to get issue #{} events for repository '{}'! Message is '{}' ("
            "{}).".format(
                issue_number, repo, res.reason, res.status_code))
    return json.loads(res.content)


#
def get_github_issue_referenced_events(repo: str, issue_number: str):
    """
    get issue events with referenced (commit linking) type from GitHub for provided repository by issue number

    :param repo: repository name (with organization/owner prefix)
    :param issue_number: number of issue
    :return: list of referenced type issue events, constructed from response JSON
    """
    events = get_github_issue_events(repo, issue_number)
    return [event for event in events if event['event'] == "referenced"]


#
def get_successfull_build_info(repo, check_run_names, all_successfull=False):
    check_runs = get_github_check_runs(repo)
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
def get_github_workflows_log(repo, check_run_names):
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
    job_id = get_successfull_build_info(repo, check_run_names).get("id")
    if not job_id:
        raise Exception("Unable to get job id from GitHub API check runs")
    workflows_headers = {
        "User-Agent": "GitHubWorkflowsLog/1.0",
        "Authorization": "token " + settings.github_token,
        "Accept": "application/vnd.github.v3+json",
    }
    res = requests_retry_session().get(
        "https://api.github.com/repos/{}/actions/jobs/{}/logs".format(
            repo, job_id
        ),
        headers=workflows_headers,
        timeout=settings.requests_timeout
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
    #     timeout=settings.requests_timeout
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
def get_travis_log(repo, check_run_names):
    # check_runs_headers = {
    #     "User-Agent": "GitHubCheckRuns/1.0",
    #     "Authorization": "token " + settings.github_token,
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
    travis_build = get_successfull_build_info(repo, check_run_names).get("external_id")
    if not travis_build:
        return None
    # 
    # travis_token = get_travis_token()
    # 
    travis_headers = {
        "Travis-API-Version": "3",
        "User-Agent": "API Explorer",
        "Authorization": "token " + settings.travis_token,
    }
    res = requests.get(
        "https://api.travis-ci.com/build/{}".format(travis_build), 
        headers=travis_headers
    )
    if res.status_code != 200:
        raise Exception("Travis API reported an error while trying to get build info for build {} (repository '{}')! Message is '{}' ({}).".format(travis_build, repo, res.reason, res.status_code))
    job_id = json.loads(res.content).get("jobs", [{}])[-1].get("id")
    if job_id is None:
        raise Exception("No valid job ID found for build {} (repository '{}').".format(travis_build, repo))
    res = requests.get(
        "https://api.travis-ci.com/job/{}/log".format(job_id), 
        headers=travis_headers
    )
    if res.status_code != 200:
        raise Exception("Travis API reported an error while trying to get build log for job {} (build {} for repository '{}')! Message is '{}' ({}).".format(job_id, travis_build, repo, res.reason, res.status_code))
    return json.loads(res.content).get("content")


def get_successfull_status_info(repo):
    """
    Extract info about successfull AppVeyor build from GitHub repository
    
    :param repo: github repository
    :returns: repository status info for successfull AppVeyor build
    """
    status_headers = {
        "User-Agent": "GitHubCheckRuns/1.0",
        "Authorization": "token " + settings.github_token,
        "Accept": "application/vnd.github.antiope-preview+json",
    }
    res = requests_retry_session().get(
        "https://api.github.com/repos/{}/commits/master/status".format(repo),
        headers=status_headers,
        timeout=settings.requests_timeout
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


def get_appveyor_log(repo):
    """
    Retrieve AppVeyor build log for a given repository
    
    :param repo: github repository
    :returns: build log
    """
    # get existing (repo, slug) pairs
    existing_projects_repos = get_appveyor_project_repo_names()
    slug = existing_projects_repos[repo]
    # get latest build info
    headers = {
        "User-Agent": "AppVeyorBuildRepo/1.0",
        "Authorization": "Bearer " + settings.appveyor_token,
    }
    res = requests.get(
        APPVEYOR_LATEST_BUILD_API_URL.format(settings.appveyor_account, slug), 
        headers=headers
    )
    if res.status_code != 200:
        raise Exception(
            "AppVeyor API reported an error while trying to get latest build "
            "of repository {} (project '{}')! Message is '{}' ({}).".format(
                repo, slug, res.reason, res.status_code
            )
        )
    build = json.loads(res.content).get("build")
    if build["status"] != "success":
        raise Exception(
            "AppVeyor build {} of repository '{}' was not successfull".format(
                build.get("buildId"), repo
            )
        )
    job_id = build.get("jobs", [{}])[0].get("jobId")
    if job_id is None:
        raise Exception(
            "No valid job ID found for build {} of repository '{}'.".format(
                build.get("buildId"), repo
            )
        )
    res = requests.get(
        APPVEYOR_BUILD_LOG_API_URL.format(job_id), 
        headers=headers
    )
    if res.status_code != 200:
        raise Exception(
            "AppVeyor API reported an error while trying to get build log "
            "for job {} (build {} of repository '{}', project '{}')! "
            "Message is '{}' ({}).".format(
                job_id, build.get("buildId"), repo, slug, res.reason, res.status_code
            )
        )
    return res.content.decode('utf-8')
    # return str(res.content)

#
def get_task_id(log):
    task_id_str = "TASKID is"
    i = log.find(task_id_str)
    # skip all occurences that start with a comma, 
    # e.g. from source code like `echo "TASKID is ..."`,
    # which is echoed to the log before being executed
    while i > 0 and (log[i-1] == '"' or log[i-1] == "'"):
        i = log.find(task_id_str, i+1)
    if i < 0:
        return None
    i += len(task_id_str) + 1
    try:
        task_id = int(log[i:i+2].strip())
    except ValueError as e:
        print(e)
        task_id = -1
    return task_id


def get_grade_reduction_coefficient(log):
    """
    get grade reduction coefficient by provided build log

    :param log: build log
    :return: grade reduction coefficient as str or None
    """
    reduction_str = "Grading reduced by"
    i = log.find(reduction_str)
    # skip all occurences that start with a comma, 
    # e.g. from source code like `echo "Grading reduced by ..."`,
    # which is echoed to the log before being executed
    while i > 0 and (log[i-1] == '"' or log[i-1] == "'"):
        i = log.find(reduction_str, i+1)
    if i < 0:
        return None
    # print(log)
    # print(i)
    i += len(reduction_str) + 1
    reduction_percent = int(log[i:log.find("%", i)].strip())
    if reduction_percent == 0:
        return None
    else:
        # 0.01 * (100 - REDUCTION_PERCENT) = REDUCTION_COEFFICIENT in decimal form
        # return 0.01 * (100 - reduction_percent) # pure float coefficient
        # for current case, where percents could be in range [1; 100], using of 'g' format is OK
        return '{0:g}'.format(0.01 * (100 - reduction_percent))


def get_string_pos_helper(log, search_str):
    i = log.find(search_str)
    # skip all occurences that start with a quote, 
    # e.g. from source code like `echo "Grading reduced by ..."`,
    # which is echoed to the log before being executed
    while i > 0 and (log[i-1] == '"' or log[i-1] == "'"):
        i = log.find(search_str, i+1)
    if i < 0:
        return None
    return i + len(search_str) + 1


def get_grading_points(log):
    """
    get grading points (score) if provided in the build log

    :param log: build log
    :return: grade reduction coefficient as str or None
    """
    # TODO: this function should take a regex argument to search for a specific phrase in the logs
    points = None
    i = get_string_pos_helper(log, "Score is")
    if i is not None:
        points = float(log[i:log.find("\n", i)].strip())
    else:
        i = get_string_pos_helper(log, "Points")
        if i is not None:
            points = float(log[i:log.find("/", i)].strip())
    return points


#
def get_repo_issues_grade_coefficient(repo: str, lab_id: str):
    """
    get grade coefficient for provided repository and lab id by checking repository issues requirements

    :param repo: repository name (with organization/owner prefix)
    :param lab_id: id of lab
    :return: None or float coefficient (which can be 0.0)
    """

    if "issue" not in settings.os_labs[lab_id]['repo_requirements']:
        return None

    # get prefix
    if "prefix" in settings.os_labs[lab_id]['repo_requirements']['issue']:
        prefix = settings.os_labs[lab_id]['repo_requirements']['issue']['prefix']
    else:
        prefix = None

    # get linked commit message part
    if "linked_commit_msg_part" in settings.os_labs[lab_id]['repo_requirements']['issue']:
        linked_commit_msg_part = settings.os_labs[lab_id]['repo_requirements']['issue']['prefix']
    else:
        linked_commit_msg_part = None

    # get issues min quantity from settings (mandatory)
    if "min_quantity" in settings.os_labs[lab_id]['repo_requirements']['issue']:
        min_quantity = settings.os_labs[lab_id]['repo_requirements']['issue']['min_quantity']
    else:
        min_quantity = None

    # get grade percent from settings (mandatory)
    if "grade_percent" in settings.os_labs[lab_id]['repo_requirements']['issue']:
        grade_percent = settings.os_labs[lab_id]['repo_requirements']['issue']['grade_percent']
    else:
        grade_percent = None

    # check acquired lab settings
    if grade_percent is None or min_quantity is None:
        return None

    # get repo issues from github
    if prefix is None:
        repo_issues = get_github_issues(repo)
    else:
        repo_issues = [issue for issue in get_github_issues(repo) if issue['title'].startswith(prefix)]

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
        student_commit_events_for_issue = [event for event in get_github_issue_referenced_events(repo, current_issue_number)
                                           if event['actor']['login'] not in settings.teacher_github_logins
                                           and event['commit_id'] is not None
                                           and repo in event['commit_url']]
        if len(student_commit_events_for_issue) == 0:
            student_commit_events_for_issue = [
                
            ]

        if len(student_commit_events_for_issue) >= 1:
            if linked_commit_msg_part is not None:
                linked_commits_sha = [event['commit_id'] for event in student_commit_events_for_issue]
                linked_commits = [commit for commit in
                                  [get_github_commit_by_sha(repo, sha) for sha in linked_commits_sha]
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
def get_repo_commit_grade_coefficient(repo: str, lab_id: str):
    """
    get grade coefficient for provided repository and lab id by checking repository commits requirements

    :param repo: repository name (with organization/owner prefix)
    :param lab_id: id of lab
    :return: None or float coefficient (which can be 0.0)
    """

    if "commit" not in settings.os_labs[lab_id]['repo_requirements']:
        return None

    # get commit message part
    if "msg_part" in settings.os_labs[lab_id]['repo_requirements']['commit']:
        msg_part = settings.os_labs[lab_id]['repo_requirements']['commit']['msg_part']
    else:
        msg_part = None

    # get issues min quantity from settings
    if "min_quantity" in settings.os_labs[lab_id]['repo_requirements']['commit']:
        min_quantity = settings.os_labs[lab_id]['repo_requirements']['commit']['min_quantity']
    else:
        min_quantity = None

    # get grade percent
    if "grade_percent" in settings.os_labs[lab_id]['repo_requirements']['commit']:
        grade_percent = settings.os_labs[lab_id]['repo_requirements']['commit']['grade_percent']
    else:
        grade_percent = None

    # check acquired lab settings
    if grade_percent is None or min_quantity is None:
        return None

    # get repo commits from github
    repo_commits = get_github_commits_by_branch(repo)

    # get commits and removing authored by teacher
    student_commits = [commit for commit in repo_commits
                       if commit['author']['login'] not in settings.teacher_github_logins]

    if msg_part is not None:
        commits_with_prefix = [commit for commit in student_commits if msg_part in commit['commit']['message']]
        commits_number: int = len(commits_with_prefix)
    else:
        commits_number: int = len(student_commits)

    if commits_number >= int(min_quantity):
        return float(int(grade_percent) / 100)
    else:
        return 0.0


def github_get_file(repo, filepath):
    """
    get a single file from GitHub
    
    :param repo: repository name (with organization/owner prefix)
    :param filepath: path and file name of the file to be retrieved
    :returns: file contents as a bytes string
    """
    # https://gist.github.com/Integralist/9482061
    status_headers = {
        "User-Agent": "GitHubGetFile/1.0",
        "Authorization": "token " + settings.github_token,
        "Accept": "application/vnd.github.v3.raw",
    }
    res = requests_retry_session().get(
        "https://api.github.com/repos/{}/contents/{}".format(repo, filepath),
        headers=status_headers,
        timeout=settings.requests_timeout
    )
    if res.status_code != 200:
        raise Exception("GitHub API reported an error while trying to get file '{}' from repository '{}'! Message is '{}' ({}).".format(filepath, repo, res.reason, res.status_code))
    return res.content


def github_get_latest_commit_date(repo):
    """
    get the latest commit timestamp to a GitHub repository
    
    :param repo: repository name (with organization/owner prefix)
    :returns: date of the latest commit
    """
    status_headers = {
        "User-Agent": "GitHubGetLatestCommitDate/1.0",
        "Authorization": "token " + settings.github_token,
        "Accept": "application/vnd.github.v3.raw",
    }
    res = requests_retry_session().get(
        "https://api.github.com/repos/{}".format(repo),
        headers=status_headers,
        timeout=settings.requests_timeout
    )
    if res.status_code != 200:
        raise Exception("GitHub API reported an error while trying to get info about repository '{}'! Message is '{}' ({}).".format(repo, res.reason, res.status_code))
    pushed_at = json.loads(res.content).get("pushed_at")
    return datetime.datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))

