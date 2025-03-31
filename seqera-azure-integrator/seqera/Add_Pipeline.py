
import json
from seqera import seqera_request


def create_pipeline(
    endpoint: str,
    token: str,
    workspaceId: str
) -> dict:
    
    # Prepare minimal create payload
    create_payload = {
        "name": "testfatemehghhg",
        "description": "this pileine is for test",
        "launch": {
            "computeEnvId": "45079qWB5yR6AQcJWsUs9h",
            "runName": "testrun",
            "pipeline": "https://github.com/nextflow-io/hello",
            "workDir": "az://workdirseqera"
        }
    }

    response = seqera_request(
        method="POST",
        endpoint=endpoint,
        token=token,
        path=f"pipelines?workspaceId={workspaceId}",
        payload=create_payload
    )
    response.raise_for_status()
    return response.json()
