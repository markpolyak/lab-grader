import json

import requests

from lab_grader.core.common import requests_retry_session

APPVEYOR_PROJECTS_API_URL = "https://ci.appveyor.com/api/account/{}/projects/paged?pageIndex={}&pageSize=100"
APPVEYOR_LATEST_BUILD_API_URL = "https://ci.appveyor.com/api/projects/{}/{}"
APPVEYOR_BUILD_LOG_API_URL = "https://ci.appveyor.com/api/buildjobs/{}/log"


class AppVeyor:
    def __init__(self, requests_timeout, auth: dict):
        self.requests_timeout = requests_timeout
        self.account = None
        self.token = None
        self.__dict__.update(**auth)

    # get projects list from AppVeyor
    def get_appveyor_project_repo_names(self):
        project_repository_names = {}
        headers = {
            "User-Agent": "AppVeyorAddRepo/1.0",
            "Authorization": "Bearer " + self.token,
        }
        page_index = 0
        has_next_page = True
        while has_next_page:
            res = requests_retry_session().get(
                APPVEYOR_PROJECTS_API_URL.format(
                    self.account,
                    page_index
                ),
                headers=headers,
                timeout=self.requests_timeout
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
    def add_appveyor_project(self, repo):
        headers = {
            "User-Agent": "AppVeyorAddRepo/1.0",
            "Authorization": "Bearer " + self.token,
        }
        add_project_request = {
            "repositoryProvider": "gitHub",
            "repositoryName": repo,
        }
        res = requests.post('https://ci.appveyor.com/api/account/{}/projects'.format(self.account),
                            data=add_project_request, headers=headers)
        if res.status_code != 200:
            raise Exception(
                "AppVeyor API reported an error while trying to add a new project '{}'! Message is '{}' ({}).".format(
                    repo, res.reason, res.status_code)
            )
            # raise Exception("Appveyor API error!")
        return res.content

    # trigger a new build of repo's specified branch
    def trigger_appveyor_build(self, slug, branch="master"):
        headers = {
            "User-Agent": "AppVeyorBuildRepo/1.0",
            "Authorization": "Bearer " + self.token,
        }
        build_project_request = {
            "accountName": self.account,
            # "repositoryProvider": "gitHub",
            "projectSlug": slug,
            "branch": branch,
        }
        res = requests.post('https://ci.appveyor.com/api/account/{}/builds'.format(self.account),
                            data=build_project_request, headers=headers)
        if res.status_code != 200:
            raise Exception(
                "AppVeyor API reported an error while trying to build branch '{}' of project '{}'! Message is '{}' ({}).".format(
                    branch, slug, res.reason, res.status_code))
            # exit(1)
        return res.content

    # add repositories to appveyor if they are not already added
    def add_appveyor_projects_safely(self, repo_list, trigger_build=False, dry_run=True):
        existing_projects_repos = self.get_appveyor_project_repo_names()
        new_projects = {}
        for repo in repo_list:
            if repo not in existing_projects_repos:
                if not dry_run:
                    res = self.add_appveyor_project(repo)
                    slug = json.loads(res)['slug']
                    new_projects[repo] = slug
                    if trigger_build:
                        self.trigger_appveyor_build(slug)
                else:
                    new_projects[repo] = ''
        return new_projects

    def get_appveyor_log(self, repo):
        """
        Retrieve AppVeyor build log for a given repository

        :param repo: github repository
        :returns: build log
        """
        # get existing (repo, slug) pairs
        existing_projects_repos = self.get_appveyor_project_repo_names()
        slug = existing_projects_repos[repo]
        # get latest build info
        headers = {
            "User-Agent": "AppVeyorBuildRepo/1.0",
            "Authorization": "Bearer " + self.token,
        }
        res = requests.get(
            APPVEYOR_LATEST_BUILD_API_URL.format(self.account, slug),
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
