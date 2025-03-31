# Deprecation notice (2023-12-07)

The code in this folder is not deployed anywhere. It is not in use, anymore.

Jira task: https://biosustain-dev.atlassian.net/browse/RI-140

The following content, and the code, are kept for reference purposes.

# Data-broker

This README describes how to setup a development environment for the data-broker. For instructions on how to deploy the data-broker, see `DEPLOYMENT.md`. For a reference of available API endpoints and their usage, see `REST_API.md`.

## Initial setup

Firstly, make a copy of `template.env` fill out `AZURE_CLIENT_SECRET`.
This is required for both development and deployment:

``` bash
    cp template.env Docker.env
    nano Docker.env
```

## Running the development server

Make sure you have the ODBC driver for SQL Server installed: `https://docs.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server?view=sql-server-ver15`


The `manage.sh` script takes care of setting up a virtual environment and populating environmental variables.

To start the development server:

``` bash
    ./manage.sh runserver
```

To make request to the development server:

``` bash
    export MY_API_KEY=...
    curl -vL -H "APIKEY: ${MY_API_KEY}" localhost:8000/ngs/samples | json_pp
```

## Docker images

### Building a docker image

To build an image with a tag based on the current commit:

``` bash
    make
    # or
    make build
```

By default, the the short form of the current commit hash will be used as the tag for the docker image. This can be overridden by setting the `TAG` variable:

``` bash
    make TAG=MyTag
    # or
    make build TAG=MyTag
```

**WARNING:** Please make sure that all current changes have been committed before building a docker image for deployment!

### Running a docker image

To run an image with a tag based on the current commit:

``` bash
    make test
```

The default can be overridden by setting the `TAG` variable as shown above.

### Querying a docker image

**WARNING**: Requests made to the docker image will be logged in the data warehouse. To avoid this during development, uncomment `AZURE_DWH_LOGGING=0` in the `Docker.env` file.

Query the data-broker:

``` bash
    DB_DOMAIN="cfbdatabroker.northeurope.cloudapp.azure.com"

    # Use resolve to provide expected hosts for nginx/django
    curl -vL -H "APIKEY: ${MY_API_KEY}" --resolve ${DB_DOMAIN}:80:127.0.0.1 http://${DB_DOMAIN}/proteomics/files
```

The `--resolve` option is needed since nginx and Django is setup to refuse connections from other domains.
