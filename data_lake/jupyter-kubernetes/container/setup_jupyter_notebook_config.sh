#!/bin/bash

set -o nounset # Fail on unset variables
set -o errexit # Fail on uncaught non-zero returncodes
set -o pipefail # Fail is a command in a chain of pipes fails

(
    echo
    echo
    echo '# -- Custom conda kernels using via nb_conda_kernels'
    echo '# Only show conda environments in list of kernels'
    echo 'c.CondaKernelSpecManager.env_filter = "^/opt/conda"'
    echo '# Less verbose name for custom kernels; default '
    echo 'c.CondaKernelSpecManager.name_format = "{0} [conda env:{1}]"'
    echo
    echo '# -- Timing out terminals, kernels, and servers for logged-in but idle users.'
    echo 'c.MappingKernelManager.cull_idle_timeout = 1 * 60 * 60'
    echo 'c.MappingKernelManager.cull_interval = 60'
    echo 'c.MappingKernelManager.cull_connected = True'
    echo 'c.TerminalManager.cull_inactive_timeout = 1 * 60 * 60'
    echo 'c.NotebookApp.shutdown_no_activity_timeout = 1 * 60 * 60'
    echo
    echo
) >> /etc/jupyter/jupyter_notebook_config.py
