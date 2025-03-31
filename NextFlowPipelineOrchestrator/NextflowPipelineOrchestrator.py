import io
import os
import logging
import uuid
import paramiko
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.keyvault.secrets import SecretClient
from dotenv import load_dotenv
import vm_creation  
import st_creation 
import batch_creation 
import kv_update

load_dotenv()


subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
resource_group = os.getenv('RESOURCE_GROUP')
vault_name = os.getenv('VAULT_NAME')
user_assigned_identity_id = os.getenv('USER_ASSIGNED_IDENTITY_ID')
user_assigned_identity_object_id = os.getenv('USER_ASSIGNED_IDENTITY_OBJECT_ID')  #Object ID or Principal ID
ip_range = os.getenv('IP_RANGE')
location = 'westeurope'
admin_username = 'azureuser'

# Print out environment variables for debugging
print(f"Subscription ID: {subscription_id}")
print(f"Resource Group: {resource_group}")
print(f"Vault Name: {vault_name}")
print(f"User Assigned Identity ID: {user_assigned_identity_id}")
print(f"IP Range: {ip_range}")


# public_ip, public_ip_id = vm_creation.create_public_ip(resource_group, location)
# print(f"{public_ip},{public_ip_id}")
# Validate required environment variables
if not subscription_id or not resource_group or not vault_name or not user_assigned_identity_id:
    raise ValueError("Required environment variables are missing.")

credential = DefaultAzureCredential()
compute_client = ComputeManagementClient(credential, subscription_id)
network_client = NetworkManagementClient(credential, subscription_id)
vm_sizes = {'1': {'size': 'Standard_B1s', 'os_disk_size_gb': 30}}

print('Select a VM size:')
for key, value in vm_sizes.items():
    print(f'{key}: {value["size"]}')

selected_size_key = input('Enter the number corresponding to the VM size: ')
selected_size = vm_sizes[selected_size_key]
vm_name = f"vm-{uuid.uuid4().hex[:8]}"

vnet_name, subnet_name, subnet_address_space, vnet_id = vm_creation.create_virtual_network(resource_group, location)
    
nsg_id = vm_creation.create_network_security_group(resource_group, location)
vm_creation.associate_nsg_with_subnet(resource_group, vnet_name, subnet_name, nsg_id)
# Create public IP
public_ip, public_ip_id = vm_creation.create_public_ip(resource_group, location, network_client)
print (f"{public_ip, public_ip_id}")
# Create NIC with the public IP
nic_id, nic_name = vm_creation.create_network_interface(resource_group, location, vnet_name, subnet_name, nsg_id, public_ip_id)
# nic_id = vm_creation.create_network_interface(resource_group, location, vnet_name, subnet_name, nsg_id)

# Specify Key Vault URL and secret name for storing private key
subnet_id = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Network/virtualNetworks/{vnet_name}/subnets/{subnet_name}"
kv_update.allow_vnet_in_key_vault(credential, subscription_id, resource_group, vault_name, subnet_id)

# kv_update.allow_vnet_in_key_vault(credential, subscription_id, resource_group, vault_name, vnet_id)
# secret_client = SecretClient(vault_url=f"https://{vault_name}.vault.azure.net", credential=credential)

key_vault_url = f"https://{vault_name}.vault.azure.net"
secret_name = f"{vm_name}-ssh-private-key"

# Create the VM
vm = vm_creation.create_virtual_machine(
    credential=credential,
    subscription_id=subscription_id,
    vm_size=selected_size,  
    resource_group = resource_group,
    vm_name=vm_name,
    nic_id=nic_id,
    admin_username=admin_username,
    user_assigned_identity_id=user_assigned_identity_id,
    location=location
    )
print(f'VM {vm_name} with size {selected_size["size"]} created successfully!')
print(f"Private key for VM '{vm_name}' is securely stored in Key Vault as ssh-private-key")
    
