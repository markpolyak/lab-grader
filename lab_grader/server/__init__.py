from lab_grader.core import Grader
from lab_grader import PathConfig
from bottle import auth_basic, request, route, run, get, HTTPError

@route('/api/grader/labs', method='POST')
def check_labs():
    labs_count = request.json.get('labs_count')
    config = request.json.get('config')
    dry_run = request.json.get('dry_run')
    logs_vv = request.json.get('logs_vv')
    return Grader(course_config=config, dry_run=dry_run, logs_vv=logs_vv).check_labs(labs_count=labs_count)

@route('/api/grader/labs', method='GET')
def check_labs():
    return Grader(course_config='example-course-config.yaml', dry_run=False, logs_vv=True).check_labs(labs_count=["2"])

@route('/api/grader/email', method='POST')
def check_emails():
    config = request.json.get('config')
    dry_run = request.json.get('dry_run')
    logs_vv = request.json.get('logs_vv')
    return Grader(course_config=config, dry_run=dry_run, logs_vv=logs_vv).check_emails()

@route('/api/grader/logs', method='GET')
def get_logs():
    try:
        uuid_log_id = request.query.get('file')
        path_config = PathConfig()
        log_file = "{}/{}.log".format(path_config.log_path, uuid_log_id)
        with open(log_file, 'r') as f:
            return f.read()
    except FileNotFoundError as e:
        return HTTPError(404, e)

def run_grader_server(instance):
    host = instance.split(':')[0]
    port = instance.split(':')[-1]
    run(host=host, port=port, debug=True, catchall=False)
