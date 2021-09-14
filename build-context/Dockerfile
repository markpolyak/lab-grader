ARG FROM_IMAGE=python
ARG FROM_VERSION=3.8-slim-buster

FROM ${FROM_IMAGE}:${FROM_VERSION}

ENV MOSSUM_REPO_URL=https://github.com/hjalti/mossum@master

WORKDIR /opt/grader
COPY lab_grader lab_grader/
COPY setup.py .
COPY build-context/entrypoint.sh .

RUN apt-get update && apt-get install -y git && apt-get clean

RUN pip install git+$MOSSUM_REPO_URL \
    && pip install .

WORKDIR /opt/grader/configs

RUN chmod +x /opt/grader/entrypoint.sh
ENTRYPOINT ["/opt/grader/entrypoint.sh"]