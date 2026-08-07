# Project Sentinel — frontend container image (docs/02 §13.1)
# Multi-stage: build the Vite app on Node, serve static dist behind nginx.
# The dashboard only talks to the backend via the `/api` reverse proxy in
# nginx.conf, so a laptop can host the full web app with zero npm tooling.

FROM node:22-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
COPY frontend/ ./

RUN npm ci

RUN npm run build

FROM nginx:1.29-alpine

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]