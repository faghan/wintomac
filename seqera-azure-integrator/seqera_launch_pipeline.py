import requests


def seqera_request_launch(
    method: str,
    endpoint: str,
    token: str,
    path: str,
    workspace_id: str | None = None,
    payload: dict | None = None,
    files: dict | None = None,
    params: dict = {},
) -> requests.Response:
    """Make a request to Seqera Platform API.

    Args:
        method: HTTP method to use (GET, POST, etc)
        endpoint: Base URL of Seqera Platform API
        token: API access token for authentication
        path: API endpoint path to request
        workspace_id: Optional workspace ID to scope request to
        payload: Optional JSON payload to send with request
        files: Optional files to upload with request
        params: Optional query parameters to include

    Returns:
        requests.Response: Response from the API request

    Raises:
        requests.exceptions.RequestException: If the request fails
    """
    url = f"{endpoint}/{path.strip('/')}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    # Add workspace_id to query params if provided
    if workspace_id:
        params["workspaceId"] = workspace_id

    if files is None:
        headers["Content-Type"] = "application/json"
        response = requests.request(
            method, url, headers=headers, json=payload, params=params
        )
    else:
        response = requests.request(
            method, url, headers=headers, files=files, params=params
        )

    return response