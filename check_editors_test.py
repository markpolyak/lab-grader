import unittest
from unittest.mock import MagicMock

import check_editors

class TestCheckEditors(unittest.TestCase):

# Проверка работы парсера 

	def test_github_data_parser(self):
		with open('data.json', 'r') as reader:
			json = reader.read()
			result = check_editors.github_data_parser(json)
			self.assertTrue("nphl" in result) 			# Проверка наличия ожидаемых login-ов
			self.assertEqual(len(result), 2) 			# Проверка кол-ва ожидаемых login-ов
			self.assertFalse("black_hacker" in result) 	# Проверка отсутсвия не ожидаемых login-ов
			self.assertIsInstance(result, list) 		# Проверка типа возвращаемого результата

# Проверка согласованности вызова callback

	def test_check_geter_parser(self):
		getter = MagicMock()
		parser = MagicMock(return_value=["nphl"])
		check_editors.check(getter, parser, ["nphl"], "file") 		
		getter.assert_called_with(
			"file", "https://api.github.com/repos/:owner/:repo/commits?path=file") # Проверка, параметров вызова callback

# Проверка факта выброса исключения, если проверка автора не прошла

	def test_check_rise(self):
		getter = MagicMock()
		parser = MagicMock(return_value=["black_hacker"])
		with self.assertRaises(RuntimeError): 						# Проверка исключения
			check_editors.check(getter, parser, ["nphl"], "file") 

# Проверка с каким сообщением произошёл выброс исключения

	def test_check_rise_message(self):
		getter = MagicMock()
		parser = MagicMock(return_value=["black_hacker"])
		with self.assertRaises(RuntimeError) as res:
			check_editors.check(getter, parser, ["nphl"], "file")
		self.assertEqual(str(res.exception), "[black_hacker] wrong editor for file [file]") # Проверка корректности сообщения

# Проверка нормального завершения работы

	def test_check_ok(self):
		getter = MagicMock()
		parser = MagicMock(return_value=["nphl"])
		check_editors.check(getter, parser, ["nphl", "nphl2"], "file") 

# Проверка согласованности вызова callback при вызове главной ф-ции интерфейса

	def test_check_editors(self):
		getter = MagicMock()
		parser = MagicMock(return_value=["nphl"])
		check_editors.check_editors(["file1"], ["nphl", "nphl2"], getter, parser)
		getter.assert_called_with( 										# Проверка аргумента вызова callback
			"file1", "https://api.github.com/repos/:owner/:repo/commits?path=file1")

# Проверка корректности сформированного URL для Github API

	def test_build_github_edpoint(self):
		url = check_editors.build_github_edpoint("testfile")
		self.assertCountEqual(url, "https://api.github.com/repos/:owner/:repo/commits?path=testfile")   # Проверка ожидаемого URL

if __name__ == '__main__':
    unittest.main()
