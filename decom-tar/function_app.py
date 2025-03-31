import logging
import tarfile
import os
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
import azure.functions as func

# Connection string for the Azure Blob Storage
STORAGE_CONNECTION_STRING = ""
CONTAINER_NAME = "masldmice"

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="http_trigger")
def http_trigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    # Local file path for test.tar
    tar_file_path = "masldmice/data/X204SC23121938-Z01-F001_01.tar"
    
    # Decompress the tar file
    extracted_files_path = "masldmice/data"
    if not os.path.exists(extracted_files_path):
        os.makedirs(extracted_files_path)

    try:
        with tarfile.open(tar_file_path, 'r') as tar:
            tar.extractall(path=extracted_files_path)
        logging.info('Tar file decompressed successfully.')
    except Exception as e:
        logging.error(f"Failed to decompress tar file: {str(e)}")
        return func.HttpResponse("Failed to decompress tar file.", status_code=500)

    # Initialize the Blob Service Client
    blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)

    # Upload extracted files to the blob container
    try:
        for root, dirs, files in os.walk(extracted_files_path):
            for file in files:
                file_path = os.path.join(root, file)
                blob_client = container_client.get_blob_client(os.path.relpath(file_path, extracted_files_path))
                
                with open(file_path, "rb") as data:
                    blob_client.upload_blob(data, overwrite=True)
                logging.info(f'File {file} uploaded successfully to blob storage.')
    except Exception as e:
        logging.error(f"Failed to upload files to blob storage: {str(e)}")
        return func.HttpResponse("Failed to upload files to blob storage.", status_code=500)

    return func.HttpResponse("Files decompressed and uploaded successfully.", status_code=200)
