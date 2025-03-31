import requests
import json

# Define the Event Grid event payload
event = {
    "id": "test-id",
    "eventType": "Microsoft.Storage.BlobCreated",
    "subject": "/blobServices/default/containers/raw/blobs/test.txt",
    "data": {
        "api": "PutBlockList",
        "clientRequestId": "test-request-id",
        "requestId": "test-request-id",
        "eTag": "test-etag",
        "contentType": "text/plain",
        "contentLength": 524288,
        "blobType": "BlockBlob",
        "url": "https://your-storage-account.blob.core.windows.net/raw/test.txt",
        "sequencer": "0000000000000000000000000000000000000000000000000000000000000000",
        "storageDiagnostics": {
            "batchId": "test-batch-id"
        }
    },
    "dataVersion": "",
    "metadataVersion": "1",
    "eventTime": "2024-06-19T12:34:56.789Z"
}

# Wrap the event in a list as Event Grid sends a list of events
events = [event]

# Post the event to the local Azure Functions runtime
response = requests.post(
    "http://localhost:7071/runtime/webhooks/eventgrid?functionName=PipelineOrchestrator_v1",
    data=json.dumps(events),
    headers={"Content-Type": "application/json"}
)

# Print the response from the function
print(response.status_code)
print(response.text)
