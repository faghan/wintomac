import os
import uuid
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import NetworkInterface, NetworkInterfaceIPConfiguration, Subnet, VirtualNetwork
from azure.mgmt.compute.models import HardwareProfile, StorageProfile, ImageReference, OSDisk, OSProfile, NetworkProfile, NetworkInterfaceReference
import ipaddress
import getpass  # For secure password input

# Load environment variables from .env file
load_dotenv()

# Load environment variables
subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
resource_group = os.getenv('RESOURCE_GROUP')

if not subscription_id or not resource_group:
    raise ValueError("AZURE_SUBSCRIPTION_ID and RESOURCE_GROUP environment variables must be set.")

# Authentication
credential = DefaultAzureCredential()

# Clients
compute_client = ComputeManagementClient(credential, subscription_id)
network_client = NetworkManagementClient(credential, subscription_id)

# Define VM sizes and configurations
vm_sizes = {
    '1': {'size': 'Standard_B1s', 'os_disk_size_gb': 30},
    '2': {'size': 'Standard_B2s', 'os_disk_size_gb': 30},
    '3': {'size': 'Standard_D2s_v3', 'os_disk_size_gb': 30},
    '4': {'size': 'Standard_D4s_v3', 'os_disk_size_gb': 30},
    '5': {'size': 'Standard_DS1_v2', 'os_disk_size_gb': 30},
}

def get_existing_vnet_address_spaces():
    """Retrieve all existing VNet address spaces in the subscription."""
    existing_vnet_spaces = []
    for vnet in network_client.virtual_networks.list_all():
        for prefix in vnet.address_space.address_prefixes:
            existing_vnet_spaces.append(ipaddress.ip_network(prefix))
    return existing_vnet_spaces

def find_non_overlapping_address_space(existing_spaces, vnet_size=16):
    """Find a non-overlapping address space for the new VNet."""
    for network in ipaddress.ip_network('10.0.0.0/8').subnets(new_prefix=vnet_size):
        if all(not network.overlaps(existing) for existing in existing_spaces):
            return str(network)
    raise ValueError("No non-overlapping address space available.")

def create_virtual_network(resource_group, location, vnet_name, subnet_name):
    # Get existing VNet address spaces
    existing_vnet_spaces = get_existing_vnet_address_spaces()

    # Find a non-overlapping address space
    vnet_address_space = find_non_overlapping_address_space(existing_vnet_spaces)

    # Convert the generator to a list to access the first /24 subnet
    subnet_list = list(ipaddress.ip_network(vnet_address_space).subnets(new_prefix=24)) 
    subnet_address_space = str(subnet_list[0])

    vnet_params = VirtualNetwork(
        location=location,
        address_space={'address_prefixes': [vnet_address_space]},
        subnets=[Subnet(name=subnet_name, address_prefix=subnet_address_space)]
    )
    vnet = network_client.virtual_networks.begin_create_or_update(resource_group, vnet_name, vnet_params).result()
    return vnet

def create_network_interface(resource_group, location, nic_name, vnet_name, subnet_name):
    subnet_info = network_client.subnets.get(resource_group, vnet_name, subnet_name)
    nic_params = NetworkInterface(
        location=location,
        ip_configurations=[NetworkInterfaceIPConfiguration(
            name='ipconfig1',
            subnet={'id': subnet_info.id},
            private_ip_allocation_method='Dynamic'
        )]
    )
    nic = network_client.network_interfaces.begin_create_or_update(resource_group, nic_name, nic_params).result()
    return nic.id

def create_vm(vm_size, resource_group, vm_name, nic_id, admin_username, admin_password, location='westeurope'):
    vm_parameters = {
        'location': location,
        'hardware_profile': HardwareProfile(vm_size=vm_size['size']),
        'storage_profile': StorageProfile(
            image_reference=ImageReference(
                publisher='Canonical',
                offer='UbuntuServer',
                sku='18.04-LTS',
                version='latest'
            ),
            os_disk=OSDisk(
                create_option='FromImage',
                name=f'{vm_name}_osdisk',
                disk_size_gb=vm_size['os_disk_size_gb']
            )
        ),
        'os_profile': OSProfile(
            computer_name=vm_name,
            admin_username=admin_username,
            admin_password=admin_password
        ),
        'network_profile': NetworkProfile(
            network_interfaces=[NetworkInterfaceReference(
                id=nic_id,
                primary=True
            )]
        )
    }

    creation_result = compute_client.virtual_machines.begin_create_or_update(
        resource_group_name=resource_group,
        vm_name=vm_name,
        parameters=vm_parameters
    ).result()

    return creation_result

# User selects VM size
print('Select a VM size:')
for key, value in vm_sizes.items():
    print(f'{key}: {value["size"]}')

selected_size_key = input('Enter the number corresponding to the VM size: ')

if selected_size_key not in vm_sizes:
    print('Invalid selection')
else:
    # Prompt the user for admin username and password
    admin_username = input('Enter the admin username: ')
    admin_password = getpass.getpass('Enter the admin password: ')  # Secure password input

    selected_size = vm_sizes[selected_size_key]
    vm_name = f"vm-{uuid.uuid4().hex[:8]}"
    location = 'westeurope'
    vnet_name = f"vnet-{uuid.uuid4().hex[:8]}"
    subnet_name = f"subnet-{uuid.uuid4().hex[:8]}"
    nic_name = f"nic-{uuid.uuid4().hex[:8]}"

    # Create Virtual Network and Subnet
    create_virtual_network(resource_group, location, vnet_name, subnet_name)

    # Create Network Interface
    nic_id = create_network_interface(resource_group, location, nic_name, vnet_name, subnet_name)

    # Create VM
    create_vm(selected_size, resource_group, vm_name, nic_id, admin_username, admin_password)
    print(f'VM {vm_name} with size {selected_size["size"]} created successfully!')
