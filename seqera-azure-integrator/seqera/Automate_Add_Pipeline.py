import argparse
import os

from Add_Pipeline import create_pipeline



def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(description="Launch pipeline on Azure")

    parser.add_argument(
        "-w",
        "--workspaceId",
        type=str,
        required=True,
        help="ID of workspace to create a pipeline inside it. Note you have to use the ID not the workspace name.",
    )
    parser.add_argument(
        "-e",
        "--seqera-endpoint",
        # default=os.environ.get("SEQERA_API_ENDPOINT"),
        help="Seqera Platform API endpoint (default: $SEQERA_API_ENDPOINT)"
    )
    parser.add_argument(
        "-t",
        "--token",
        # default=os.environ.get("SEQERA_ACCESS_TOKEN"),
        help="Seqera Platform access token (default: $SEQERA_ACCESS_TOKEN)"
    )
  
    return parser.parse_args()


def main():
    """Main function to launch a pipeline on Seqera Platform."""
    args = parse_args()

    workspace_features = create_pipeline(
        endpoint=args.seqera_endpoint,
        token=args.token,
        workspaceId=args.workspaceId
    )
    print(workspace_features["pipeline"]["name"])
    print(f"created pipeline")
    #print(f"created workspace {workspace_features["workspace"]["name"]} with workspace ID: {workspace_features["workspace"]["id"]}")


if __name__ == "__main__":
    main()