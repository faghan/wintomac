from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, BlobClient

from seqera.seqera import seqera_request
from seqera.utils import clean_csv


def create_blob_service(account_url) -> BlobServiceClient:
    """Create an Azure Blob Service client using default credentials.

    Args:
        account_url: Azure Storage account URL in format https://<storageaccountname>.blob.core.windows.net

    Returns:
        BlobServiceClient: Authenticated client for interacting with Azure Blob Storage
    """
    default_credential = DefaultAzureCredential()

    # Create the BlobServiceClient object
    return BlobServiceClient(account_url, credential=default_credential)


def create_blob_client(blob_service: BlobServiceClient, csv_path: str) -> BlobClient:
    """Create an Azure Blob Client for accessing a specific CSV file.

    Args:
        blob_service: Authenticated Azure Blob Service client
        csv_path: Path to CSV file in Azure blob storage, with optional az:// prefix

    Returns:
        BlobClient: Client for accessing the specific blob

    Raises:
        ValueError: If the specified CSV file does not exist
    """
    # Parse container and blob path from csv_path
    path_without_prefix = csv_path.lstrip("az://")
    container_name = path_without_prefix.split("/")[0]
    blob_path = "/".join(path_without_prefix.split("/")[1:]).strip("/")
    blob_client = blob_service.get_container_client(container_name).get_blob_client(
        blob_path
    )

    if not blob_client.exists():
        raise ValueError(f"CSV file {csv_path} does not exist")

    return blob_client


def list_datasets(endpoint: str, token: str, workspace_id: str) -> list:
    """List all datasets in the workspace.

    Args:
        endpoint: Seqera Platform API endpoint URL
        token: Seqera Platform API access token
        workspace_id: ID of the workspace to list datasets from

    Returns:
        list: List of dataset objects from the workspace

    Raises:
        requests.exceptions.HTTPError: If the API request fails
    """
    response = seqera_request(
        "GET", endpoint, token, "datasets", workspace_id=workspace_id
    )
    response.raise_for_status()
    return response.json()["datasets"]


def find_dataset_by_name(
    name: str, endpoint: str, token: str, workspace_id: str
) -> dict | None:
    """Find a dataset by name in the workspace.

    Args:
        name: Name of dataset to find
        endpoint: Seqera Platform API endpoint URL
        token: Seqera Platform API access token
        workspace_id: ID of the workspace to search in

    Returns:
        dict | None: Dataset object if found, None if not found
    """
    datasets = list_datasets(endpoint, token, workspace_id)
    return next((d for d in datasets if d["name"] == name), None)


def add_dataset(csv_path: str, endpoint: str, token: str, workspace_id: str) -> str:
    """Add CSV file as dataset to Seqera Platform.

    Args:
        csv_path: Path to CSV file in Azure blob storage
        endpoint: Seqera Platform API endpoint URL
        token: Seqera Platform API access token
        workspace_id: ID of the workspace to add dataset to

    Returns:
        str: ID of the created or existing dataset

    Raises:
        requests.exceptions.HTTPError: If the API request fails
    """
    csv_name = clean_csv(csv_path)

    # Check if dataset already exists
    existing_dataset = find_dataset_by_name(csv_name, endpoint, token, workspace_id)
    if existing_dataset:
        print(f"Dataset {csv_name} already exists, using existing dataset")
        return existing_dataset["id"]

    payload = {
        "name": csv_name,
        "description": f"Dataset from Azure blob storage: {csv_path}",
    }

    response = seqera_request(
        method="POST",
        endpoint=endpoint,
        token=token,
        path="datasets",
        workspace_id=workspace_id,
        payload=payload,
    )
    response.raise_for_status()
    return response.json()["dataset"]["id"]


def upload_dataset_content(
    dataset_id: str,
    blob_client: BlobClient,
    endpoint: str,
    token: str,
    workspace_id: str,
    blob_service: BlobServiceClient,
    header: bool = True,
) -> dict:
    """Upload CSV content to an existing dataset.

    Args:
        dataset_id: ID of dataset to upload content to
        blob_client: Azure Blob Client for accessing the CSV file
        endpoint: Seqera Platform API endpoint URL
        token: Seqera Platform API access token
        workspace_id: ID of the workspace containing the dataset
        blob_service: Azure Blob Service client
        header: Whether the CSV file has a header row (default: True)

    Returns:
        dict: Details of the uploaded dataset version

    Raises:
        requests.exceptions.HTTPError: If the API request fails
    """
    # Prepare file upload
    files = {"file": ("dataset.csv", blob_client.download_blob().readall(), "text/csv")}

    params = {"header": "true"} if header else None
    response = seqera_request(
        method="POST",
        endpoint=endpoint,
        token=token,
        path=f"workspaces/{workspace_id}/datasets/{dataset_id}/upload",
        files=files,
        params=params or {},
    )
    response.raise_for_status()
    return response.json()["version"]


def add_and_upload_dataset(
    csv_path: str,
    storage_account_url: str,
    endpoint: str,
    token: str,
    workspace_id: str,
) -> dict:
    """Add a CSV file as a dataset and upload its content to Seqera Platform.

    Args:
        csv_path: Path to CSV file in Azure blob storage
        storage_account_url: Azure Storage account URL in format https://<storageaccountname>.blob.core.windows.net
        endpoint: Seqera Platform API endpoint URL
        token: Seqera Platform API access token
        workspace_id: ID of the workspace to add dataset to

    Returns:
        dict: Details of the uploaded dataset version

    Raises:
        requests.exceptions.HTTPError: If any API request fails
        ValueError: If the CSV file does not exist
    """
    dataset_id = add_dataset(csv_path, endpoint, token, workspace_id)
    blob_service = create_blob_service(storage_account_url)
    blob_client = create_blob_client(blob_service, csv_path)
    dataset_version_details = upload_dataset_content(
        dataset_id, blob_client, endpoint, token, workspace_id, blob_service
    )
    return dataset_version_details
