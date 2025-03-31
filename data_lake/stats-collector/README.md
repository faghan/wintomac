# stats-collector (deprecated)

**No longer in use since we are now using the blob inventory reports feature of storage accounts.**


C# program deployed to an Azure Container Instance. Crawls the data lake and collects number of folder and files and data volumes.

Registry: https://portal.azure.com/#@dtudk.onmicrosoft.com/resource/subscriptions/aee8556f-d2fd-4efd-a6bd-f341a90fa76e/resourceGroups/rg-cfb-common/providers/Microsoft.ContainerRegistry/registries/cfbregistry/repository

Runs once a week by the Azure automation runbook `start-datalake-stats-collector`in the automation account `aa-datalake-stats`

Collects NGS run statistics from cfbngsv2/miseq01 and cfbngsv2/nextseq01 and insert it to the Data Warehouse table data_lake.ngs_run_stats.
 - Numnber of runs = Number of top-level folders under miseq01/MiSeqOutput and nextseq01/NextSeqOutput
 - Data volume in bytes = Total data volume

Collects NGS sample statistics from cfbngsv2/sample and inserts into the Data Warehouse table data_lake.ngs_sample_stats.
- Number of samples counted as number of top-level folders in the samples container
- Data volume in bytes = volume of all blobs in the samples container
- Sample names = json array of top-level folder names.

Collect proteomics statistics from cfbproteomics/proteomics.
- Number of runs = Number of top-level folders in the container.
- Number of samples = Total number of rows in the Samples tab in all metadata.xlsx files found in top-level folders.
- Data volume in bytes = volume of all blobs in the proteomics container.

Using C# because the .NET library for Azure blob storage at the time of development was much, much more effective than the Python library. That might not still be the case.

## Deployment
The app is containerized and the image is pushed to the Azure Container Registry (ACR) cfbregistry.

An Azure Container Instance (ACI) is created from the image and started by the runbook run-datalake-stats-collector in the Automation Account aa-infrastructure.

The runbook is scheduled to run once a week by the schedule OnceAWeek in the automation account.

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

To run an image with a tag based on the current commit using Docker_dev.env:

``` bash
    make test
```

The default can be overridden by setting the `TAG` variable as shown above.

### Create Azure Container Instance

``` bash
az container create  \
	--resource-group rg-datalake-stats \
	--name datalake-stats-dev \
	--image cfbregistry.azurecr.io/datalake_stats:<tag> \
	--location northeurope \
	--cpu 1 \
	--memory 0.5 \
	--restart-policy Never \
	--environment-variables 'AZURE_TENANT_ID'='f251f123-c9ce-448e-9277-34bb285911d9' 'AZURE_CLIENT_ID'='91f4882a-3c1c-4579-9ecc-6bf2250e109a' 'NGS_ACCOUNT'='cfbngsv2' 'NGS_SAMPLES_CONTAINER'='samples' 'NGS_NEXTSEQ_CONTAINER'='nextseq01' 'NGS_MISEQ_CONTAINER'='miseq01' 'PROTEOMICS_ACCOUNT'='cfbproteomics' 'PROTEOMICS_CONTAINER'='proteomics' 'DWH_SERVER_NAME'='postgres-cfb.postgres.database.azure.com' 'DWH_DB_NAME'='dwh' 'DWH_USER_NAME'='cfb_schema_admin' \
	--secure-environment-variables 'AZURE_CLIENT_SECRET'='the-secret' 'DWH_PASSWORD'='the-password' \
	--registry-login-server cfbregistry.azurecr.io \
	--registry-username cfbregistry \
	--registry-password the-registry-password
```

AZURE_TENANT_ID: The AAD directory (tenant) id

AZURE_CLIENT_ID: Id of the AAD registered app cfb_datalake_stats_collector

AZURE_CLIENT_SECRET: The secret for the AAD registered app cfb_datalake_stats_collector

### Automation Runbook

PowerShell script for Azure Automation Runbook:
```PowerShell
<#
    .DESCRIPTION
        Azure Automation Account Runbook to start the Azure Container Instance that collects data lake statistics.
        It uses the Automation Account's Managed Identity

    .PARAMETER $ResourceGroup
        Name of the resource group where the container instance is created.

    .PARAMETER $ContainerName
        Name of the container instance to start.

#>

param
(
    [Parameter(Mandatory=$true)]
    [String] $ResourceGroup,

    [Parameter(Mandatory=$true)]
    [String] $ContainerName
)

try
{
    "Logging in to Azure..."
    Connect-AzAccount -Identity
}
catch {
    Write-Error -Message $_.Exception
    throw $_.Exception
}

try
{
    "Getting container group $ContainerName in $ResourceGroup"
    $containerGroup = Get-AzContainerGroup -ResourceGroupName $ResourceGroup -Name $ContainerName

    # check state
    if($containerGroup.State -eq "Running")
    {
        $errorMessage = "Container $ContainerName is already running."
        throw $errorMessage
    }

    "Starting container..."
    Invoke-AzResourceAction -ResourceId $containerGroup.Id -Action start -Force

    # TODO: Check status (Invoke-AzResourceAction does not return anything)

    "Runbook finished"

}
catch {
    Write-Error -Message $_.Exception
    throw $_.Exception
}
```
