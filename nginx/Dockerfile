ARG FROM_IMAGE=nginx
ARG FROM_VERSION=1.21.3

FROM node:14-alpine as build
WORKDIR /usr/src/app
COPY ui/package.json package.json
RUN npm install
RUN npm install -g @angular/cli
COPY ui/. .
RUN ng build

FROM ${FROM_IMAGE}:${FROM_VERSION}-alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY .htpasswd.template /etc/nginx/.htpasswd
COPY --from=build /usr/src/app/dist /usr/share/nginx/html