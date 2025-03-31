#!/bin/bash

set -o nounset # Fail on unset variables
set -o errexit # Fail on uncaught non-zero returncodes
set -o pipefail # Fail is a command in a chain of pipes fails

test_dir=$(dirname $0)
if [ -n "${test_dir}" ];
then
    cd "${test_dir}";
fi

GROUP=${1:-.}
FILTER=${2:-.}
OLD_PWD=${PWD}

# Attempt to find location of venv
if ! which sync_to_azure > /dev/null;
then
    while test "${PWD}" != "/";
    do
        if [ -e "venv" ];
        then
            BIN=$(readlink -f venv/bin)

            echo "Adding ${BIN} to PATH" 2> /dev/stderr
            export PATH=${BIN}:$PATH

            break
        fi

        cd ..
    done
else
    echo "Using 'sync_to_azure' already in PATH" 2> /dev/stderr
fi

cd "${OLD_PWD}"


########################################################################################
## Miseq

for test in $(find ${GROUP} -type f -name '*.json' | sed -e's#^\./##' | sort | grep "${FILTER}");
do
    echo
    echo
    echo "-- ${test} --"

    if ! ./tester.py --config ${test/\/*/}.ini --test "${test}";
    then
        echo
        echo "Test failed: ${test}"

        exit 1
    fi
done
