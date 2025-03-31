# Deprecation notice (2023-11-30)

The code in this folder is not deployed anywhere. It is not in use, anymore.

Jira task: https://biosustain-dev.atlassian.net/browse/RI-135

The following content, and the code, are kept for reference purposes.

# OVERVIEW

This script is syncs data from a PAS-X Savvy (previously named Incyght) server to our PostgreSQL DWH on Azure using the Savvy REST API. In other words, data is read from a REST API and written to tables in our DWH(in our subscription, the Azure Database for PostgreSQL server is named "postgres-cfb," and the name of the database is "dwh").

The scripts are deployed to a server and scheduled to run every six hours. 

To get an overview of the pipeline, please refer to this diagram at the following link: [Benchling pipeline](https://lucid.app/lucidchart/14f6049e-51ba-4b0d-8bbe-4865f1fa195b/edit?viewport_loc=-292%2C-48%2C1365%2C577%2C0_0&invitationId=inv_1fea5bdf-0444-472f-8a8b-391e65747c6e)

## Installation

``` bash
$ python3 setup.py install
$ pasx_savvy_sync --help
```

## Example usage

The script requires a number of parameters and the use of a config file is therefore
recommended:

``` bash
$ cp template.ini config.ini
$ vim config.ini
$ pasx_savvy_sync --config config.ini
```
## Build the code
```bash
make build
```

## Run the code
```bash
make run
```

## Push the code
```bash
make push
```

