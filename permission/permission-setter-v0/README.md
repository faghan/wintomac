# API

## Endpoints documentation

[Endpoints documentation](docs/README.md)

## API direct connection

To call the API directly, you can use the following command:

```bash
./bin/request.sh
```

To call API from external client "Authorization" header should be set to "Bearer <token>" where token can be obtained by calling the following command:

```bash
./bin/get_token.sh
```

# Development

## Setup

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
- [Azure functions core tools](https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local?tabs=linux%2Ccsharp%2Cbash)

### Credentials

You have to create a `.local.settings.json` file in the root, and add the azure credetails to it. For example usage check the [`local.settings.json.template`](.local.settings.json.template) file.

### Install dependencies

```bash
pipenv install --dev
```

## Running locally

To start the server, run:

```bash
func start
```

## Development

This project is using test driven development (TDD). To run the tests, call the following command:

```bash
pipenv run pytest tests
```

## Documentation

API change should be documented in the [openapi.yml](openapi.yml) file. Once this file is updated one needs to call:

```bash
./bin/update_docs.sh
```

to update the documentation in [docs](docs) folder.
