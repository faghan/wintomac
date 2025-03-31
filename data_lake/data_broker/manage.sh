#!/bin/bash

set -o nounset # Fail on unset variables
set -o errexit # Fail on uncaught non-zero returncodes
set -o pipefail # Fail is a command in a chain of pipes fails

if [ ! -e "Docker.env" ];
then
    cp -av template.env Docker.env
fi

# Exports all docker environmental variables;
# xargs is needed for values containing spaces
export $(grep -v "^#" Docker.env | xargs -d"\n")

# Avoid filling the DWH log with junk while working
echo "Logging to DWH disabled!"
export AZURE_DWH_LOGGING=0

if [ -z "${AZURE_CLIENT_SECRET:-}" ];
then
    echo "ERROR: Please set AZURE_CLIENT_SECRET in Docker.env before proceeding"
    exit 1
fi

if [ ! -e "venv" ];
then
    echo "Creating virtual environment"
    python3 -m venv venv
    # The cryptography package as part of azure-identity will only install on latest pip:
    ./venv/bin/pip3 install -U pip
    ./venv/bin/pip3 install -r container/requirements/local.txt
fi

echo "Entering virtual environment"
. ./venv/bin/activate

cd container

echo "Fetching secrets from the Azure keyvault"
. secrets.sh

echo "Invoking development server"
env DJANGO_SETTINGS_MODULE="config.settings.local" python3 manage.py $@
