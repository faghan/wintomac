FROM jupyter/datascience-notebook:2ddf41a430e1

USER root

# WARNING: Using 'WORKDIR' breaks jupyterhub

# Install gnupg2, needed for apt-keyu
RUN apt-get update && apt-get install -y gnupg2
# Install Microsoft ODBC driver and related headers (for pyodbc)
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
RUN curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list > /etc/apt/sources.list.d/mssql-release.list
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev

# Install g++ required for pyodbc
RUN apt-get install g++ -y

# Install python wrappers for Microsoft ODBC
RUN pip install --no-cache-dir pyodbc

# Install nb_conda_kernels to allow custom, persistant conda environments
RUN conda install nb_conda_kernels

# Install R conda packages; all but r-odbc can be install manually as well
RUN conda install \
    r-biocmanager \
    r-getpass \
    r-ggplot2 \
    r-odbc \
    r-openxlsx \
    r-rcpp \
    r-reshape2 \
    r-rlang \
    r-statmod \
    r-stringi \
    r-zip

# Install additional R packages manually (slower than conda);
# script is copied individually to avoid triggering a re-run on folder changes
COPY setup.r /container/setup.r
RUN Rscript /container/setup.r

# Requested packages (ggplot and plotly required by cameo)
RUN pip install --no-cache-dir \
    cameo \
    cobra \
    croissance \
    escher \
    ggplot \
    plotly

# Required Jupyter lab extensions for escher
RUN jupyter labextension install @jupyter-widgets/jupyterlab-manager
RUN jupyter labextension install escher

COPY ./container/ /container/
COPY ./jupyter_service_sample_notebooks/* /container/sample_notebooks/
RUN bash /container/setup_jupyter_notebook_config.sh

# Switch back to unprivileged user to match base Dockerfile
USER $NB_UID