import datetime

class AbstractCIAdapter:
    """
    Common VCS+CI interface.
    """

    @classmethod
    def user_exists(cls, username) -> bool:
        """
        Checks if user exists in the VCS.

        :param username: VCS username to search for
        :returns: True if user exists, False otherwise
        """
        pass

    def __init__ (self, username):
        """
        Initializes a new instance of CIAdapterInterface
        associated with the given user.

        :param username: VCS user (account) name.
        """
        self.username = username

    def get_repos(self) -> []:
        """
        Returns a set of VCS repositories for the associated user.

        :returns: a list of repositories for the associated user.
        """
        pass

    def add_repos_to_ci(self, repo_list, trigger_build=False, dry_run=False):
        """
        Add repositories to CI if they are not already added.

        :param repo_list: a list of repositories to add;
        :param trigger_build: trigger project rebuild immediately;
        :param dry_run: test the operation without actually add
                        the repositories.
        """
        pass

    def get_last_ci_log(self, repo) -> {}:
        """
        Retrieves the last CI build log for the given repository.

        :param repo: a repository;
        :returns: the build log.
        """
        pass

              
class Repo:
    """
    Base class to represent a repository.
    """
    def __init__(self, n, e):
        self.name = n
        self.email = e

class CIAdapterCheckError(Exception):
    """
    A class to represent a CIAdapter instance verification error.
    """
    pass

def check_repo (repo):
      if not isinstance(repo, Repo):
          raise CIAdapterCheckError("Not an instance of AbstractCIAdapter")
      if not repo.name:
          raise CIAdapterCheckError("The repo name should not be empty")
      if not repo.email:
          raise CIAdapterCheckError("The repo email should not be empty")

def check_get_repos (adapter):
      repos = adapter.get_repos()
      if not isinstance(repos, list) or not repos:
          raise CIAdapterCheckError("get_repos() should return a non-empty list of objects of type 'Repo'")

      for r in repos:
          if not isinstance(r, Repo):
              raise CIAdapterCheckError("Each element returned by get_repos() whould be a Repo")
          check_repo(r)

def check_user_exists (adapter):
      res = adapter.user_exists("test")

def check_adapter (adapter):
      if not isinstance(adapter, AbstractCIAdapter):
          raise CIAdapterCheckError("Not an instance of AbstractCIAdapter")
      check_get_repos(adapter)
      check_user_exists(adapter)
