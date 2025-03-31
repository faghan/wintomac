#!/bin/bash

set -o nounset # Fail on unset variables
set -o errexit # Fail on uncaught non-zero returncodes
set -o pipefail # Fail is a command in a chain of pipes fails

LIVE=/broker/letsencrypt/live.tgz
BACKUP=/broker/letsencrypt/$(date +"%Y%m%d_%H%M%S.tgz")

if [ -e "${LIVE}" ];
then
    mv -v "${LIVE}" "${BACKUP}"
fi

# Backup all relevant files
tar cvzf ${LIVE} /etc/nginx/nginx.conf /etc/letsencrypt
