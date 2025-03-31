import logging
import azure.functions as func
import json
from pathlib import Path, PurePosixPath
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
import os
import subprocess
import paramiko
from azure.mgmt.compute import ComputeManagementClient
from azure.batch import BatchServiceClient
from azure.batch.batch_auth import SharedKeyCredentials
import subprocess
import docker

app = func.FunctionApp()

@app.function_name(name="BlobTrigger1")
@app.blob_trigger(arg_name="myblob", 
                  path="raw",
                  connection="CONNECTION_SETTING")
def test_function(myblob: func.InputStream):
   logging.info(f"Python blob trigger function processed blob \n"
                f"Name: {myblob.name}\n"
                f"Blob Size: {myblob.length} bytes")
app = func.FunctionApp()
@func.blob_trigger(arg_name="blob")

def StartNextflowPipeline(blob: func.InputStream):
    logging.info('Blob trigger function processed blob \n'
                 f'Name: {blob.name}\n'
                 f'Blob Size: {blob.length} bytes\n'
                 f'URI: {blob.uri}')

    # Extract container name and blob path from the blob URI
    blob_uri_parts = blob.uri.split('/')
    container_name = blob_uri_parts[-2]
    blob_path = '/'.join(blob_uri_parts[3:-1])

    logging.info(f"Blob uploaded to container '{container_name}' with path '{blob_path}'")

    # Continue with your logic here...
    # For example:
    # - Access the blob using its name
    # - Process the blob
    # - Trigger other actions

    # Example: Log the blob content
    blob_content = blob.read().decode('utf-8')
    logging.info(f"Blob content: {blob_content}")

    # Example: Trigger Nexflow pipeline or any other action
    # subprocess.run(["nexflow", "run", "myPipeline", "--input", blob.name])

