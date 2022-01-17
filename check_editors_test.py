import unittest
from unittest.mock import MagicMock

import check_editors

class TestCheckEditors(unittest.TestCase):

	def test_github_data_parser(self):
		with open('tests/check_editors.json', 'r') as reader:
			json = reader.read()
			result = check_editors.github_data_parser(json)
			self.assertTrue("nphl" in result)
			self.assertEqual(len(result), 2)
			self.assertFalse("black_hacker" in result)
			self.assertIsInstance(result, list)

	def test_check_geter_parser(self):
		getter = MagicMock()
		parser = MagicMock(return_value=["nphl"])
		check_editors.check(getter, parser, ["nphl"], "file")
		getter.assert_called_with(
			"file", "https://api.github.com/repos/:owner/:repo/commits?path=file")

	def test_check_rise(self):
		getter = MagicMock()
		parser = MagicMock(return_value=["black_hacker"])
		with self.assertRaises(RuntimeError):
			check_editors.check(getter, parser, ["nphl"], "file")

	def test_check_ok(self):
		getter = MagicMock()
		parser = MagicMock(return_value=["nphl"])
		check_editors.check(getter, parser, ["nphl", "nphl2"], "file")

	def test_check_editors(self):
		getter = MagicMock()
		parser = MagicMock(return_value=["nphl"])
		check_editors.check_editors(["file1"], ["nphl", "nphl2"], getter, parser)
		getter.assert_called_with(
			"file1", "https://api.github.com/repos/:owner/:repo/commits?path=file1")

	def test_build_github_edpoint(self):
		url = check_editors.build_github_edpoint("testfile")
		self.assertCountEqual(url, "https://api.github.com/repos/:owner/:repo/commits?path=testfile")

if __name__ == '__main__':
    unittest.main()
