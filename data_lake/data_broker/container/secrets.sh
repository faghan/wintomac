#!/bin/bash

echo "Fetching AZURE_NGS_SECRET from Azure key storage"
AZURE_NGS_SECRET="$(./get_secret.py ${AZURE_NGS_ACCOUNT})"
echo "Fetching AZURE_PROTEOMICS_SECRET from Azure key storage"
AZURE_PROTEOMICS_SECRET="$(./get_secret.py ${AZURE_PROTEOMICS_ACCOUNT})"
echo "Fetching AZURE_DWH_PASSWORD from Azure key storage"
AZURE_DWH_PASSWORD="$(./get_secret.py dwhpassword)"
echo "Fetching DJANGO_SECRET_KEY from Azure key storage"
DJANGO_SECRET_KEY="$(./get_secret.py djangosecretkey)"

# Exports are called afterwards, so that pipefail triggers on get_secret.py failures
export AZURE_NGS_SECRET
export AZURE_PROTEOMICS_SECRET
export AZURE_DWH_PASSWORD
export DJANGO_SECRET_KEY
