import argparse
import os

from seqera.pipeline import launch_pipeline
from seqera.datasets import add_and_upload_dataset


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(description="Launch pipeline on Azure")
    parser.add_argument(
        "--csv", required=True, help="Path to CSV file in Azure blob storage"
    )
    parser.add_argument(
        "--pipeline-id",
        type=str,
        help="ID of pipeline to launch. If not supplied no pipeline will be launched.",
    )
    parser.add_argument(
        "--storage-account-url",
        default=os.environ.get("AZURE_STORAGE_ACCOUNT_URL"),
        help="Azure Storage account URL, should be in the format https://<storageaccountname>.blob.core.windows.net (default: $AZURE_STORAGE_ACCOUNT_URL)",
    )
    parser.add_argument(
        "--seqera-endpoint",
        default=os.environ.get("SEQERA_API_ENDPOINT"),
        help="Seqera Platform API endpoint (default: $SEQERA_API_ENDPOINT)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("SEQERA_ACCESS_TOKEN"),
        help="Seqera Platform access token (default: $SEQERA_ACCESS_TOKEN)",
    )
    parser.add_argument(
        "--workspace",
        type=int,
        default=os.environ.get("SEQERA_WORKSPACE_ID"),
        help="Seqera Platform workspace ID (default: $TOWER_WORKSPACE_ID)",
    )
    return parser.parse_args()


def main():
    """Main function to add a dataset and optionally launch a pipeline.

    Adds a CSV file as a dataset to Seqera Platform and optionally launches a pipeline
    using that dataset as input. The pipeline output will be written to Azure blob storage
    in a directory named after the dataset.
    """
    args = parse_args()

    dataset_version_details = add_and_upload_dataset(
        csv_path=args.csv,
        storage_account_url=args.storage_account_url,
        endpoint=args.seqera_endpoint,
        token=args.token,
        workspace_id=args.workspace,
    )

    if args.pipeline_id:
        workflow_details = launch_pipeline(
            pipeline_id=args.pipeline_id,
            endpoint=args.seqera_endpoint,
            token=args.token,
            workspace_id=args.workspace,
            params={
                "input": dataset_version_details["url"],
                "outdir": f"az://outputs/${dataset_version_details['datasetName']}/",
            },
        )
        print(
            f"Launched pipeline {args.pipeline_id} with workflow ID: {workflow_details["workflowId"]}"
        )


if __name__ == "__main__":
    main()
