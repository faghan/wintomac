import argparse
import os

from seqera.pipeline import launch_pipeline
from seqera.utils import clean_csv


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(description="Launch pipeline on Azure")
    parser.add_argument(
        "-c", "--csv", required=True, help="Path to CSV file in Azure blob storage"
    )
    parser.add_argument(
        "-p",
        "--pipeline-id",
        type=str,
        required=True,
        help="ID of pipeline to launch. Note you have to use the ID not the pipeline name.",
    )
    parser.add_argument(
        "-e",
        "--seqera-endpoint",
        default=os.environ.get("SEQERA_API_ENDPOINT"),
        help="Seqera Platform API endpoint (default: $SEQERA_API_ENDPOINT)",
    )
    parser.add_argument(
        "-t",
        "--token",
        default=os.environ.get("SEQERA_ACCESS_TOKEN"),
        help="Seqera Platform access token (default: $SEQERA_ACCESS_TOKEN)",
    )
    parser.add_argument(
        "-w",
        "--workspace",
        type=int,
        default=os.environ.get("SEQERA_WORKSPACE_ID"),
        help="Seqera Platform workspace ID (default: $TOWER_WORKSPACE_ID)",
    )
    return parser.parse_args()


def main():
    """Main function to launch a pipeline on Seqera Platform."""
    args = parse_args()

    clean_csv_path = clean_csv(args.csv)

    workflow_id = launch_pipeline(
        pipeline_id=args.pipeline_id,
        endpoint=args.seqera_endpoint,
        token=args.token,
        workspace_id=args.workspace,
        params={
            "input": args.csv,
            "outdir": f"az://outputs/{clean_csv_path}",
        },
    )
    print(f"Launched pipeline {args.pipeline_id} with workflow ID: {workflow_id}")


if __name__ == "__main__":
    main()