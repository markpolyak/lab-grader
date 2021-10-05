import os
import yaml

def load_config(path_to_yaml: str) -> dict:
    try:
        with open(path_to_yaml, encoding="utf-8", mode='r') as stream:
            config = yaml.safe_load(stream)
            return config
    except (FileNotFoundError, yaml.YAMLError) as exp:
        raise exp

class PathConfig:
    def __init__(self):
        self.auth_config = os.getenv('GRADER_AUTH_CONFIG', '../static/app/auth.yaml')
        self.logger_config = os.getenv('GRADER_LOGGER_CONFIG', '../static/app/logging.yaml')
        self.courses_path = os.getenv('GRADER_COURSE_CONFIGS_PATH', '../static/courses')
        self.log_path = os.getenv('GRADER_LOG_PATH', 'logs')
