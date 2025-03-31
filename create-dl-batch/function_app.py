import os
import uuid
import logging
import json
import paramiko
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.batch import BatchManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.keyvault.secrets import SecretClient
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import base64
from azure.mgmt.batch.models import BatchAccountCreateParameters, BatchAccountIdentity, NetworkProfile, PublicNetworkAccessType
from azure.mgmt.storage.models import StorageAccountCreateParameters, Sku, Kind, NetworkRuleSet, VirtualNetworkRule, IPRule, RoutingPreference
from azure.mgmt.network.models import PrivateEndpoint, Subnet, PrivateEndpointConnection
from azure.mgmt.network.models import PrivateLinkServiceConnection
from azure.mgmt.compute.models import VirtualMachine, HardwareProfile, NetworkInterfaceReference, OSProfile, LinuxConfiguration, SshConfiguration, SshPublicKey

app = func.FunctionApp()

def create_storage_account(credential, subscription_id, resource_group_name, vnet_name, subnet_name, ip_range, location):
    storage_client = StorageManagementClient(credential, subscription_id)
    
    # Create a unique name for the new storage account
    new_storage_account_name = f"storage{uuid.uuid4().hex[:8]}"
    logging.info(f"The storage account name is {new_storage_account_name}")

    # Define the network rule set for the new storage account
    network_rule_set = NetworkRuleSet(
        bypass='Logging, Metrics, AzureServices',
        default_action='Deny',
        virtual_network_rules=[
            VirtualNetworkRule(
                virtual_network_resource_id=f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Network/virtualNetworks/{vnet_name}/subnets/{subnet_name}",
                action='Allow'
            )
        ],
        ip_rules=[
            IPRule(
                ip_address_or_range=ip_range,
                action='Allow'
            )
        ]
    )

    # Define the routing preference for the storage account
    routing_preference = RoutingPreference(
        routing_choice='MicrosoftRouting',  # Choose between 'MicrosoftRouting' and 'InternetRouting'
        publish_microsoft_endpoints=True,
        publish_internet_endpoints=True
    )

    # Define the parameters for the new storage account, including the minimum TLS version
    storage_account_params = StorageAccountCreateParameters(
        sku=Sku(name='Standard_LRS'),
        kind=Kind.STORAGE_V2,
        location=location,
        is_hns_enabled=True,
        network_rule_set=network_rule_set,
        routing_preference=routing_preference,
        minimum_tls_version='TLS1_2'  # Set the minimum TLS version to 1.2
    )

    # Create the new storage account
    async_storage_creation = storage_client.storage_accounts.begin_create(
        resource_group_name,
        new_storage_account_name,
        storage_account_params
    )

    # Wait for the creation to complete
    async_storage_creation.result()

    logging.info(f"Created new storage account: {new_storage_account_name}")
    
    # Retrieve the storage account keys
    keys = storage_client.storage_accounts.list_keys(resource_group_name, new_storage_account_name)
    storage_account_key = keys.keys[0].value

    logging.info(f"Storage account key retrieved: {storage_account_key}")

    return new_storage_account_name, storage_account_key


def create_batch_account(credential, subscription_id, resource_group_name, batch_account_name, storage_account_name, location):
    batch_client = BatchManagementClient(credential, subscription_id)
    
    # Define the parameters for the new batch account
    batch_account_params = BatchAccountCreateParameters(
        location=location,
        identity=BatchAccountIdentity(
            type='SystemAssigned'
        ),
        auto_storage={
            'storage_account_id': f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Storage/storageAccounts/{storage_account_name}"
        },
        public_network_access=PublicNetworkAccessType.DISABLED,
        network_profile=NetworkProfile(
            public_network_access=PublicNetworkAccessType.DISABLED
        )
    )

    # Create the new batch account
    async_batch_creation = batch_client.batch_account.begin_create(
        resource_group_name,
        batch_account_name,
        batch_account_params
    )

    # Wait for the creation to complete
    async_batch_creation.result()

    logging.info(f"Created new batch account: {batch_account_name}")
    # Retrieve the batch account keys
    keys = batch_client.batch_account.get_keys(resource_group_name, batch_account_name)
    batch_account_key = keys.primary

    logging.info(f"Batch account key retrieved: {batch_account_key}")

    return batch_account_name, batch_account_key


