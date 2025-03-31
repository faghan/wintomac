#!/bin/bash
for i in {1}
do
echo $i 
curl --location 'http://localhost:7071/runtime/webhooks/EventGrid?functionName=StartNextflowPipeline' \
--header 'aeg-event-type: Notification' \
--header 'Content-Type: application/json' \
--data '{
    "id": "30fc57ec-701e-007d-74a3-59a56a06c86f",
    "data": {
        "api": "PutBlob",
        "clientRequestId": "2d852232-16c5-40ab-43c0-45a37423fba5",
        "requestId": "30fc57ec-701e-007d-74a3-59a56a000000",
        "eTag": "0x8DC27BA85E7529D",
        "contentType": "text/plain",
        "contentLength": 9,
        "blobType": "BlockBlob",
        "blobUrl": "https://biosustaindls.blob.core.windows.net/sandbox/thoeri/raw/project0001/test01.txt",
        "url": "https://biosustaindls.blob.core.windows.net/sandbox/thoeri/raw/project0001/test01.txt",
        "sequencer": "000000000000000000000000000330f00000000000001632",
        "identity": "32858c26-6fed-4874-a6c4-3a0be3d2fc09",
        "storageDiagnostics": {
            "batchId": "e32055c0-5006-0043-00a3-592666000000"
        }
    },
    "topic": "/subscriptions/aee8556f-d2fd-4efd-a6bd-f341a90fa76e/resourceGroups/rg-infrastructure/providers/Microsoft.Storage/storageAccounts/biosustaindls",
    "subject": "/blobServices/default/containers/sandbox/blobs/thoeri/raw/project0001/test01.txt",
    "event_type": "Microsoft.Storage.BlobCreated"
}' &
done