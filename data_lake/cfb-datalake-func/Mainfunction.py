import logging
import azure.functions as func
import json
from pathlib import Path, PurePosixPath
from azure.identity import DefaultAzureCredential
from azure.mgmt.batch import BatchManagementClient
from azure.storage.blob import BlobServiceClient
import os
import paramiko
from azure.mgmt.compute import ComputeManagementClient
from azure.batch import BatchServiceClient
from azure.batch.batch_auth import SharedKeyCredentials
import subprocess
import docker

app = func.FunctionApp()

@app.event_grid_trigger(arg_name="event")
def StartNextflowPipeline(event: func.EventGridEvent):
    result = json.dumps({
        'id': event.id,
        'data': event.get_json(),
        'topic': event.topic,
        'subject': event.subject,
        'event_type': event.event_type,
    })

    logging.info('Python EventGrid trigger processed an event: %s', result)

    account_name = os.environ["DATA_LAKE_ACCOUNT_NAME"]
    logging.warning("Account name: %s", account_name)

    blob_path = PurePosixPath(*Path(event.subject).parts[6:])

    blob_container_name = Path(event.subject).parts[4]

    logging.info(f"Setting metadata on file: {blob_container_name}/{blob_path}")

    # Acquire a credential object for the app identity. When running in the cloud,
    # DefaultAzureCredential uses the app's managed identity or user-assigned service principal.
    # When run locally, DefaultAzureCredential relies on environment variables named
    # AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, and AZURE_TENANT_ID.
    credential = DefaultAzureCredential()
 
     # Get blob service client
    blob_service_client = BlobServiceClient(
        account_url=f"https://{account_name}.blob.core.windows.net",
        credential=credential,
    )

    # Get container client
    container_client = blob_service_client.get_container_client(blob_container_name)

    # Get blob client
    blob_client = container_client.get_blob_client(str(blob_path))

    logging.warning("blob_name: %s", blob_client.blob_name)

    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    # Build Docker image
    work_directory = "/home/faghan/repos/data-lake/cfb-datalake-func"
    dockerfile_path = os.path.join(work_directory, "Dockerfile")
    image_name = "my_image"
    subprocess.run(["docker", "build", "-t", image_name, "."])
    
    # Initialize Batch service client
    batch_account_name = "testfatemeh"
    batch_account_key = ""
    credentials = SharedKeyCredentials(batch_account_name, batch_account_key)
    batch_url = "https://testfatemeh.westeurope.batch.azure.com"
    batch_client = BatchServiceClient(credentials, batch_url=batch_url)

    # Get list of jobs in the Batch account
    jobs = batch_client.job.list()

    # Iterate through the jobs and delete each one from the specified Batch account
    for job in jobs:
    # Check if the job belongs to the specified Batch account
        # if job.id.startswith(f"{batch_account_name}_"):
        print("Deleting job:", job.id)
        batch_client.job.delete(job_id=job.id)
        print("Job deleted successfully.")

    print("All jobs deleted from the specified Batch account.")
    # Get list of pools in the Batch account
    pools = batch_client.pool.list()

    # Iterate through the pools and delete each one from the specified Batch account
    for pool in pools:
        print("Deleting pool:", pool.id)
        batch_client.pool.delete(pool_id=pool.id)
        print("Pool deleted successfully.")

    print("All pools deleted from the specified Batch account.")

    storageAccountName = "sttestfatemeh",
    storageAccountKey= "",