def create_private_endpoint(credential, subscription_id, resource_group_name, batch_account_name, vnet_name, subnet_name, location):
    network_client = NetworkManagementClient(credential, subscription_id)
    
    # Generate a unique name for the private endpoint
    private_endpoint_name = f"pe-{uuid.uuid4().hex[:8]}"
    
    # Define the subnet
    subnet = Subnet(id=f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Network/virtualNetworks/{vnet_name}/subnets/{subnet_name}")
    
    # Define the private link service connection
    private_link_service_connection = PrivateLinkServiceConnection(
        name=f"plsconn-{uuid.uuid4().hex[:8]}",
        private_link_service_id=f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Batch/batchAccounts/{batch_account_name}",
        group_ids=["batchAccount"]
    )

    # Define the private endpoint parameters
    private_endpoint_parameters = PrivateEndpoint(
        location=location,
        subnet=subnet,
        private_link_service_connections=[private_link_service_connection]
    )

    # Create the private endpoint
    async_pe_creation = network_client.private_endpoints.begin_create_or_update(
        resource_group_name,
        private_endpoint_name,
        private_endpoint_parameters
    )

    # Wait for the creation to complete
    async_pe_creation.result()

    logging.info(f"Created private endpoint: {private_endpoint_name}")

def create_ssh_key_pair():
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

def store_private_key_in_key_vault(vault_url, private_key, secret_name):
    credential = DefaultAzureCredential()
    secret_client = SecretClient(vault_url=vault_url, credential=credential)
    secret_client.set_secret(secret_name, private_key)

def create_virtual_machine(credential, subscription_id, resource_group_name, vnet_name, subnet_name, nsg_name, location, vault_url, secret_name):
    compute_client = ComputeManagementClient(credential, subscription_id)
    network_client = NetworkManagementClient(credential, subscription_id)

    private_key_pem, public_key_pem = create_ssh_key_pair()
    store_private_key_in_key_vault(vault_url, private_key_pem, secret_name)

    # Network Interface
    nic = network_client.network_interfaces.begin_create_or_update(
        resource_group_name,
        "myNic",
        {
            "location": location,
            "ip_configurations": [{
                "name": "myIpConfig",
                "subnet": {
                    "id": f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Network/virtualNetworks/{vnet_name}/subnets/{subnet_name}"
                },
                "public_ip_address": None,
                "network_security_group": {
                    "id": f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Network/networkSecurityGroups/{nsg_name}"
                }
            }]
        }
    ).result()

    # VM Creation
    vm_parameters = {
        "location": location,
        "storage_profile": {
            "image_reference": {
                "publisher": "Canonical",
                "offer": "0001-com-ubuntu-server-focal",
                "sku": "20_04-lts-gen2",
                "version": "latest"
            }
        },
        "hardware_profile": {
            "vm_size": "Standard_D2s_v3"
        },
        "os_profile": {
            "computer_name": "myVM",
            "admin_username": "azureuser",
            "linux_configuration": {
                "disable_password_authentication": True,
                "ssh": {
                    "public_keys": [{
                        "path": "/home/azureuser/.ssh/authorized_keys",
                        "key_data": public_key_pem
                    }]
                }
            }
        },
        "network_profile": {
            "network_interfaces": [{
                "id": nic.id
            }]
        }
    }

    vm_creation = compute_client.virtual_machines.begin_create_or_update(
        resource_group_name,
        "myVM",
        vm_parameters
    ).result()

    return vm_creation.name

def get_private_key_from_key_vault(vault_url, secret_name):
    credential = DefaultAzureCredential()
    secret_client = SecretClient(vault_url=vault_url, credential=credential)
    secret = secret_client.get_secret(secret_name)
    return secret.value

def ssh_into_vm(vm_ip, username, private_key):
    # Load the private key
    private_key_obj = paramiko.RSAKey.from_private_key(private_key)

    # Create an SSH client
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        # Connect to the VM
        ssh_client.connect(hostname=vm_ip, username=username, pkey=private_key_obj)
        print(f"Successfully connected to {vm_ip}")
        
        # Example: Execute a command on the VM
        stdin, stdout, stderr = ssh_client.exec_command('ls -la')
        print("Command output:", stdout.read().decode())
    finally:
        ssh_client.close()

def create_public_ip(credential, subscription_id, resource_group_name, location):
    network_client = NetworkManagementClient(credential, subscription_id)
    
    public_ip_name = f"publicIP-{uuid.uuid4().hex[:8]}"
    public_ip_parameters = {
        'location': location,
        'public_ip_allocation_method': 'Dynamic',
        'dns_settings': {
            'domain_name_label': public_ip_name
        }
    }

    async_public_ip_creation = network_client.public_ip_addresses.begin_create_or_update(
        resource_group_name,
        public_ip_name,
        public_ip_parameters
    )

    public_ip = async_public_ip_creation.result()
    return public_ip


@app.event_grid_trigger(arg_name="azeventgrid")
def PipelineOrchestrator_v1(azeventgrid: func.EventGridEvent):
    logging.info('Python EventGrid trigger processed an event')

    # Initialize the Azure SDK clients
    credential = DefaultAzureCredential()
    subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
    resource_group_name = os.getenv('RESOURCE_GROUP')
    vnet_name = os.getenv('VNET')
    subnet_st = os.getenv('SUBNET_ST')
    subnet_batch = os.getenv('SUBNET_BATCH')
    subnet_vm = os.getenv('SUBNET_VM')
    ip_range = os.getenv('IP_RANGE')
    location =  'westeurope' # or your desired Azure region  'switzerlandnorth' 
    vault_url = os.getenv('VAULT_URL')
    secret_name = f"ssh-key-{uuid.uuid4().hex}"
    nsg_name = os.getenv('NSG_NAME')
    # # Create the storage account
    # storage_account_name, storage_account_key = create_storage_account(credential, subscription_id, resource_group_name, vnet_name, subnet_st, ip_range, location)
    
    # # Define the batch account name
    # batch_account_name = f"batch{uuid.uuid4().hex[:8]}"
    
    # # Create the batch account
    # batch_account_name, batch_account_key = create_batch_account(credential, subscription_id, resource_group_name, batch_account_name, storage_account_name, location)

    # Create the private endpoint for the batch account
    # create_private_endpoint(credential, subscription_id, resource_group_name, batch_account_name, vnet_name, subnet_batch, location)
    
    # Create the virtual machine
    credential = DefaultAzureCredential()
    vm_name = create_virtual_machine(credential, subscription_id, resource_group_name, vnet_name, subnet_vm, nsg_name, location, vault_url, secret_name)
    print(f"VM created with name: {vm_name}")
    # # Save the credentials to a JSON file
    # credentials = {
    #     "storageAccountName": storage_account_name,
    #     "storageAccountKey": storage_account_key,
    #     "batchAccountName": batch_account_name,
    #     "batchAccountKey": batch_account_key
    # }

    # with open('credentials.json', 'w') as f:
    #     json.dump(credentials, f)

    # logging.info(f"Credentials saved to credentials.json")






# import os
# import uuid
# import logging
# import azure.functions as func
# from azure.identity import DefaultAzureCredential
# from azure.mgmt.storage import StorageManagementClient
# from azure.mgmt.batch import BatchManagementClient
# from azure.mgmt.batch.models import BatchAccountCreateParameters, BatchAccountIdentity, NetworkProfile, PublicNetworkAccessType
# from azure.mgmt.storage.models import StorageAccountCreateParameters, Sku, Kind, NetworkRuleSet, VirtualNetworkRule, IPRule, RoutingPreference

# app = func.FunctionApp()

# def create_storage_account(credential, subscription_id, resource_group_name, vnet_name, subnet_name, ip_range, location):
#     storage_client = StorageManagementClient(credential, subscription_id)
    
#     # Create a unique name for the new storage account
#     new_storage_account_name = f"storage{uuid.uuid4().hex[:16]}"
#     logging.info(f"The storage account name is {new_storage_account_name}")

#     # Define the network rule set for the new storage account
#     network_rule_set = NetworkRuleSet(
#         bypass='Logging, Metrics, AzureServices',
#         default_action='Deny',
#         virtual_network_rules=[
#             VirtualNetworkRule(
#                 virtual_network_resource_id=f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Network/virtualNetworks/{vnet_name}/subnets/{subnet_name}",
#                 action='Allow'
#             )
#         ],
#         ip_rules=[
#             IPRule(
#                 ip_address_or_range=ip_range,
#                 action='Allow'
#             )
#         ]
#     )

#     # Define the routing preference for the storage account
#     routing_preference = RoutingPreference(
#         routing_choice='MicrosoftRouting',  # Choose between 'MicrosoftRouting' and 'InternetRouting'
#         publish_microsoft_endpoints=True,
#         publish_internet_endpoints=True
#     )

#     # Define the parameters for the new storage account
#     storage_account_params = StorageAccountCreateParameters(
#         sku=Sku(name='Standard_LRS'),
#         kind=Kind.STORAGE_V2,
#         location=location,
#         is_hns_enabled=True,
#         network_rule_set=network_rule_set,
#         routing_preference=routing_preference
#     )

#     # Create the new storage account
#     async_storage_creation = storage_client.storage_accounts.begin_create(
#         resource_group_name,
#         new_storage_account_name,
#         storage_account_params
#     )

#     # Wait for the creation to complete
#     async_storage_creation.result()

#     logging.info(f"Created new storage account: {new_storage_account_name}")
#     return new_storage_account_name

# def create_batch_account(credential, subscription_id, resource_group_name, batch_account_name, storage_account_name, vnet_name, subnet_name, ip_range, location='westeurope'):
#     batch_client = BatchManagementClient(credential, subscription_id)
    
#     # Define the parameters for the new batch account
#     batch_account_params = BatchAccountCreateParameters(
#         location=location,
#         identity=BatchAccountIdentity(
#             type='SystemAssigned'
#         ),
#         auto_storage={
#             'storage_account_id': f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Storage/storageAccounts/{storage_account_name}"
#         },
#         public_network_access=PublicNetworkAccessType.DISABLED,
#         network_profile=NetworkProfile(
#             network_interfacing_policies=PrivateLinkServiceNetworkPolicies.DISABLED,
#             public_network_access=PublicNetworkAccessType.DISABLED,
#             public_network_rules=[
#                 IPRule(
#                     value=ip_range
#                 )
#             ]
#         )
#     )

#     # Create the new batch account
#     async_batch_creation = batch_client.batch_account.begin_create(
#         resource_group_name,
#         batch_account_name,
#         batch_account_params
#     )

#     # Wait for the creation to complete
#     async_batch_creation.result()

#     logging.info(f"Created new batch account: {batch_account_name}")

# @app.event_grid_trigger(arg_name="azeventgrid")
# def PipelineOrchestrator_v1(azeventgrid: func.EventGridEvent):
#     logging.info('Python EventGrid trigger processed an event')

#     # Initialize the Azure SDK clients
#     credential = DefaultAzureCredential()
#     subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
#     resource_group_name = os.getenv('RESOURCE_GROUP')
#     vnet_name = os.getenv('VNET')
#     subnet_name = os.getenv('SUBNET')
#     ip_range = os.getenv('IP_RANGE')
#     location = 'westeurope'  # or your desired Azure region

#     # Create the storage account
#     storage_account_name = create_storage_account(credential, subscription_id, resource_group_name, vnet_name, subnet_name, ip_range, location)
    
#     # Define the batch account name
#     batch_account_name = f"batch{uuid.uuid4().hex[:16]}"
    
#     # Create the batch account
#     create_batch_account(credential, subscription_id, resource_group_name, batch_account_name, storage_account_name, ip_range, location)

# # import os
# # import uuid
# # import logging
# # import azure.functions as func
# # from azure.identity import DefaultAzureCredential
# # from azure.mgmt.storage import StorageManagementClient
# # from azure.mgmt.storage.models import StorageAccountCreateParameters, Sku, Kind, NetworkRuleSet, VirtualNetworkRule, IPRule, RoutingPreference

# # app = func.FunctionApp()

# # def create_storage_account(credential, subscription_id, resource_group_name, vnet_name, subnet_name, ip_range, location):
# #     storage_client = StorageManagementClient(credential, subscription_id)
    
# #     # Create a unique name for the new storage account
# #     new_storage_account_name = f"dataanalyticsdev{uuid.uuid4().hex[:6]}"
# #     logging.info(f"The storage account name is {new_storage_account_name}")

# #     # Define the network rule set for the new storage account
# #     network_rule_set = NetworkRuleSet(
# #         bypass='Logging, Metrics, AzureServices',
# #         default_action='Deny',
# #         virtual_network_rules=[
# #             VirtualNetworkRule(
# #                 virtual_network_resource_id=f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Network/virtualNetworks/{vnet_name}/subnets/{subnet_name}",
# #                 action='Allow'
# #             )
# #         ],
# #         ip_rules=[
# #             IPRule(
# #                 ip_address_or_range=ip_range,
# #                 action='Allow'
# #             )
# #         ]
# #     )

# #     # Define the routing preference for the storage account
# #     routing_preference = RoutingPreference(
# #         routing_choice='MicrosoftRouting',  # Choose between 'MicrosoftRouting' and 'InternetRouting'
# #         publish_microsoft_endpoints=True,
# #         publish_internet_endpoints=True
# #     )

# #     # Define the parameters for the new storage account
# #     storage_account_params = StorageAccountCreateParameters(
# #         sku=Sku(name='Standard_LRS'),
# #         kind=Kind.STORAGE_V2,
# #         location=location,
# #         is_hns_enabled=True,
# #         network_rule_set=network_rule_set,
# #         routing_preference=routing_preference
# #     )

# #     # Create the new storage account
# #     async_storage_creation = storage_client.storage_accounts.begin_create(
# #         resource_group_name,
# #         new_storage_account_name,
# #         storage_account_params
# #     )

# #     # Wait for the creation to complete
# #     async_storage_creation.result()

# #     logging.info(f"Created new storage account: {new_storage_account_name}")
# #     return new_storage_account_name

# # @app.event_grid_trigger(arg_name="azeventgrid")
# # def PipelineOrchestrator_v1(azeventgrid: func.EventGridEvent):
# #     logging.info('Python EventGrid trigger processed an event')

# #     # Initialize the Azure SDK clients
# #     credential = DefaultAzureCredential()
# #     subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
# #     resource_group_name = os.getenv('RESOURCE_GROUP')
# #     vnet_name = os.getenv('VNET')
# #     subnet_name = os.getenv('SUBNET')
# #     ip_range = os.getenv('IP_RANGE')
# #     location = 'westeurope'  # or your desired Azure region

# #     # Create the storage account
# #     create_storage_account(credential, subscription_id, resource_group_name, vnet_name, subnet_name, ip_range, location)

# # # import os
# # # import uuid
# # # import logging
# # # import azure.functions as func
# # # from azure.identity import DefaultAzureCredential
# # # from azure.mgmt.resource import ResourceManagementClient
# # # from azure.mgmt.storage import StorageManagementClient
# # # from azure.mgmt.network import NetworkManagementClient
# # # from azure.mgmt.storage.models import StorageAccountCreateParameters, Sku, Kind, NetworkRuleSet, VirtualNetworkRule, IPRule, RoutingPreference

# # # app = func.FunctionApp()

# # # @app.event_grid_trigger(arg_name="azeventgrid")
# # # def PipelineOrchestrator_v1(azeventgrid: func.EventGridEvent):
# # #     logging.info('Python EventGrid trigger processed an event')

# # #     # Initialize the Azure SDK clients
# # #     credential = DefaultAzureCredential()
# # #     subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
# # #     resource_group_name = os.getenv('RESOURCE_GROUP')
# # #     vnet_name = os.getenv('VNET')
# # #     subnet_name = os.getenv('SUBNET')
# # #     ip_range = os.getenv('IP_RANGE')
# # #     location = 'westeurope'  # or your desired Azure region

# # #     storage_client = StorageManagementClient(credential, subscription_id)
# # #     network_client = NetworkManagementClient(credential, subscription_id)

# # #     # Create a unique name for the new storage account
# # #     new_storage_account_name = f"storage{uuid.uuid4().hex[:16]}"
# # #     logging.info(f"The storage account name is {new_storage_account_name}")

# # #     # Define the network rule set for the new storage account
# # #     network_rule_set = NetworkRuleSet(
# # #         bypass='Logging, Metrics, AzureServices',
# # #         default_action='Deny',
# # #         virtual_network_rules=[
# # #             VirtualNetworkRule(
# # #                 virtual_network_resource_id=f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Network/virtualNetworks/{vnet_name}/subnets/{subnet_name}",
# # #                 action='Allow'
# # #             )
# # #         ],
# # #         ip_rules=[
# # #             IPRule(
# # #                 ip_address_or_range= ip_range,
# # #                 action='Allow'
# # #             )
# # #         ]
# # #     )

# # #     # Define the routing preference for the storage account
# # #     routing_preference = RoutingPreference(
# # #         routing_choice='MicrosoftRouting',  # Choose between 'MicrosoftRouting' and 'InternetRouting'
# # #         publish_microsoft_endpoints=True,
# # #         publish_internet_endpoints=True
# # #     )

# # #     # Define the parameters for the new storage account
# # #     storage_account_params = StorageAccountCreateParameters(
# # #         sku=Sku(name='Standard_LRS'),
# # #         kind=Kind.STORAGE_V2,
# # #         location=location,
# # #         is_hns_enabled=True,
# # #         network_rule_set=network_rule_set,
# # #         routing_preference=routing_preference
# # #     )

# # #     # Create the new storage account
# # #     async_storage_creation = storage_client.storage_accounts.begin_create(
# # #         resource_group_name,
# # #         new_storage_account_name,
# # #         storage_account_params
# # #     )

# # #     # Wait for the creation to complete
# # #     async_storage_creation.result()

# # #     logging.info(f"Created new storage account: {new_storage_account_name}")
