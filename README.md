# lab-grader
universal lab grader for university courses

## Description
REST API is developed using Bottle framework. Works with Python 3.9  
API specification is written in *SUAI-lab_grader_rest_api-1.2.0-swagger.yaml*

Frontend is developed using Angular.

## Prepare for run 
- setup /static/app/auth.yml as in the [example](/static/app/auth.yaml.example)
- put google-credential.json to /static/app
- if needed create /nginx/.htpasswd for basic auth as in the [example](/nginx/.htpasswd.template)

## Run Lab Grader web service on 80 port
```shell
docker-compose up -d
```

## Local install
```shell
# local
pip install .
```

## Local usage
```shell
# server mode
export GRADER_SERVER=$(hostname -i):8080
python -m lab_grader -a $GRADER_AUTH_CONFIG --logging-config $GRADER_LOGGER_CONFIG server --listen $GRADER_SERVER

# single task mode
python -m lab_grader -a $GRADER_AUTH_CONFIG --logging-config $GRADER_LOGGER_CONFIG task [options]
```