#!/bin/sh
set -e

echo "Running database migrations..."
python manage.py migrate --noinput

if [ "${AUTO_COLLECTSTATIC:-false}" = "true" ]; then
  echo "Collecting static files..."
  python manage.py collectstatic --noinput
fi

exec "$@"
