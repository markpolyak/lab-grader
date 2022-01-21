import json

# Генератор endpoint 
# Необходимо в функции обратного вызова заменить /:owner/:repo
# на те которые сейчас обрабатываются, т.к. информация об этом есть только в вызывающем коде

def build_github_edpoint(file):
	return "https://api.github.com/repos/:owner/:repo/commits?path="+file

# Парсер ответа от фунции обратного вызова (сырые данные от github)
# В нашем примере полуим "nphl"

def github_data_parser(str):
	data = json.loads(str)
	result = []

	for line in data:
		login = line['committer']['login']

		if login not in result:
			result.append(login)

	return result

# Главная рабочая ф-ция
# Осуществляет проверку и вызывает callback

def check(callback, parser, allowed_users, file):
	raw_json = callback(file, build_github_edpoint(file))
	editors = parser(raw_json)

	for editor in editors:
		if (editor not in allowed_users):
			raise RuntimeError("["+ editor +"] wrong editor for file ["+ file +"]")


# Рабочая ф-ция. Принимает 3 обязательных параметра.
#  Список файлов в репозитории. 
#  Список редакторов.
#  Callback для непосредственного выполнения запроса к API Github, который получит файл и endpoint по которому нужно выполнить запрос.

def check_editors(files, users, data_getter, parser = github_data_parser):
	for file in files:
		check(data_getter, parser, users, file)
