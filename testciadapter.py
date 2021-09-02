from abstractciadapter import (AbstractCIAdapter, Repo)

class TestCIAdapterGood (AbstractCIAdapter):
      def __init__ (self, username):
            super().__init__ (username)

      def get_repos (self):
          return [
              Repo("name1", "email2"),
              Repo("name2", "email2"),
          ]

      def user_exists (cls, username):
          return True

class TestCIAdapterBad1 (AbstractCIAdapter):
      def __init__ (self, username):
            super().__init__ (username)

      def get_repos (self):
            return []

class TestCIAdapterBad2 (AbstractCIAdapter):
      def __init__ (self, username):
            super().__init__ (username)

      def get_repos (self):
            return [
                  Repo("name1", "email2"),
                  "name2", "email2"
            ]
