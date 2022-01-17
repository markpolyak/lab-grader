# lab-grader
Universal lab grader for university courses

## Usage
```
python main.py --help
python main.py --dry-run
python main.py
python main.py --action moss -l 1
```

## check_editors usage
```python
import check_editors

def load_github_data(filename, prepared_url):
    # filename = tests/test1.py
    # prepared_url = https://api.github.com/repos/:owner/:repo/commits?path=tests/test1.py

    # Нужно заменить в url :owner и :repo на необходимые

    # Ваполнить запрос к АПИ требуемым методомь с нужными настройками
    json_data = get_data_from_github_impl(url)

    # Вернуть разультат без какой либо обработки
    return json_data

# Бросит исключение если файл редактировал не пользователь из списка
check_editors.check_editors(
    ["tests/test1.py", "tests/test2.py"],
    ["markpolyak"],
    load_github_data
)
```
