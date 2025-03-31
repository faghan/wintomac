#!/bin/bash

set -o nounset # Fail on unset variables
set -o errexit # Fail on uncaught non-zero returncodes
set -o pipefail # Fail is a command in a chain of pipes fails

if [ $# -ne 1 ];
then
    echo "Usage:" > /dev/stderr
    echo "\$ $0 <command>" > /dev/stderr
    exit 1
elif [ ! -e "/config/config.ini" ];
then
    echo "'/config/config.ini' not found" > /dev/stderr

    exit 1
fi

# Workaround for HOME defaulting to /, which is read-only when using -u
export HOME=/tmp/work
mkdir -p ${HOME}
cd ${HOME}

sync_to_azure $1 --config /config/config.ini
