# lab-grader API
REST API for universal lab grader for university courses

## Description
REST API is developed using Bottle framework. Works with Python 3.9  
API specification is written in *SUAI-lab_grader_rest_api-1.2.0-swagger.yaml*

## Install
```shell
# local
pip install git+https://github.com/hjalti/mossum@master
pip install .

# docker(server mode)
docker-compose up -d
```

## Usage
```shell
# server mode
export GRADER_SERVER=$(hostname -i):8080
python -m lab_grader -a $GRADER_AUTH_CONFIG --logging-config $GRADER_LOGGER_CONFIG server --listen $GRADER_SERVER

# single task mode
python -m lab_grader -a $GRADER_AUTH_CONFIG --logging-config $GRADER_LOGGER_CONFIG task [options]
```
Authentification info is stored in *auth_login.tsv* and *auth_pass.tsv*. *auth_pass.tsv* contains a byte sequence that contains the password hash and salt. It could be generated using *api/grader/modauth* endpoint, linked with *mod_auth()* function, where basic authentification must be turned off (comment *grader_controller.py*, line 31)  
Logs of each query to service are storing in /logs directory and have uuid-generated names
