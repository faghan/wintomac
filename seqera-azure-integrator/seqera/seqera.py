import requests


def seqera_request(
    method: str,
    endpoint: str,
    token: str,
    path: str,
    workspaceId: str | None = None,
    payload: dict | None = None,
    files: dict | None = None,
    params: dict = {},
) -> requests.Response:

    url = f"{endpoint}/{path.strip('/')}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    # Add workspace_id to query params if provided
    if workspaceId:
        params["workspaceId"] = workspaceId

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