# Assign 'Network Contributor' role to the VM's user-assigned identity for the VNet
vm_creation.assign_network_contributor_role(user_assigned_identity_object_id, vnet_id)

# Generate unique storage account name
storage_account_name = st_creation.generate_storage_account_name()

# Create storage account
storage = st_creation.create_storage_account(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        storage_account_name=storage_account_name,
        location=location,
        vnet_name=vnet_name,  
        subnet_name=subnet_name,  
        vnet_resource_group=resource_group,
        ip_range=ip_range
    )

# Assign 'Storage Blob Contributor' role to the user-assigned identity into the Storage Account
st_creation.assign_storage_blob_data_contributor_role(
    credential=credential,
    subscription_id=subscription_id,
    resource_group_name=resource_group,
    storage_account_name=storage_account_name,
    user_assigned_identity_id=user_assigned_identity_object_id
)
storage_account_id = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Storage/storageAccounts/{storage_account_name}"

# Create Batch account
batch_account_name = f"batch{uuid.uuid4().hex[:8]}"
batch_account_id=f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Batch/batchAccounts/{batch_account_name}"
batch = batch_creation.create_batch_account_with_identity(
    credential=credential,
    subscription_id=subscription_id,
    resource_group_name=resource_group,
    storage_account_id=storage_account_id,
    user_assigned_identity_id=user_assigned_identity_id,
    batch_account_name=batch_account_name,
    location=location
)

# Assign 'Contributor' role to the user-assigned identity into the Storage Account
batch_creation.assign_contributor_role_to_identity(
    credential=credential,
    subscription_id=subscription_id,
    batch_account_id=batch_account_id,
    user_assigned_identity_object_id=user_assigned_identity_object_id  
)


public_ip_address = vm_creation.get_public_ip_address(resource_group,public_ip_id)
print (f"public ip address is '{public_ip_address}'")
secret_client = SecretClient(credential=credential, vault_url=key_vault_url)
private_key_pem = secret_client.get_secret(secret_name).value
private_key = paramiko.RSAKey.from_private_key(io.StringIO(private_key_pem))
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

