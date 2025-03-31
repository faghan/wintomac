import argparse
import os

from workspace import create_workspace



def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(description="Launch pipeline on Azure")

    parser.add_argument(
        "-o",
        "--org-id",
        type=str,
        required=True,
        help="ID of organization to create a workspace inside it. Note you have to use the ID not the org name.",
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
  
    return parser.parse_args()


def main():
    """Main function to launch a pipeline on Seqera Platform."""
    args = parse_args()

    workspace_features = create_workspace(
        endpoint=args.seqera_endpoint,
        token=args.token,
        org_id=args.org_id,
    )
    print(workspace_features["workspace"]["name"])
    print(f"created workspace")
    #print(f"created workspace {workspace_features["workspace"]["name"]} with workspace ID: {workspace_features["workspace"]["id"]}")


if __name__ == "__main__":
    main()