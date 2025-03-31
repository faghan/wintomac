from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
import os
import subprocess
import time

# Azure credentials
subscription_id = 'aee8556f-d2fd-4efd-a6bd-f341a90fa76e'
resource_group = 'rg-test_Fatemeh'
vm_name = 'vm-fatemeh'
location = 'West Europe'

# Create Azure Compute Management Client
credential = DefaultAzureCredential()
compute_client = ComputeManagementClient(credential, subscription_id)

# Start the VM
print("Starting the VM...")
compute_client.virtual_machines.start(resource_group, vm_name)
print("VM started.")

# Clone repository and execute code
print("Cloning repository and executing code...")
os.system("git clone https://github.com/F-Gh2015/Nextflow-Pipeline")