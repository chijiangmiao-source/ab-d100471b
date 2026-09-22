# syntax=docker/dockerfile:1

# ---- build stage ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG WEB_HOST
ARG WEB_PORT
ARG API_HOST
ARG API_PORT
ENV WEB_HOST=${WEB_HOST} \
    WEB_PORT=${WEB_PORT} \
    API_HOST=${API_HOST} \
    API_PORT=${API_PORT}
RUN npm run build

# ---- serve stage ----
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY docker-entrypoint.sh /docker-entrypoint-web.sh
RUN chmod +x /docker-entrypoint-web.sh

# Runtime-configurable: container listen port and API upstream.
ENV WEB_PORT=80 \
    API_HOST=api \
    API_PORT=8000

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --start-period=4s --retries=5 \
    CMD wget -qO- "http://127.0.0.1:${WEB_PORT}/health" | grep -q '"ok"' || exit 1

ENTRYPOINT ["/docker-entrypoint-web.sh"]
