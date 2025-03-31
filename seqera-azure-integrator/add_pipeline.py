
import os
import json
from seqera_add_pipeline import seqera_request


def create_pipeline(
    endpoint: str,
    token: str,
    workspaceId: str
) -> dict:
    pipeline_name = os.getenv("PIPELINE_NAME")
    compute_env_id = os.getenv("COMPUTE_ENV_ID")
    github_repos = os.getenv("GITHUB_REPOS")
    work_dir = os.getenv("WORK_DIR")
    # Prepare minimal create payload
    create_payload = {
        "name": f"{pipeline_name}",
        "description": "Please refer to the Readme file for more information",
        "launch": {
            "computeEnvId": f"{compute_env_id}",
            "runName": "testrun",
            "pipeline": f"{github_repos}",
            "workDir": f"{work_dir}"
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

    # response_json = response.json()
    # pipeline_id = response_json.get("id")
    return response.json()
    # return pipeline_id


# def main():
#     """Main function to launch a pipeline on Seqera Platform."""

#     workflow_id = create_pipeline_from_github(
#         endpoint=os.getenv("SEQERA_API_ENDPOINT"),
#         token=os.getenv("SEQERA_API_TOKEN"),
#         workspace_id=os.getenv("WORKSPACE_ID"),
#         pipeline_name=os.getenv("PIPELINE_NAME"),
#         pipeline_description=os.getenv("PIPELINE_DESCRIPTION"),
#         github_repo_url=os.getenv("GITHUB_REPOS")
#         )
#     print(f"Created pipeline {pipeline_name}")


# if __name__ == "__main__":
#     main()