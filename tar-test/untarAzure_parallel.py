import tarfile
import io
import logging
from azure.storage.blob import BlobServiceClient, ContainerClient
from concurrent.futures import ThreadPoolExecutor

def upload_blob(container_client, blob_name, file_content):
    """
    Upload a single blob to Azure Blob Storage.
    """
    try:
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(file_content, overwrite=True)
        print(f"Extracted and uploaded {blob_name}")
    except Exception as e:
        logging.error(f"Error uploading {blob_name}: {e}")

def extract_tar_in_memory(storage_account_name, storage_account_key, container_name, tar_blob_name):
    """
    Extracts a .tar file stored in Azure Blob Storage to the same container.
    """
    try:
        blob_service_client = BlobServiceClient(
            account_url=f"https://{storage_account_name}.blob.core.windows.net",
            credential=storage_account_key
        )
        container_client = blob_service_client.get_container_client(container_name)
        tar_blob_client = container_client.get_blob_client(tar_blob_name)

        # Download the .tar file into memory
        tar_stream = io.BytesIO(tar_blob_client.download_blob().readall())

        # Open the .tar file
        with tarfile.open(fileobj=tar_stream, mode='r') as tar:
            with ThreadPoolExecutor() as executor:
                futures = []
                for member in tar.getmembers():
                    file_obj = tar.extractfile(member)
                    if file_obj:
                        file_content = file_obj.read()
                        extracted_blob_name = f"{member.name}"
                        futures.append(executor.submit(upload_blob, container_client, extracted_blob_name, file_content))
                
                # Wait for all uploads to complete
                for future in futures:
                    future.result()

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise

# Example usage
storage_account_name = "albertst"  # Replace with your Azure storage account name
storage_account_key = ""  # Replace with your Azure storage account key
container_name = "masldmice/data"  # Replace with your container name
tar_blob_name = "X204SC23121938-Z01-F001_02.tar"  # Replace with your .tar blob name

# Extract the .tar file stored in Azure Blob Storage
extract_tar_in_memory(storage_account_name, storage_account_key, container_name, tar_blob_name)
