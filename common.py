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


def github_user_exists(username):
    """
    Check if a GitHub user exists
    
    :param username: github username to search for
    :returns: True if user exists, False otherwise
    """
    # https://api.github.com/search/users?q=user:username
    res = requests_retry_session().get(
        'https://api.github.com/search/users?q=user:{}'.format(username),
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
    res = requests_retry_session().get(
        "https://api.github.com/repos/{}/commits/master/check-runs".format(
            repo
        ),
        headers=check_runs_headers,
        timeout=settings.requests_timeout
    )
    if res.status_code != 200:
        raise Exception("GitHub API reported an error while trying to get check run info for repository '{}'! Message is '{}' ({}).".format(repo, res.reason, res.status_code))
    return json.loads(res.content).get("check_runs")


#
def get_successfull_build_info(repo):
    check_runs = get_github_check_runs(repo)
    # travis_build = None
    # completion_time = None
    for check_run in check_runs:
        if (
            "Travis CI" in check_run.get("name") 
            and check_run.get("conclusion") == "success"
        ):
            # travis_build = check_run.get("external_id")
            # completion_time = check_run.get("completed_at")
            return check_run
    # if not travis_build:
    return {}
    # return 


#
def get_travis_log(repo):
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
    travis_build = get_successfull_build_info(repo).get("external_id")
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
    i = log.find("TASKID is")
    if i < 0:
        return None
    i += len("TASKID is") + 1
    return int(log[i:i+2].strip())


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



# #
# def get_task2_id(log):
#     i = log.find("Task")
#     if i < 0:
#         return None
#     i += len("Task") + 1
#     return int(log[i:i+2].strip())


#
# def gsheet(solutions, debug=False):
#     #
#     scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
#     creds = ServiceAccountCredentials.from_json_keyfile_name(settings.gsheet_key_filename, scope)
#     conn = gspread.authorize(creds)
#     #
#     for sol in solutions:
#         group_name = sol[0].strip()
#         stud_name = sol[1].lower().strip()
#         repo = sol[2].strip()
#         lab_id = int(repo.split('os-task')[1].split('-')[0])
#         try:
#             worksheet = conn.open(settings.gspreadsheet_name).worksheet(group_name)
#         except:
#             raise Exception("No group {}: {}".format(group_name, sol))
#         names_list = [x.lower() for x in worksheet.col_values(2)[2:]]
#         if stud_name in names_list:
#             stud_row = names_list.index(stud_name) + 3
#         else:
#             raise Exception("No student {}: {}".format(stud_name, sol))
#         if lab_id == 2:
#             completion_date = get_successfull_build_info(repo).get("completed_at")
#             is_empty = worksheet.cell(stud_row, 4+1).value.strip() == ''
#         elif lab_id == 3:
#             completion_date = get_successfull_status_info(repo).get("updated_at")
#             is_empty = worksheet.cell(stud_row, 7+1).value.strip() == ''
#         else:
#             completion_date = None
#             is_empty = False
#         if debug:
#             print("{}: {}, {}".format(sol, completion_date, is_empty))
#         if completion_date and is_empty:
#             worksheet.update_cell(stud_row, 4+(lab_id-2)*3, repo)
#             worksheet.update_cell(stud_row, 4+(lab_id-2)*3+1, datetime.datetime.strptime(completion_date, '%Y-%m-%dT%H:%M:%SZ').date().isoformat())
    
