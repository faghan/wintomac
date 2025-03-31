#!/usr/bin/env python3
import argparse
import os
import sys

from azure.core.exceptions import AzureError
from azure.identity import ClientSecretCredential
from azure.keyvault.secrets import SecretClient


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("key", help="Key-vault value to retrieve")

    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    client = SecretClient(
        vault_url=f"https://{os.environ['AZURE_KEY_VAULT']}.vault.azure.net",
        credential=ClientSecretCredential(
            client_id=os.environ["AZURE_CLIENT_ID"],
            client_secret=os.environ["AZURE_CLIENT_SECRET"],
            tenant_id=os.environ["AZURE_TENANT_ID"],
        ),
    )

    try:
        print(client.get_secret(args.key).value)
    except AzureError as error:
        print("ERROR fetching secret %r" % (args.key,), file=sys.stderr)
        print(str(error), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
