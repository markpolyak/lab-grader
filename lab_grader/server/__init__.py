import hashlib
import os
from lab_grader.core import Grader
from lab_grader import PathConfig
from bottle import auth_basic, request, route, run, get, HTTPError


def is_authenticated_user(user_check, password_check):
    with open("auth_login.tsv", 'r') as f:
        user = f.read()

    with open("auth_pass.tsv", 'rb') as f:
        storage = f.read()

    salt = storage[:32]  # 32 является длиной соли
    key = storage[32:]

    key_check = hashlib.pbkdf2_hmac(
        'sha256',  # Используемый алгоритм хеширования
        password_check.encode('utf-8'),  # Конвертируется пароль в байты
        salt,  # Предоставляется соль
        100000  # Рекомендуется использовать хотя бы 100000 итераций SHA-256
    )

    if user == user_check and key == key_check:
        return True
    return False


@route('/api/grader/modauth', method='POST')
@auth_basic(is_authenticated_user)
def mod_auth():
    user = request.json.get('username')
    password = request.json.get('password')
    salt = os.urandom(32)

    key = hashlib.pbkdf2_hmac(
        'sha256',  # Используемый алгоритм хеширования
        password.encode('utf-8'),  # Конвертируется пароль в байты
        salt,  # Предоставляется соль
        100000  # Рекомендуется использовать хотя бы 100000 итераций SHA-256
    )

    with open('auth_login.tsv', 'w') as f:
        f.write(user)

    storage = salt + key
    with open('auth_pass.tsv', 'wb') as f:
        f.write(storage)


@route('/api/grader/labs', method='POST')
@auth_basic(is_authenticated_user)
def check_labs():
    labs_count = request.json.get('labs_count')
    config = request.json.get('config')
    dry_run = request.json.get('dry_run')
    logs_vv = request.json.get('logs_vv')
    return Grader(course_config=config, dry_run=dry_run, logs_vv=logs_vv).check_labs(labs_count=labs_count)


@route('/api/grader/email', method='POST')
@auth_basic(is_authenticated_user)
def check_emails():
    config = request.json.get('config')
    dry_run = request.json.get('dry_run')
    logs_vv = request.json.get('logs_vv')
    return Grader(course_config=config, dry_run=dry_run, logs_vv=logs_vv).check_emails()


@route('/api/grader/logs', method='GET')
@auth_basic(is_authenticated_user)
def get_logs():
    try:
        uuid_log_id = request.query.get('file')
        path_config = PathConfig()
        log_file = "{}/{}.log".format(path_config.log_path, uuid_log_id)
        with open(log_file, 'r') as f:
            return f.read()
    except FileNotFoundError as e:
        return HTTPError(404, e)


@get('/auth')
def auth():
    return "Authentication complete"


def run_grader_server(instance):
    host = instance.split(':')[0]
    port = instance.split(':')[-1]
    run(host=host, port=port)
