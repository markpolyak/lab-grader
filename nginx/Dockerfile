ARG FROM_IMAGE=nginx
ARG FROM_VERSION=1.21.3

FROM ${FROM_IMAGE}:${FROM_VERSION}-alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY .htpasswd.template /etc/nginx/.htpasswd