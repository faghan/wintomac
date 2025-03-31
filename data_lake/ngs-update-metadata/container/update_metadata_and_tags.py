import argparse
import logging
import os
import sys
from pathlib import PurePosixPath
from pathlib import Path

import coloredlogs

# import azure.functions as func
import psycopg2
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobPrefix, BlobServiceClient

_LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
_LOG_MAX_SIZE = 1024 * 1024
_LOG_MAX_FILES = 5


def parse_args(argv):
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--log-file",
        help="Append log messages to file; files are rotated at 1MB",
        type=Path,
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
    )

    return parser.parse_args(argv)


def setup_logging(args):
    coloredlogs.install(fmt=_LOG_FORMAT, level=args.log_level)

    root_log = logging.getLogger()
    if args.log_file is not None:
        handler = logging.handlers.RotatingFileHandler(
            filename=args.log_file, maxBytes=_LOG_MAX_SIZE, backupCount=_LOG_MAX_FILES
        )
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))

        root_log.addHandler(handler)

    # Set the logging level for all azure-* libraries to WARNING
    # The default INFO level will log all request and response headers for REST API call made by the library
    azure_logger = logging.getLogger("azure")
    azure_logger.setLevel(logging.WARNING)


def get_registry_id(sample_id):

    # HACK: tags can not be None, so return "NOT REGISTERED" if a sample is found with null as file_registry_id$

    # set default registry id if not found in Benchling
    registry_id = "NONE"

    # lookup id in Benchling
    conn = None
    connection_string = os.environ["BenchlingConnectionString"]
    try:
        sql = "SELECT CASE WHEN file_registry_id$ IS NULL THEN 'NOT REGISTERED' ELSE file_registry_id$ END FROM biosustain.sequencing_submission_sample WHERE name$ = %s AND archived$ = FALSE;"
        conn = psycopg2.connect(connection_string)
        cur = conn.cursor()
        cur.execute(sql, (sample_id,))
        row = cur.fetchone()
        cur.close()
        if row:
            registry_id = row[0]
    except:
        logging.exception("Exception occurred")
        raise
    finally:
        if conn is not None:
            conn.close()

    return registry_id


def main(argv):

    args = parse_args(argv)

    setup_logging(args)

    logger = logging.getLogger("main")
    logger.info(
        "Executing "
        + __file__
        + " with arguments: "
        + ", ".join(["%s=%s" % (key, value) for (key, value) in args.__dict__.items()])
    )

    account_name = os.environ["NGS_ACCOUNT_NAME"]
    blob_container_name = os.environ["CONTAINER_NAME"]

    credential = DefaultAzureCredential()

    # Get blob service client
    blob_service_client = BlobServiceClient(
        account_url=f"https://{account_name}.blob.core.windows.net",
        credential=credential,
    )

    # Get container client
    container_client = blob_service_client.get_container_client(blob_container_name)

    sample_id = ""
    benchling_registry_id = ""
    depth = 1
    separator = "   "

    def walk_blob_hierarchy(prefix=""):
        nonlocal depth
        nonlocal sample_id
        nonlocal benchling_registry_id
        for item in container_client.walk_blobs(name_starts_with=prefix):
            short_name = item.name[len(prefix) :]
            if isinstance(item, BlobPrefix):
                logger.info("Folder: " + separator * depth + short_name)
                depth += 1
                walk_blob_hierarchy(prefix=item.name)
                depth -= 1
            else:
                if str(item.name).endswith(
                    tuple([".fastq.gz", ".bam", ".csv", ".fastq"])
                ):
                    message = "Blob: " + separator * depth + short_name
                    logger.info(message)

                    # Get blob client
                    blob_client = container_client.get_blob_client(item.name)

                    # get sample id from first part of path
                    blob_path = PurePosixPath(item.name)
                    new_sample_id = blob_path.parts[0]
                    if benchling_registry_id == "" or sample_id != new_sample_id:
                        sample_id = new_sample_id

                        # get Benchling registry id
                        benchling_registry_id = get_registry_id(sample_id)

                    # set tags and metadata
                    data = {
                        "sample_id": sample_id,
                        "entity_registry_id": benchling_registry_id,
                    }
                    blob_client.set_blob_tags(data)
                    blob_client.set_blob_metadata(data)

    walk_blob_hierarchy()


if __name__ == "__main__":
    main(sys.argv[1:])
