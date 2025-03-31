import os
import re
import logging
import requests
import azure.functions as func
from add_pipeline import create_pipeline
from launch_pipeline import launch_pipeline

app = func.FunctionApp()

seqera_api_endpoint = os.getenv("SEQERA_API_ENDPOINT") 
seqera_workspace_id = os.getenv("WORKSPACE_ID")
github_repos = os.getenv("GITHUB_REPOS")
seqera_token = os.getenv("SEQERA_API_TOKEN")

@app.blob_trigger(arg_name="myblob", path="raw/{name}", 
                  connection="AzureWebJobsStorage") 
def BlobTriggerFunction(myblob: func.InputStream):
    file_name = myblob.name.split("/")[-1]

    # Check if filename matches "sample*.csv"
    if re.match(r"^sample.*\.csv$", file_name):
        logging.info("Upload happened: Triggering Nextflow pipeline.")
        logging.info(f"Processed blob: {file_name}")
        logging.info(f"Blob size: {myblob.length} bytes")
        pipeline_features = create_pipeline(
            endpoint = seqera_api_endpoint,
            token = seqera_token,
            workspaceId = seqera_workspace_id
        )
        pipeline_id = pipeline_features['pipeline']['pipelineId']

        workflow_id = launch_pipeline(
            pipeline_id = pipeline_id,
            endpoint = seqera_api_endpoint,
            token = seqera_token,
            workspace_id = seqera_workspace_id,
        )
        print(f"Launched pipeline {pipeline_id} with workflow ID: {workflow_id}")
    else:
        logging.info("File uploaded but does not match pattern. Ignoring.")




# def trigger_nextflow_pipeline():
#     """Trigger a Nextflow pipeline on Seqera."""
#     api_token = os.getenv("SEQERA_API_TOKEN")
#     if not api_token:
#         logging.error("SEQERA_API_TOKEN not set in environment variables.")
#         return

#     headers = {
#         "Authorization": f"Bearer {api_token}",
#         "Content-Type": "application/json"
#     }

#     payload = {
#         "workspaceId": SEQERA_WORKSPACE_ID,
#         "name": "MyPipeline",
#         "description": "A minimal pipeline",
#         "launch": {
#             "pipeline": GITHUB_PIPELINE_URL,  
#             "workDir": "az://workdirseqera",
#             "computeEnvId": "45079qWB5yR6AQcJWsUs9h",
#             "revision": "main",
#             "paramsText": "{}",
#             "pullLatest": False,
#             "stubRun": False
#         }
#     }

#     response = requests.post(f"{seqera_api_url}/pipelines", json=payload, headers=headers)

#     if response.status_code == 200:
#         logging.info("Nextflow pipeline triggered successfully.")
#     else:
#         logging.error(f"Failed to trigger pipeline: {response.status_code} - {response.text}")




# @app.blob_trigger(arg_name="myblob", path="raw/{name}", 
#                   connection="AzureWebJobsStorage") 
# def BlobTriggerFunction(myblob: func.InputStream):
#     file_name = myblob.name.split("/")[-1]

#     # Check if filename matches "sample*.csv"
#     if re.match(r"^sample.*\.csv$", file_name):
#         logging.info("Upload happened: We are waiting for another step.")
#     else:
#         logging.info("File uploaded but does not match pattern. Ignoring.")

#     # Log blob details
#     logging.info(f"Processed blob: {file_name}")
#     logging.info(f"Blob size: {myblob.length} bytes")

