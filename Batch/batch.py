from azure.identity import AzureCliCredential
from azure.batch import BatchServiceClient

# Initialize Azure CLI credential
credential = AzureCliCredential()

# Initialize Batch service client
account_name = "your-batch-account-name"
batch_url = "https://{0}.westeurope.batch.azure.com".format(account_name)
batch_client = BatchServiceClient(batch_url=batch_url, credential=credential)

# Specify the job ID of the job you want to delete
job_id_to_delete = "job-04fdc0b6f4ef4640da6a-SPLITLETTERS"

# Delete the specified job from the Batch account
print("Deleting job:", job_id_to_delete)
batch_client.job.delete(job_id=job_id_to_delete)
print("Job deleted successfully.")

print("Job deleted.")
