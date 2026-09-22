#!/bin/sh
# Render the nginx config from runtime environment (only our three vars, so
# nginx's own $host / $remote_addr variables are left untouched), then run nginx
# in the foreground.
set -e

export WEB_PORT="${WEB_PORT:-80}"
export API_HOST="${API_HOST:-api}"
export API_PORT="${API_PORT:-8000}"

envsubst '$WEB_PORT $API_HOST $API_PORT' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf

echo "web on :${WEB_PORT} -> api at ${API_HOST}:${API_PORT}"
exec nginx -g 'daemon off;'
