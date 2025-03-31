import time
import os
import uuid
from dotenv import load_dotenv
from azure.mgmt.authorization import AuthorizationManagementClient
from azure.mgmt.authorization.models import RoleAssignmentCreateParameters, RoleAssignmentProperties
from azure.mgmt.msi import ManagedServiceIdentityClient
from azure.mgmt.msi.models import Identity
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import NetworkInterface, NetworkInterfaceIPConfiguration, Subnet, VirtualNetwork, NetworkSecurityGroup, SecurityRule, ServiceEndpointPropertiesFormat,PublicIPAddress 
from azure.mgmt.compute.models import HardwareProfile, StorageProfile, ImageReference, OSDisk, OSProfile, NetworkProfile, NetworkInterfaceReference, LinuxConfiguration, SshConfiguration, SshPublicKey
from azure.keyvault.secrets import SecretClient
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from azure.mgmt.compute.models import VirtualMachineIdentity
from azure.mgmt.resource import ResourceManagementClient
import ipaddress


load_dotenv()

subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
resource_group = os.getenv('RESOURCE_GROUP')
vault_name = os.getenv('VAULT_NAME')  

if not subscription_id or not resource_group or not vault_name:
    raise ValueError("AZURE_subscription_id, resource_group, and VAULT_NAME environment variables must be set.")

credential = DefaultAzureCredential()

compute_client = ComputeManagementClient(credential, subscription_id)
network_client = NetworkManagementClient(credential, subscription_id)
secret_client = SecretClient(vault_url=f"https://{vault_name}.vault.azure.net", credential=credential)
authorization_client = AuthorizationManagementClient(credential, subscription_id)

from azure.mgmt.compute.models import VirtualMachineIdentity

identity = VirtualMachineIdentity(
    type="UserAssigned",
    user_assigned_identities={
        "/subscriptions/{subscription-id}/resourceGroups/{resource-group}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/{identity-name}": {}
    }
)

# def assign_network_contributor_role(user_assigned_identity_object_id, vnet_id):
#     """Assign 'Network Contributor' role to the user-assigned managed identity on the VNet."""
#     role_definition_id = f"/subscriptions/{subscription_id}/providers/Microsoft.Authorization/roleDefinitions/4d97b98b-1d4f-4787-a291-c67834d212e7"  # Network Contributor role ID

#     # Role assignment ID must be a new GUID
#     role_assignment_id = str(uuid.uuid4())

#     assignment_params = RoleAssignmentCreateParameters(
#         properties=RoleAssignmentProperties(
#             role_definition_id=role_definition_id,
#             principal_id=user_assigned_identity_object_id,
#             principal_type="ServicePrincipal"
#         )
#     )

#     authorization_client.role_assignments.create(
#         scope=vnet_id,
#         role_assignment_name=role_assignment_id,
#         parameters=assignment_params
#     )
#     print(f"Assigned 'Network Contributor' role to identity on VNet '{vnet_id}'.")
def assign_network_contributor_role(user_assigned_identity_object_id, vnet_id):
    """Assign 'Network Contributor' role to the user-assigned managed identity on the VNet."""
    role_definition_id = f"/subscriptions/{subscription_id}/providers/Microsoft.Authorization/roleDefinitions/4d97b98b-1d4f-4787-a291-c67834d212e7"  # Network Contributor role ID

    role_assignment_id = str(uuid.uuid4())

    assignment_params = RoleAssignmentCreateParameters(
        role_definition_id=role_definition_id,
        principal_id=user_assigned_identity_object_id,
        principal_type="ServicePrincipal"
    )

    authorization_client.role_assignments.create(
        scope=vnet_id,
        role_assignment_name=role_assignment_id,
        parameters=assignment_params
    )
    print(f"Assigned 'Network Contributor' role to identity on VNet '{vnet_id}'.")


