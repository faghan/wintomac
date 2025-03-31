#!/bin/bash

set -o nounset # Fail on unset variables

# Specifies location for user-created conda envs
cp -n "/container/.condarc" "${HOME}/"

# Adds example notebooks
mkdir -p "${HOME}/sample_notebooks"

ls /container/sample_notebooks/ |
while read filename;
do
    source="/container/sample_notebooks/${filename}"
    destination="${HOME}/sample_notebooks/${filename}"

    cp -a -f "${source}" "${destination}"
    # It is not possible to set group permissions
    chmod u-w "${destination}"
done
