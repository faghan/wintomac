#!/bin/bash

set -o nounset # Fail on unset variables
set -o errexit # Fail on uncaught non-zero returncodes
set -o pipefail # Fail is a command in a chain of pipes fails

# Unpack /etc/letsencrypt/ and other files
if [ -e /broker/letsencrypt ];
then
    echo "Unpacking letsencrypt certificates"
    tar xvf /broker/letsencrypt/live.tgz -C /
fi


# Disabled since it requires that port 80 be forwarded; see DEPLOYMENT.md
# # Install crontab for automatic letsencrypt renewal
# echo "Installing certbot contab"
# crontab /broker/certbot.tab
# echo "Starting cron"
# service cron start

echo "Starting nginx"
service nginx start

. secrets.sh

# These folders must exist during startup
mkdir -p /var/log/nginx
mkdir -p /var/log/django

echo "Starting gunicorn"
exec gunicorn --bind unix:/broker/gunicorn.sock --workers 3 config.wsgi:application