def create_ssh_key_pair():
    """Generate an SSH key pair and return the private and public keys."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    public_key = private_key.public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH
    ).decode('utf-8')
    return private_key_pem, public_key_pem

def store_private_key_in_key_vault(private_key, secret_name):
    """Store the private key in Azure Key Vault."""
    secret_client.set_secret(secret_name, private_key)
    print(f"Private key stored in Key Vault as '{secret_name}'")

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

# def create_public_ip(resource_group, location):
#     """Create a public IP for the VM."""
#     public_ip_name = f"pip-{uuid.uuid4().hex[:8]}"
#     public_ip_params = PublicIPAddress(
#         location=location,
#         public_ip_allocation_method='Dynamic'
#     )
#     public_ip = network_client.public_ip_addresses.begin_create_or_update(
#         resource_group, public_ip_name, public_ip_params
#     ).result()
#     print(f"Public IP '{public_ip_name}' created.")
#     print(f"Public IP '{public_ip}' created.")
#     return public_ip.ip_address, public_ip.id

def create_public_ip(resource_group, location, network_client):
    """Create a public IP for the VM."""
    public_ip_name = f"pip-{uuid.uuid4().hex[:8]}"
    
    public_ip_params = PublicIPAddress(
        location=location,
        public_ip_allocation_method='Dynamic'
    )

    public_ip_async_operation = network_client.public_ip_addresses.begin_create_or_update(
        resource_group, public_ip_name, public_ip_params
    )

    public_ip = public_ip_async_operation.result()

    if not public_ip.ip_address:
        retries = 5
        for _ in range(retries):
            time.sleep(5)  # Wait for 5 seconds before retrying
            public_ip = network_client.public_ip_addresses.get(resource_group, public_ip_name)
            if public_ip.ip_address:
                break

    if public_ip.ip_address:
        print(f"Public IP '{public_ip_name}' created with IP Address: {public_ip.ip_address}")
    else:
        print(f"Public IP '{public_ip_name}' was created, but no IP Address was assigned yet.")

    return public_ip.ip_address, public_ip.id

def create_virtual_network(resource_group, location):
    subnet_name = f"default"
    vnet_name = f"vnet-{uuid.uuid4().hex[:8]}"

    existing_vnet_spaces = get_existing_vnet_address_spaces()

    vnet_address_space = find_non_overlapping_address_space(existing_vnet_spaces)

    subnet_list = list(ipaddress.ip_network(vnet_address_space).subnets(new_prefix=27)) 
    subnet_address_space = str(subnet_list[0])

    subnet = Subnet(
        name=subnet_name,
        address_prefix=subnet_address_space,
        service_endpoints=[
            ServiceEndpointPropertiesFormat(service="Microsoft.Storage"),
            ServiceEndpointPropertiesFormat(service="Microsoft.KeyVault")
        ]
    )

    vnet_params = VirtualNetwork(
        location=location,
        address_space={'address_prefixes': [vnet_address_space]},
        subnets=[subnet]
    )

    vnet = network_client.virtual_networks.begin_create_or_update(
        resource_group,
        vnet_name,
        vnet_params
    ).result()

    return vnet_name, subnet_name, subnet_address_space, vnet.id 

# def create_network_interface(resource_group, location, vnet_name, subnet_name, nsg_id):
#     """Create a network interface and associate it with an NSG."""
#     subnet_info = network_client.subnets.get(resource_group, vnet_name, subnet_name)  # Get the existing subnet info
#     nic_params = NetworkInterface(
#         location=location,
#         ip_configurations=[NetworkInterfaceIPConfiguration(
#             name='ipconfig1',
#             subnet={'id': subnet_info.id},
#             private_ip_allocation_method='Dynamic'
#         )],
#         network_security_group={'id': nsg_id}  # Associate NIC with the NSG
#     )
#     nic_name = f"nic-{uuid.uuid4().hex[:8]}"
#     nic = network_client.network_interfaces.begin_create_or_update(resource_group, nic_name, nic_params).result()
#     print(f"NIC '{nic_name}' created and associated with NSG '{nsg_id}'.")
#     return nic.id

def create_network_interface(resource_group, location, vnet_name, subnet_name, nsg_id, public_ip_id):
    """Create a network interface with a public IP."""
    subnet_info = network_client.subnets.get(resource_group, vnet_name, subnet_name)
    nic_params = NetworkInterface(
        location=location,
        ip_configurations=[NetworkInterfaceIPConfiguration(
            name='ipconfig1',
            subnet={'id': subnet_info.id},
            private_ip_allocation_method='Dynamic',
            public_ip_address={'id': public_ip_id}  
        )],
        network_security_group={'id': nsg_id}
    )
    nic_name = f"nic-{uuid.uuid4().hex[:8]}"
    nic = network_client.network_interfaces.begin_create_or_update(resource_group, nic_name, nic_params).result()
    print(f"NIC '{nic_name}' created and associated with NSG '{nsg_id}'.")
    return nic.id, nic_name

def get_public_ip_address(resource_group, public_ip_id):
    """Retrieve the public IP address from its resource ID."""
    public_ip_name = public_ip_id.split("/")[-1]
    
    public_ip = network_client.public_ip_addresses.get(resource_group, public_ip_name)
    return public_ip.ip_address

from azure.mgmt.network.models import NetworkSecurityGroup, SecurityRule

def create_network_security_group(resource_group, location):
    nsg_name = f"nsg-{uuid.uuid4().hex[:8]}"
    nsg_params = NetworkSecurityGroup(location=location)
    nsg = network_client.network_security_groups.begin_create_or_update(
        resource_group, nsg_name, nsg_params).result()

    inbound_rules = [
        SecurityRule(
            name="Allow-BatchNodeManagement-Inbound",
            priority=200,
            direction="Inbound",
            access="Allow",
            protocol="*",
            source_port_range="*",
            destination_port_range="*",
            source_address_prefix="BatchNodeManagement.WestEurope",
            destination_address_prefix="*",
        ),
        SecurityRule(
            name="Allow-SSH-Inbound",
            priority=170,
            direction="Inbound",
            access="Allow",
            protocol="Tcp",
            source_port_range="*",
            destination_port_range="22",
            source_address_prefix="*",
            destination_address_prefix="*",
        ),
    ]

    outbound_rules = [
        SecurityRule(
            name="Allow-BatchNodeManagement-Outbound",
            priority=170,
            direction="Outbound",
            access="Allow",
            protocol="*",
            source_port_range="*",
            destination_port_range="*",
            source_address_prefix="*",
            destination_address_prefix="BatchNodeManagement.WestEurope",
        ),
        SecurityRule(
            name="Allow-Storage-Outbound",
            priority=200,
            direction="Outbound",
            access="Allow",
            protocol="*",
            source_port_range="*",
            destination_port_range="*",
            source_address_prefix="*",
            destination_address_prefix="Storage",
        ),
    ]

    for rule in inbound_rules + outbound_rules:
        network_client.security_rules.begin_create_or_update(
            resource_group, nsg_name, rule.name, rule
        ).result()

    print(f"Network Security Group '{nsg_name}' with custom rules created.")
    return nsg.id

def associate_nsg_with_subnet(resource_group, vnet_name, subnet_name, nsg_id):
    subnet_info = network_client.subnets.get(resource_group, vnet_name, subnet_name)
    subnet_info.network_security_group = {'id': nsg_id}
    network_client.subnets.begin_create_or_update(
        resource_group, vnet_name, subnet_name, subnet_info
    ).result()
    print(f"NSG associated with subnet '{subnet_name}' in VNet '{vnet_name}'.")


def create_virtual_machine(credential, subscription_id, vm_size, resource_group, vm_name, nic_id, admin_username, user_assigned_identity_id, location='westeurope'):
    private_key_pem, public_key_pem = create_ssh_key_pair()
    secret_name = f"{vm_name}-ssh-private-key"
    store_private_key_in_key_vault(private_key_pem, secret_name)

    vm_identity = VirtualMachineIdentity(
        type="UserAssigned",
        user_assigned_identities={
            user_assigned_identity_id: {}  
        }
    )

    vm_parameters = {
        'location': location,
        'identity': vm_identity,
        'hardware_profile': HardwareProfile(vm_size=vm_size['size']),
        'storage_profile': StorageProfile(
            image_reference=ImageReference(
                publisher='Canonical',
                offer='0001-com-ubuntu-server-focal',
                sku='20_04-lts-gen2',
                version='latest'
            ),
            os_disk=OSDisk(
                create_option='FromImage',
                name=f'{vm_name}_osdisk',
                disk_size_gb=vm_size['os_disk_size_gb']
            )
        ),
        'os_profile': OSProfile(
            computer_name=f"vm-{uuid.uuid4().hex[:8]}",
            admin_username=admin_username,
            linux_configuration=LinuxConfiguration(
                disable_password_authentication=True,
                ssh=SshConfiguration(
                    public_keys=[SshPublicKey(
                        path=f'/home/{admin_username}/.ssh/authorized_keys',
                        key_data=public_key_pem
                    )]
                )
            )
        ),
        'network_profile': NetworkProfile(
            network_interfaces=[NetworkInterfaceReference(
                id=nic_id,
                primary=True
            )]
        )
    }

    vm_creation = compute_client.virtual_machines.begin_create_or_update(
        resource_group,
        vm_name,
        vm_parameters
    ).result()

    return vm_creation


def delete_vm_and_related_resources(credential, subscription_id, resource_group, vm_name):
    # Authenticate using DefaultAzureCredential
    # credential = DefaultAzureCredential()

    # Create clients for compute, network, and resource management
    compute_client = ComputeManagementClient(credential, subscription_id)
    network_client = NetworkManagementClient(credential, subscription_id)
    resource_client = ResourceManagementClient(credential, subscription_id)

    # Step 1: Get the VM details
    print(f"Fetching details for VM: {vm_name}")
    vm = compute_client.virtual_machines.get(resource_group, vm_name)

    # Extract resource IDs of related components
    nic_id = vm.network_profile.network_interfaces[0].id
    os_disk_id = vm.storage_profile.os_disk.managed_disk.id
    public_ip_id = None
    vnet_id = None
    nsg_id = None

    # Get NIC details to retrieve public IP and VNet
    nic_name = nic_id.split("/")[-1]
    nic = network_client.network_interfaces.get(resource_group, nic_name)
    if nic.ip_configurations:
        ip_config = nic.ip_configurations[0]
        if ip_config.public_ip_address:
            public_ip_id = ip_config.public_ip_address.id
        if ip_config.subnet:
            vnet_id = ip_config.subnet.id.rsplit("/subnets", 1)[0]
        if nic.network_security_group:
            nsg_id = nic.network_security_group.id

    # Delete the VM
    print(f"Deleting VM: {vm_name}")
    async_vm_delete = compute_client.virtual_machines.begin_delete(resource_group, vm_name)
    async_vm_delete.wait()

    # Delete the NIC
    print(f"Deleting NIC: {nic_name}")
    async_nic_delete = network_client.network_interfaces.begin_delete(resource_group, nic_name)
    async_nic_delete.wait()

    # Delete the OS disk
    os_disk_name = os_disk_id.split("/")[-1]
    print(f"Deleting OS Disk: {os_disk_name}")
    async_disk_delete = compute_client.disks.begin_delete(resource_group, os_disk_name)
    async_disk_delete.wait()

    # Delete the Public IP
    if public_ip_id:
        public_ip_name = public_ip_id.split("/")[-1]
        print(f"Deleting Public IP: {public_ip_name}")
        async_public_ip_delete = network_client.public_ip_addresses.begin_delete(resource_group, public_ip_name)
        async_public_ip_delete.wait()

    # Delete the Virtual Network
    if vnet_id:
        vnet_name = vnet_id.split("/")[-1]
        print(f"Deleting Virtual Network: {vnet_name}")
        async_vnet_delete = network_client.virtual_networks.begin_delete(resource_group, vnet_name)
        async_vnet_delete.wait()
    
    # Delete the Network Security Group (NSG)
    if nsg_id:
        nsg_name = nsg_id.split("/")[-1]
        print(f"Deleting Network Security Group: {nsg_name}")
        async_nsg_delete = network_client.network_security_groups.begin_delete(resource_group, nsg_name)
        async_nsg_delete.wait()

    print("Successfully deleted VM and related resources.")
