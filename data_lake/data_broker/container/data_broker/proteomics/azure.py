import datetime

from django.conf import settings

from azure.storage.blob import (
    BlobServiceClient,
    ContainerSasPermissions,
    generate_blob_sas,
)


def get_container_client():
    blob_account_url = (
        f"https://{settings.AZURE_PROTEOMICS_ACCOUNT}.blob.core.windows.net"
    )

    service_client = BlobServiceClient(
        account_url=blob_account_url, credential=settings.AZURE_PROTEOMICS_SECRET,
    )

    return service_client.get_container_client(settings.AZURE_PROTEOMICS_CONTAINER)


def get_blob_sas_url(blob_name, duration=datetime.timedelta(hours=1)):
    azure_host = f"https://{settings.AZURE_PROTEOMICS_ACCOUNT}.blob.core.windows.net"
    sas_token = generate_blob_sas(
        account_name=settings.AZURE_PROTEOMICS_ACCOUNT,
        container_name=settings.AZURE_PROTEOMICS_CONTAINER,
        account_key=settings.AZURE_PROTEOMICS_SECRET,
        blob_name=blob_name,
        permission=ContainerSasPermissions(read=True),
        expiry=datetime.datetime.utcnow() + duration,
    )

    return f"{azure_host}/{settings.AZURE_PROTEOMICS_CONTAINER}/{blob_name}?{sas_token}"
