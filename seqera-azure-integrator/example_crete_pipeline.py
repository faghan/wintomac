import yaml
from seqera.seqera import seqera_request
from seqera.create_pipeline import create_pipeline_from_github

if __name__ == "__main__":
    endpoint = "https://api.cloud.seqera.io/"
    token = "eyJ0aWQiOiAxMTA3MX0uMTg4MGZkYzVmNTdhOGZkNzUxZGFhZjc0NjAxYjc4YjRkMjY2ZGEwOQ=="  # Replace with your API token
    workspace_id = "240298380956328"  # Replace with your workspace ID
    pipeline_name = "My_New_Pipeline"
    pipeline_description = "This is a new pipeline from the Nextflow hello world GitHub repository"
    github_repo_url = "https://github.com/nextflow-io/hello"  # GitHub URL of the pipeline
    params = {
        "param1": "value1",
        "param2": "value2",
        # Additional parameters to initialize the pipeline
    }

    try:
        created_pipeline = create_pipeline_from_github(
            endpoint,
            token,
            workspace_id,
            pipeline_name,
            pipeline_description,
            github_repo_url,
            params
        )
        print("Pipeline created successfully:", created_pipeline)
    except Exception as e:
        print("Failed to create pipeline:", e)

# if __name__ == "__main__":
#     endpoint = "https://cloud.seqera.io"
#     token = "eyJ0aWQiOiAxMTA2Mn0uNGNjNjIyN2NhNTgwYzJjZmE0NTgwNGNjYzUwZmRiNmJiMGY2MjYxMg"  # Replace with your API token
#     workspace_id = "240298380956328"  # Replace with your workspace ID
#     pipeline_name = "My_New_Pipeline"
#     pipeline_description = "This is a new pipeline for bioinformatics analysis"
#     # pipeline_config = {
#     #     "container_image": "bioinformatics/image:v1.0",
#     #     "compute_env": "high-performance-compute",
#     #     # Add other necessary configurations like software requirements, etc.
#     # }
#     params = {
#         "param1": "value1",
#         "param2": "value2",
#         # Additional parameters to initialize the pipeline
#     }

#     try:
#         created_pipeline = create_pipeline(
#             endpoint,
#             token,
#             workspace_id,
#             pipeline_name,
#             pipeline_description,
#             pipeline_config,
#             params
#         )
#         print("Pipeline created successfully:", created_pipeline)
#     except Exception as e:
#         print("Failed to create pipeline:", e)