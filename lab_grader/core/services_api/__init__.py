from lab_grader.core.services_api.github import GitHub
from lab_grader.core.services_api.appveyor import AppVeyor


class ServicesApi:
    def __init__(self, auth_config: dict):
        self.request_timeout = auth_config['request_timeout']
        self.__auth = auth_config['auth']
        self.github = GitHub(requests_timeout=self.request_timeout, auth=self.__auth['github'])
        self.appveyor = AppVeyor(requests_timeout=self.request_timeout, auth=self.__auth['appveyor'])
