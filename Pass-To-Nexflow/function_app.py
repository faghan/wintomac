
import logging
import azure.functions as func
import json
from pathlib import Path, PurePosixPath
from azure.identity import DefaultAzureCredential
from azure.mgmt.batch import BatchManagementClient
from azure.storage.blob import BlobServiceClient
import os
import paramiko
from azure.mgmt.compute import ComputeManagementClient
from azure.batch import BatchServiceClient
from azure.batch.batch_auth import SharedKeyCredentials
import subprocess
import docker

app = func.FunctionApp()

@app.event_grid_trigger(arg_name="event")
def StartNextflowPipeline(event: func.EventGridEvent):
    result = json.dumps({
        'id': event.id,
        'data': event.get_json(),
        'topic': event.topic,
        'subject': event.subject,
        'event_type': event.event_type,
    })

    logging.info('Python EventGrid trigger processed an event: %s', result)

    account_name = os.environ["DATA_LAKE_ACCOUNT_NAME"]
    logging.warning("Account name: %s", account_name)

    blob_path = PurePosixPath(*Path(event.subject).parts[6:])

    blob_container_name = Path(event.subject).parts[4]

    logging.info(f"Setting metadata on file: {blob_container_name}/{blob_path}")

    # Acquire a credential object for the app identity. When running in the cloud,
    # DefaultAzureCredential uses the app's managed identity or user-assigned service principal.
    # When run locally, DefaultAzureCredential relies on environment variables named
    # AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, and AZURE_TENANT_ID.
    credential = DefaultAzureCredential()
 
     # Get blob service client
    blob_service_client = BlobServiceClient(
        account_url=f"https://{account_name}.blob.core.windows.net",
        credential=credential,
    )

    # Get container client
    container_client = blob_service_client.get_container_client(blob_container_name)

    # Get blob client
    blob_client = container_client.get_blob_client(str(blob_path))

    logging.warning("blob_name: %s", blob_client.blob_name)

    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    # # Build Docker image
    # work_directory = "/home/faghan/repos/data-lake/cfb-datalake-func"
    # dockerfile_path = os.path.join(work_directory, "Dockerfile")
    # image_name = "my_image_test"
    # subprocess.run(["docker", "build", "-t", image_name, "."])

    container_name_Nextflow = "testmaindl"
    file_name_Nextflow = "hello.txt" 
    # Construct blob URI
    blob_uri = f"az://{container_name_Nextflow}/{file_name_Nextflow}"

    # Set input and output paths for Nextflow pipeline
    os.environ["NXF_PARAMS_FILE"] = blob_uri  # Pass blob URI as input file
    os.environ["NXF_PARAMS_OUTDIR"] = "az://{container_name_Nextflow}/{result_new}"  # Specify output directory

    compute_client = ComputeManagementClient(credential, subscription_id)

    # get VM

    vm_name = "vm-fatemeh"
    resource_group_name = "rg-test_Fatemeh"
    vm_address = '172.205.169.175'
    vm_username = 'azureuser'
    private_key_path = '/home/faghan/.ssh/vm-fatemeh_key.pem'
    vm = compute_client.virtual_machines.get(resource_group_name, vm_name, expand='instanceView')

    vm_status = vm.instance_view.statuses[1]

    for s in vm.instance_view.statuses:
        logging.warning("status: %s - %s", s.code, s.display_status)

    # State can be:
    # deallocated, deallocating, running, starting, stopped, stopping, unknown
    # start VM
    if(vm.instance_view.statuses[1].code != "PowerState/running"):
        logging.warning("Starting VM...")
        async_vm_start = compute_client.virtual_machines.begin_start(resource_group_name, vm_name)
        async_vm_start.wait()
    print("The status of VM is Running now.")
    
    # Establish SSH connection to VM
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # Load the private key
    private_key = paramiko.RSAKey.from_private_key_file(private_key_path)

    commands = [
    "git clone https://github.com/F-Gh2015/Nextflow-Pipeline",
    "cd Nextflow-Pipeline/ && /home/azureuser/nextflow run main_test_two.nf -profile az_test -c nextflow_test_two.config -w az://testmaindl",
    "cd /home/azureuser && rm -rf Nextflow-Pipeline",
    # Add more commands here if needed
    ]       
    try:
        # Connect to the VM
        ssh_client.connect(hostname=vm_address, username=vm_username, pkey=private_key)

        # Execute commands or interact with the VM
        stdin, stdout, stderr = ssh_client.exec_command('uname -a')
        print("Output:")
        for line in stdout:
            print(line.strip())

        for command in commands:
            print(f"Executing command: {command}")
            stdin, stdout, stderr = ssh_client.exec_command(command)
        
        # Print command output
            print(stdout.read().decode())
            print(stderr.read().decode())

        # Close the SSH connection
        ssh_client.close()

    except paramiko.AuthenticationException:
        print("Authentication failed, please check your credentials.")
    except paramiko.SSHException as e:
        print("SSH connection failed:", str(e))

    vm = compute_client.virtual_machines.get(resource_group_name, vm_name, expand='instanceView')
    vm_status = vm.instance_view.statuses[1]

    # Shut down VM
    if vm_status.code == "PowerState/running":
        logging.warning("Shutting down VM...")
        async_vm_shutdown = compute_client.virtual_machines.begin_deallocate(resource_group_name, vm_name)
        async_vm_shutdown.wait()
        logging.warning("VM has been shut down.")
    print("The status of VM is Stopped(deallocated) now.")
    
    # Initialize Batch service client
    batch_account_name = "testfatemeh"
    batch_account_key = ""
    credentials = SharedKeyCredentials(batch_account_name, batch_account_key)
    batch_url = "https://testfatemeh.westeurope.batch.azure.com"
    batch_client = BatchServiceClient(credentials, batch_url=batch_url)


    

    # Get list of jobs in the Batch account
    jobs = batch_client.job.list()

    # Iterate through the jobs and delete each one from the specified Batch account
    for job in jobs:
    # Check if the job belongs to the specified Batch account
        # if job.id.startswith(f"{batch_account_name}_"):
        print("Deleting job:", job.id)
        batch_client.job.delete(job_id=job.id)
        print("Job deleted successfully.")

    print("All jobs deleted from the specified Batch account.")
    # Get list of pools in the Batch account
    pools = batch_client.pool.list()

    # Iterate through the pools and delete each one from the specified Batch account
    for pool in pools:
        print("Deleting pool:", pool.id)
        batch_client.pool.delete(pool_id=pool.id)
        print("Pool deleted successfully.")

    print("All pools deleted from the specified Batch account.")

    storageAccountName = "sttestfatemeh",
    storageAccountKey= "",
# @retry(RuntimeError, tries=3)
# def get_vm(resource_group_name, vm_name):
#     '''
#     you need to retry this just in case the credentials token expires,
#     that's where the decorator comes in
#     this will return all the data about the virtual machine
#     '''
#     return compute_client.virtual_machines.get(
#         resource_group_name, vm_name, expand='instanceView')

# @retry((RuntimeError, IndexError,), tries=-1)
# def get_vm_status(resource_group_name, vm_name):
#     '''
#     this will just return the status of the virtual machine
#     sometime the status may be unknown as shown by the azure portal;
#     in that case statuses[1] doesn't exist, hence retrying on IndexError
#     also, it may take on the order of minutes for the status to become
#     available so the decorator will bang on it forever
#     '''
#     return compute_client.virtual_machines.get(resource_group_name, vm_name, expand='instanceView').instance_view.statuses[1].display_status
