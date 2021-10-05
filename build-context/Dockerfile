ARG FROM_IMAGE=python
ARG FROM_VERSION=3.8-slim-buster

FROM ${FROM_IMAGE}:${FROM_VERSION}

ENV MOSSUM_REPO_URL=https://github.com/hjalti/mossum@master

RUN apt-get update && apt-get install -y git && apt-get clean

RUN pip install git+$MOSSUM_REPO_URL \
    && pip install 'requests~=2.26.0' \
    'oauth2client~=4.1.3' \
    'google-api-python-client~=2.20.0' \
    'bottle~=0.12.19' \
    'google-auth-oauthlib~=0.4.6' \
    'python-dateutil~=2.8.2' \
    'pyyaml~=5.4.1' \
    'beautifulsoup4~=4.10.0' \
    'mosspy~=1.0.9'

WORKDIR /opt/grader
COPY lab_grader lab_grader/
COPY setup.py .
RUN pip install .

COPY build-context/entrypoint.sh .

RUN chmod +x /opt/grader/entrypoint.sh
ENTRYPOINT ["/opt/grader/entrypoint.sh"]