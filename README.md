# lab-grader API
REST API for universal lab grader for university courses

## Description
REST API is developed using Bottle framework. Works with Python 3.9  
API specification is written in *SUAI-lab_grader_rest_api-1.2.0-swagger.yaml*

## Usage
```
python grader_controller.py
```
Authentification info is stored in *auth_login.tsv* and *auth_pass.tsv*. *auth_pass.tsv* contains a byte sequence that contains the password hash and salt. It could be generated using *api/grader/modauth* endpoint, linked with *mod_auth()* function, where basic authentification must be turned off (comment *grader_controller.py*, line 31)  
Logs of each query to service are storing in /logs directory and have uuid-generated names
