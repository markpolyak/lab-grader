import json

def build_github_edpoint(file):
	return "https://api.github.com/repos/:owner/:repo/commits?path="+file

def github_data_parser(str):
	data = json.loads(str)
	result = []

	for line in data:
		login = line['committer']['login']

		if login not in result:
			result.append(login)

	return result

def check(getter, parser, allowed_users, file):
	data = getter(file, build_github_edpoint(file))
	editors = parser(data)

	for editor in editors:
		if (editor not in allowed_users):
			raise RuntimeError("["+ editor +"] wrong editor for file ["+ file +"]")


def check_editors(files, users, data_getter, parser = github_data_parser):
	for file in files:
		check(data_getter, parser, users, file)
