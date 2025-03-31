import os
import azure.functions as func
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
import tarfile


# Environment variables for Azure Storage
STORAGE_CONNECTION_STRING = os.getenv('AzureWebJobsStorage')
INPUT_CONTAINER_NAME = os.getenv('INPUT_CONTAINER_NAME')
OUTPUT_CONTAINER_NAME = os.getenv('OUTPUT_CONTAINER_NAME')

def main(req: func.HttpRequest) -> func.HttpResponse:
    blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
    input_container_client = blob_service_client.get_container_client(INPUT_CONTAINER_NAME)
    output_container_client = blob_service_client.get_container_client(OUTPUT_CONTAINER_NAME)

    # Ensure output container exists
    try:
        blob_service_client.create_container(OUTPUT_CONTAINER_NAME)
    except Exception:
        pass  # Container already exists

    # List all blobs in the input container
    blobs = input_container_client.list_blobs(name_starts_with='*')

    for blob in blobs:
        blob_name = blob.name
        blob_client = input_container_client.get_blob_client(blob_name)
        tar_stream = blob_client.download_blob().readall()

        # Save the .tar file temporarily
        tar_file_path = './*.tar'
        with open(tar_file_path, 'wb') as tar_file:
            tar_file.write(tar_stream)

        # Open the .tar file and extract its contents
        with tarfile.open(tar_file_path) as tar:
            for member in tar.getmembers():
                file_obj = tar.extractfile(member)
                if file_obj:
                    file_name = member.name
                    output_blob_client = output_container_client.get_blob_client(file_name)
                    output_blob_client.upload_blob(file_obj, overwrite=True)

        # Clean up temporary file
        os.remove(tar_file_path)

    return func.HttpResponse(f'Decompressed all .tar files from {INPUT_CONTAINER_NAME}/data and uploaded files to {OUTPUT_CONTAINER_NAME} container.', status_code=200)
