import tarfile
import io
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
import logging

def extract_tar_in_memory(storage_account_name, storage_account_key, container_name, tar_blob_name):
    """
    Extracts a .tar file stored in Azure Blob Storage to the same container.

    Parameters:
    storage_account_name (str): The name of the Azure storage account.
    storage_account_key (str): The access key for the Azure storage account.
    container_name (str): The name of the container.
    tar_blob_name (str): The name of the .tar blob to extract.
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
            for member in tar.getmembers():
                # Extract each file into memory
                file_obj = tar.extractfile(member)
                if file_obj is not None:
                    file_content = file_obj.read()

                    # Define the path for the extracted file in the storage container
                    extracted_blob_name = f"{member.name}"

                    # Create a blob client for the extracted file
                    extracted_blob_client = container_client.get_blob_client(extracted_blob_name)

                    # Upload the extracted file back to Azure Blob Storage
                    extracted_blob_client.upload_blob(file_content, overwrite=True)
                    print(f"Extracted and uploaded {member.name} to {extracted_blob_name}")

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
