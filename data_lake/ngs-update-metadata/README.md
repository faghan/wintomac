# ngs-update-metadata
Ad-hoc container to update metadata and tags on blobs in the NGS storage account `cfbngsv2`.

It will loop through all blobs in the specified container in the specified storage account and set metadata and tags.

See data-lake/cfb-fa-dl/README.md for a description of rules.

## Usage
Create Docker_dev.env as a copy of Docker.env and set BenchlingConnectionString and AZURE_CLIENT_SECRET


`make build` will build the image.

`make push` will push the image to the Azure Cointainer Reistry cfbregistry.

`make pull` will pull the image from the registry.

`make test` will run the image locally using the environment file Docker_dev.env
