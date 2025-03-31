import json
import yaml
from seqera.seqera import seqera_request


def get_pipeline_launch_details(
    pipeline_id: str, endpoint: str, token: str, workspace_id: str
) -> dict:
    """Get launch details for a pipeline from the Seqera Platform API.

    Args:
        pipeline_id: ID of the pipeline to get launch details for
        endpoint: Seqera Platform API endpoint URL
        token: Seqera Platform API access token
        workspace_id: ID of the workspace containing the pipeline

    Returns:
        dict: Pipeline launch details including parameters, compute environment, etc.

    Raises:
        requests.exceptions.HTTPError: If the API request fails
    """
    response = seqera_request(
        method="GET",
        endpoint=endpoint,
        token=token,
        path=f"pipelines/{pipeline_id}/launch",
        workspace_id=workspace_id,
    )
    response.raise_for_status()
    return response.json()


def launch_pipeline(
    pipeline_id: int,
    endpoint: str,
    token: str,
    workspace_id: str,
    params: dict = {},
) -> dict:
    """Launch a pipeline using Seqera Platform.

    Args:
        pipeline_id: ID of the pipeline to launch
        endpoint: Seqera Platform API endpoint URL
        token: Seqera Platform API access token
        workspace_id: ID of the workspace containing the pipeline
        params: Dictionary of pipeline parameters to override defaults

    Returns:
        str: ID of the launched workflow

    Raises:
        requests.exceptions.HTTPError: If the API request fails
        ValueError: If pipeline parameters cannot be parsed as JSON or YAML
    """

    # Get pipeline details from Seqera Platform
    pipeline_details = get_pipeline_launch_details(
        pipeline_id, endpoint, token, workspace_id
    )

    # Try and parse paramsText as JSON first, then try YAML
    try:
        pipeline_params = json.loads(pipeline_details["launch"]["paramsText"])
    except json.JSONDecodeError:
        try:
            pipeline_params = yaml.safe_load(pipeline_details["launch"]["paramsText"])
        except yaml.YAMLError as e:
            raise ValueError(
                f"Failed to parse paramsText as JSON or YAML: {pipeline_details['launch']['paramsText']}.\n{e}"
            )

    # Update params and convert back to YAML
    pipeline_params.update(params)

    # Prepare minimal launch payload
    launch_payload = {
        "launch": {
            "id": pipeline_details["launch"]["id"],
            "computeEnvId": pipeline_details["launch"]["computeEnv"]["id"],
            "pipeline": pipeline_details["launch"]["pipeline"],
            "workDir": pipeline_details["launch"]["workDir"],
            "revision": pipeline_details["launch"]["revision"],
            "configProfiles": pipeline_details["launch"]["configProfiles"],
            "paramsText": yaml.dump(pipeline_params),
            "pullLatest": pipeline_details["launch"]["pullLatest"],
            "stubRun": pipeline_details["launch"]["stubRun"],
        }
    }

    response = seqera_request(
        method="POST",
        endpoint=endpoint,
        token=token,
        path="workflow/launch",
        workspace_id=workspace_id,
        payload=launch_payload,
    )
    response.raise_for_status()
    return response.json()
