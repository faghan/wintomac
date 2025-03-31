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
user_assigned_identity_object_id = os.getenv('USER_ASSIGNED_IDENTITY_OBJECT_ID')
ip_range = os.getenv('IP_RANGE')
location = 'westeurope'
admin_username = 'azureuser'

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
public_ip, public_ip_id = vm_creation.create_public_ip(resource_group, location, network_client)
print (f"{public_ip, public_ip_id}")
nic_id, nic_name = vm_creation.create_network_interface(resource_group, location, vnet_name, subnet_name, nsg_id, public_ip_id)

subnet_id = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Network/virtualNetworks/{vnet_name}/subnets/{subnet_name}"
kv_update.allow_vnet_in_key_vault(credential, subscription_id, resource_group, vault_name, subnet_id)


key_vault_url = f"https://{vault_name}.vault.azure.net"
secret_name = f"{vm_name}-ssh-private-key"


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
    
vm_creation.assign_network_contributor_role(user_assigned_identity_object_id, vnet_id)

storage_account_name = st_creation.generate_storage_account_name()

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

batch_creation.assign_contributor_role_to_identity(
    credential=credential,
    subscription_id=subscription_id,
    batch_account_id=batch_account_id,
    user_assigned_identity_object_id=user_assigned_identity_object_id  
)


