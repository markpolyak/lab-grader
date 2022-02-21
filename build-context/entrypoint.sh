#!/bin/bash

export GRADER_SERVER=$(hostname -i):8080
python -m lab_grader -a $GRADER_AUTH_CONFIG --logging-config $GRADER_LOGGER_CONFIG server --listen $GRADER_SERVER