commands = [
    f"""
    # Check and install Java 11
    if ! java -version 2>&1 | grep -q '11'; then
        echo "Java 11 not found. Installing Java 11..."
        sudo apt-get update && sudo apt-get install -y openjdk-11-jdk
    else
        echo "Java 11 is already installed."
    fi

    # Verify Java 11 installation
    if java -version 2>&1 | grep -q '11'; then
        echo "Java 11 is successfully installed!"
    else
        echo "Java 11 installation failed!"
    fi
    """,
    f"""
    # Check and install Docker
    if ! command -v docker >/dev/null; then
        echo "Docker not found. Installing Docker..."
        sudo apt-get update && sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io
    else
        echo "Docker is already installed."
    fi

    # Verify Docker installation
    if command -v docker >/dev/null; then
        echo "Docker is successfully installed!"
    else
        echo "Docker installation failed!"
    fi
    """,
    f"""
    # Install Nextflow
    echo "Installing Nextflow..."
    wget -qO- https://get.nextflow.io | bash
    # or using curl if wget is unavailable
    # curl -s https://get.nextflow.io | bash
    
    # Move Nextflow binary to a directory in PATH (optional, for easier access globally)
    sudo mv nextflow /usr/local/bin/
    
    # Make the Nextflow binary executable
    chmod +x /usr/local/bin/nextflow
    
    # Verify Nextflow installation
    if command -v nextflow >/dev/null; then
        echo "Nextflow is successfully installed!"
    else
        echo "Nextflow installation failed!"
    fi
    """,
    f"""
    # Check and install Git
    if ! command -v git >/dev/null; then
        echo "Git not found. Installing Git..."
        sudo apt-get update && sudo apt-get install -y git
    else
        echo "Git is already installed."
    fi
    
    # Verify Git installation
    if command -v git >/dev/null; then
        echo "Git is successfully installed!"
    else
        echo "Git installation failed!"
    fi
    """,
    f"""
    # Clone the GitHub repository
    echo "Cloning the Nextflow pipeline repository..."
    git clone https://github.com/biosustain/NextflowPipelineOrchestrator
    echo "Repository cloned successfully."
    """,
    f"""
    # Change directory and run the Nextflow pipeline
    # Change directory and replace parameters for running the Nextflow pipeline
    cd /home/azureuser/NextflowPipelineOrchestrator/NextflowTest && \
    
    # Update params.file
    if grep -i "params.file" nextflow.config; then
        sed -i '/az\\_test {{/,/}}/s/params.file = .*/params.file = \"az:\\/\\/orange\\/hello\\/hello.txt\"/' nextflow.config
        echo "Parameter params.file updated successfully."
    else
        echo "Error: Parameter params.file does not exist in the az_test profile."
        exit 1
    fi && \
    
    # Update params.outdir
    if grep -i "params.outdir" nextflow.config; then
        sed -i '/az\\_test {{/,/}}/s/params.outdir = .*/params.outdir = \"az:\\/\\/orange\\/results\"/' nextflow.config
        echo "Parameter params.outdir updated successfully."
    else
        echo "Error: Parameter params.outdir does not exist in the az_test profile."
        exit 1
    fi && \
    
    # Update clientId
    if  grep -i "clientId" "nextflow.config"; then
        sed -i "s|clientId.*|clientId='{user_assigned_identity_object_id}'|" nextflow.config
        echo "Parameter clientId in the Nextflow config file updated successfully."
    else
        echo "Error: Parameter clientId does not exist in the file."
        exit 1
    fi && \
    
    # Update virtualNetwork
    if grep -i "virtualNetwork" nextflow.config; then
        sed -i "s|virtualNetwork.*|virtualNetwork='{subnet_id}'|" nextflow.config
        echo "Parameter virtualNetwork in the Nextflow config file updated successfully."
    else
        echo "Error: Parameter virtualNetwork does not exist in the file."
        exit 1
    fi && \
    
    # Update userAssignedIdentities
    if grep -i "userAssignedIdentities" "nextflow.config"; then
        sed -i "s|userAssignedIdentities.*|userAssignedIdentities=['{user_assigned_identity_id}']|" nextflow.config
        echo "Parameter userAssignedIdentities in the Nextflow config file updated successfully."
    else
        echo "Error: Parameter userAssignedIdentities does not exist in the file."
        exit 1
    fi && \
    
    # Update storageAccountName
    if grep -i "storageAccountName" "credentials.json"; then
        sed -i "s|storageAccountName.*|storageAccountName:'{storage_account_name}'|" credentials.json
        echo "Parameter storageAccountName in the credentials file updated successfully."
    else
        echo "Error: Parameter storageAccountName does not exist in the file."
        exit 1
    fi && \
    
    # Update batchAccountName
    if grep -i "batchAccountName" "credentials.json"; then
        sed -i "s|batchAccountName.*|batchAccountName:'{batch_account_name}'|" credentials.json
        echo "Parameter batchAccountName in the credentials file updated successfully."
    else
        echo "Error: Parameter batchAccountName does not exist in the file."
        exit 1
    fi
    """
]

# Connect to the VM and execute the commands

# public_ip, public_ip_id = vm_creation.create_public_ip(resource_group, location)
try:
    print(f"Connecting to VM {public_ip_address}...")
    ssh.connect(hostname=public_ip_address, username=admin_username, pkey=private_key)
    print(f"Connected to {public_ip_address}!")

    for command in commands:
        print(f"Executing command: {command}")
        stdin, stdout, stderr = ssh.exec_command(command)
        stdout_data = stdout.read().decode()
        stderr_data = stderr.read().decode()

        print(f"Command output: {stdout_data}")
        if stderr_data:
            print(f"Command errors: {stderr_data}")
            # Optionally, add custom handling for specific errors here
finally:
    ssh.close()
    print("Connection closed.")
