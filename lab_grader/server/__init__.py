from lab_grader.core import Grader
from lab_grader import PathConfig
from bottle import auth_basic, request, route, run, get, HTTPError, response
from json import dumps


@route('/api/v1/labs', method='POST')
def check_labs():
    labs_count = request.json.get('labs_count')
    config = request.json.get('config')
    dry_run = request.json.get('dry_run')
    logs_vv = request.json.get('logs_vv')
    response.content_type = 'application/json'
    return dumps(Grader(course_config=config, dry_run=dry_run, logs_vv=logs_vv).check_labs(labs_count=labs_count))


@route('/api/v1/emails', method='POST')
def check_emails():
    config = request.json.get('config')
    dry_run = request.json.get('dry_run')
    logs_vv = request.json.get('logs_vv')
    response.content_type = 'application/json'
    return dumps(Grader(course_config=config, dry_run=dry_run, logs_vv=logs_vv).check_emails())


@route('/api/v1/logs/<file_id>', method='GET')
def get_log(file_id):
    try:
        path_config = PathConfig()
        log_file = "{}/{}.log".format(path_config.log_path, file_id)
        with open(log_file, 'r') as f:
            return f.read()
    except FileNotFoundError as e:
        return HTTPError(404, e)


def run_grader_server(instance):
    host = instance.split(':')[0]
    port = instance.split(':')[-1]
    run(host=host, port=port, debug=True, catchall=False)


# todo
@route('/api/v1/logs', method='GET')
def get_logs():
    response.content_type = 'application/json'
    return dumps(["16f0f720-0ae6-468b-af3c-7c4bc919a56e", ])


# todo
@route('/api/v1/configs', method='GET')
def get_logs():
    response.content_type = 'application/json'
    return dumps(["example-course-config.yaml",])
