# Azure Job Clearup script

A simple Azure Job clearup script. This will clearup jobs in an Azure Batch account (which have a maximum quota). It will delete jobs older than 7 days and terminate empty jobs (removing them from the quota but not deleting them).

1. Install the requirements in [requirements.txt](./requirements.txt)
1. Add the following environment variables:
   - `AZURE_BATCH_ACCOUNT_NAME`
   - `AZURE_BATCH_ACCOUNT_KEY`
   - `AZURE_BATCH_URL` (typically `https://$AZURE_BATCH_ACCOUNT_NAME.$AZURE_BATCH_REGION.batch.azure.com`)
1. Run the script (`python clearup-azure-batch-jobs.py`)
