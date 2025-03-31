#!/usr/bin/env python3
import argparse
import json
import logging
import os
import time

from datetime import datetime, timedelta, timezone
from typing import Dict

from azure.batch import BatchServiceClient
from azure.batch.batch_auth import SharedKeyCredentials

# from azure.identity import DefaultAzureCredential
import azure.batch.models as batchmodels

logging.basicConfig(level=logging.INFO)

## TODO: Get credentials from Azure Key Vault
credentials = SharedKeyCredentials(
    os.environ["AZURE_BATCH_ACCOUNT_NAME"], os.environ["AZURE_BATCH_ACCOUNT_KEY"]
)

## For when Microsoft pull their thumb out and do some work
# credentials = DefaultAzureCredential()
batch_client = BatchServiceClient(
    credentials, batch_url=os.environ["AZURE_BATCH_ACCOUNT_URL"]
)


def get_args() -> argparse.Namespace:
    """Get arguments from the command line.

    Returns:
        argparse.Namespace: Arguments from the command line
    """
    parser = argparse.ArgumentParser(description="Clearup Azure Batch Jobs")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to keep jobs before deletion",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force termination of jobs even if there are active tasks",
    )
    return parser.parse_args()


def sleep(timeout, retry=3):
    """Decorator to retry a function call if it fails.

    Args:
        timeout (int): The number of seconds to sleep between retries.
        retry (int, optional): The maximum number of retries. Defaults to 3.

    Returns:
        None

    """

    def the_real_decorator(function):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < retry:
                try:
                    value = function(*args, **kwargs)
                except batchmodels.BatchErrorException as e:
                    logging.debug(
                        f"Batch error, likely the API limit, waiting for {timeout} seconds before retrying."
                    )
                    time.sleep(timeout)
                    logging.debug(f"Retrying {function.__name__}. Attempt {retries}")
                    retries += 1

        return wrapper

    return the_real_decorator


def job_is_old(job: batchmodels.CloudJob, time: timedelta) -> bool:
    """Given a job and a time, return True if the job is older than the time.

    Args:
        job (batchmodels.CloudJob): Azure Batch CloudJob object from Batch client.
        time (timedelta): Time to compare against.

    Returns:
        bool: True if the job is older than the time from creation time.
    """
    return time > datetime.now(timezone.utc) - job.last_modified


def job_is_empty(job: batchmodels.CloudJob) -> bool:
    """Given a job, return True if the job has no tasks.

    Args:
        job (batchmodels.CloudJob): Azure Batch CloudJob object from Batch client.

    Returns:
        bool: True if the job has no tasks.
    """
    task_counts = batch_client.job.get_task_counts(job_id=job.id).task_counts
    total_tasks = task_counts.active + task_counts.failed + task_counts.running
    return total_tasks < 1


@sleep(5, 3)
def clearup_job(
    job: batchmodels.CloudJob, time: timedelta = timedelta(days=7), force: bool = False
) -> Dict[str, str]:
    """Clearup Azure Batch Jobs based on age and task status.

    Args:
        job (batchmodels.CloudJob): Azure Batch CloudJob object from Batch client.
        time (timedelta, optional): Delete jobs older than `time`. Defaults to timedelta(days=7).
        force (bool, optional): Terminate jobs even if they have active tasks within them. Defaults to False.

    Returns:
        Dict[str, str]: Dictionary of job id and status.
    """
    # Ignore starting jobs
    if job.state == "enabling":
        logging.info(
            json.dumps(
                {
                    "jobId": {job.id},
                    "status": "starting",
                    "reason": "still_starting",
                },
                default=str,
            )
        )
        return {"job": job.id, "status": "starting"}
    # Delete old jobs
    elif job_is_old(job, time):
        batch_client.job.delete(job_id=job.id)
        logging.info(
            json.dumps(
                {
                    "jobId": {job.id},
                    "status": "deleted",
                    "reason": f"Older than {time}",
                },
                default=str,
            )
        )
        return {"job": job.id, "status": "deleted"}
    # Terminate active jobs with no tasks
    elif (job_is_empty(job) or force is True) and job.state == "active":
        batch_client.job.terminate(job_id=job.id)
        logging.info(
            json.dumps(
                {
                    "jobId": {job.id},
                    "status": "terminated",
                    "reason": "empty" if force is False else "force",
                },
                default=str,
            )
        )
        return {"job": job.id, "status": "terminated"}
    # Ignore other jobs
    else:
        logging.info(
            json.dumps(
                {"jobId": {job.id}, "status": "ignore", "reason": "no_action"},
                default=str,
            )
        )
        return {"job": job.id, "status": "no action"}


def clearup_jobs(days: int = 7, force: bool = False) -> list[Dict[str, str]]:
    """Clearup Azure Batch Jobs based on age and task status.

    Args:
        days (int, optional): Delete jobs older than `days`. Defaults to 7.
        force (bool, optional): Terminate jobs even if they have active tasks within them. Defaults to False.
    """
    n_days = timedelta(days=days)  # delete jobs older than n_days
    jobs = [
        clearup_job(job, time=n_days, force=force) for job in batch_client.job.list()
    ]
    logging.info("Job clearup complete")
    return jobs


if __name__ == "__main__":
    args = get_args()
    n_days = timedelta(days=args.days)  # delete jobs older than n_days
    clearup_jobs(days=args.days, force=args.force)
    logging.info("Job clearup complete")
    clearup_pools(days=args.days, force=args.force)
