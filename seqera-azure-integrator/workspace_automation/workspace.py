import json
from seqera import seqera_request


def create_workspace(
    endpoint: str,
    token: str,
    org_id: str,
) -> dict:
    
    # Prepare minimal create payload
    create_payload = {
    "workspace": {
        "name": "AtiehWorspaceCreation3",
        "fullName": "Atieh Workspace Creation3",
        "description": "Atieh Workspace Creation3",
        "visibility": "PRIVATE"
    }
    }

    response = seqera_request(
        method="POST",
        endpoint=endpoint,
        token=token,
        path=f"orgs/{org_id}/workspaces",
        payload=create_payload,
    )
    response.raise_for_status()
    return response.json()