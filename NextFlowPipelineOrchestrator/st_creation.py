import os
import uuid
import random
import string
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.authorization import AuthorizationManagementClient
from azure.mgmt.authorization.models import RoleAssignmentCreateParameters, RoleAssignmentProperties
from azure.mgmt.storage.models import (
    StorageAccountCreateParameters,
    StorageAccountUpdateParameters,
    Sku,
    Kind,
    NetworkRuleSet,
    VirtualNetworkRule,
    IPRule,
    RoutingPreference
)
from azure.mgmt.authorization.models import RoleAssignmentCreateParameters
from azure.storage.blob import BlobServiceClient

load_dotenv()

def generate_storage_account_name():
    return f"stvm{uuid.uuid4().hex[:8]}"

def storage_account_exists(storage_client, resource_group_name, storage_account_name):
    try:
        storage_client.storage_accounts.get_properties(resource_group_name, storage_account_name)
        print(f"Storage account '{storage_account_name}' already exists.")
        return True
    except Exception as e:
        return False

def create_storage_account(
    credential,
    subscription_id,
    resource_group_name,
    storage_account_name,
    location,
    vnet_name,
    subnet_name,
    vnet_resource_group,
    ip_range
):
    storage_client = StorageManagementClient(credential, subscription_id)
    network_client = NetworkManagementClient(credential, subscription_id)

    subnet = network_client.subnets.get(vnet_resource_group, vnet_name, subnet_name)
    subnet_id = subnet.id

    parameters = StorageAccountCreateParameters(
        location=location,
        sku=Sku(name="Standard_LRS"),
        kind=Kind.STORAGE_V2,
        enable_https_traffic_only=True,
        is_hns_enabled=True,
        access_tier="Hot",
        minimum_tls_version="TLS1_2",
        allow_blob_public_access=False,
        network_rule_set=NetworkRuleSet(
            bypass="AzureServices,Logging,Metrics",
            default_action="Deny",
            virtual_network_rules=[VirtualNetworkRule(virtual_network_resource_id=subnet_id)],
            ip_rules=[IPRule(ip_address_or_range=ip_range)]
        ),
        routing_preference=RoutingPreference(
            publish_microsoft_endpoints=True,
            publish_internet_endpoints=True
        )
    )

    storage_account = storage_client.storage_accounts.begin_create(
        resource_group_name,
        storage_account_name,
        parameters
    ).result()

    created_account = storage_client.storage_accounts.get_properties(resource_group_name, storage_account_name)
    if created_account:
        print(f"Storage account '{storage_account_name}' created successfully.")
        return storage_account
    else:
        print(f"Failed to confirm the creation of storage account '{storage_account_name}'")
        return None

def assign_storage_blob_data_contributor_role(
    credential,
    subscription_id,
    resource_group_name,
    storage_account_name,
    user_assigned_identity_id
):
    auth_client = AuthorizationManagementClient(credential, subscription_id)

    storage_account_id = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Storage/storageAccounts/{storage_account_name}"

    role_definition_id = f"/subscriptions/{subscription_id}/providers/Microsoft.Authorization/roleDefinitions/ba92f5b4-2d11-453d-a403-e96b0029c9fe"

    role_assignment_params = RoleAssignmentCreateParameters(
        role_definition_id=role_definition_id,
        principal_id=user_assigned_identity_id,
        principal_type="ServicePrincipal",
        scope=storage_account_id
    )

    role_assignment = auth_client.role_assignments.create(
        scope=storage_account_id,
        role_assignment_name=str(uuid.uuid4()),  
        parameters=role_assignment_params
    )

    print(f"Assigned 'Storage Blob Data Contributor' role to managed identity {user_assigned_identity_id} on storage account {storage_account_name}")
    return role_assignment


def delete_container_and_vnet(credential, subscription_id, resource_group, account_name: str, container_name: str, vnet_id: str):
    # Construct the account URL using the provided storage account name
    account_url = f"https://{account_name}.blob.core.windows.net"
    
    # Use DefaultAzureCredential for authentication
    # credential = DefaultAzureCredential()
    
    # Create BlobServiceClient for container operations
    blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
    
    # Create the StorageManagementClient for managing storage account settings
    storage_client = StorageManagementClient(credential, subscription_id)  # Add your subscription ID here
    
    # Get the storage account
    storage_account = storage_client.storage_accounts.get_properties(resource_group, account_name)
    
    try:
        # Get the container client and delete the container
        container_client = blob_service_client.get_container_client(container_name)
        container_client.delete_container()
        print(f"Container '{container_name}' has been deleted successfully.")
        
        # Update network rules to remove the VNet
        # Get the current network rules
        current_network_rules = storage_account.network_rule_set
        if current_network_rules.virtual_network_rules:
            # Filter out the VNet ID from the list
            updated_vnet_rules = [
                rule for rule in current_network_rules.virtual_network_rules if rule.virtual_network_resource_id != vnet_id
            ]
            
            # Create the update parameters
            update_params = StorageAccountUpdateParameters(
                network_rule_set={
                    "virtual_network_rules": updated_vnet_rules
                }
            )
            
            # Update the storage account with the new network rules
            storage_client.storage_accounts.update(
                resource_group,
                account_name,
                update_params
            )
            print(f"VNet '{vnet_id}' has been removed from the storage account networking rules.")
        else:
            print("No virtual network rules are currently applied to the storage account.")
        
    except Exception as e:
        print(f"Error: {e}")
# import os
# import uuid
# import random
# import string
# from dotenv import load_dotenv
# from azure.identity import DefaultAzureCredential
# from azure.mgmt.storage import StorageManagementClient
# from azure.mgmt.network import NetworkManagementClient
# from azure.mgmt.storage.models import (
#     StorageAccountCreateParameters,
#     Sku,
#     Kind,
#     NetworkRuleSet,
#     VirtualNetworkRule,
#     IPRule,
#     RoutingPreference
# )

# # Load environment variables from .env file
# load_dotenv()

# def generate_storage_account_name():
#     return f"stvm{uuid.uuid4().hex[:8]}"

# def storage_account_exists(storage_client, resource_group_name, storage_account_name):
#     """Check if the storage account already exists."""
#     try:
#         storage_client.storage_accounts.get_properties(resource_group_name, storage_account_name)
#         print(f"Storage account '{storage_account_name}' already exists.")
#         return True
#     except Exception as e:
#         # Account does not exist
#         return False

# def create_storage_account(
#     credential,
#     subscription_id,
#     resource_group_name,
#     storage_account_name,
#     location,
#     vnet_name,
#     subnet_name,
#     vnet_resource_group,
#     ip_range
# ):
#     # Initialize clients within the function to avoid scope conflicts
#     storage_client = StorageManagementClient(credential, subscription_id)
#     network_client = NetworkManagementClient(credential, subscription_id)

#     # Get the subnet resource ID
#     subnet = network_client.subnets.get(vnet_resource_group, vnet_name, subnet_name)
#     subnet_id = subnet.id

#     # Configure storage account parameters
#     parameters = StorageAccountCreateParameters(
#         location=location,
#         sku=Sku(name="Standard_LRS"),
#         kind=Kind.STORAGE_V2,
#         enable_https_traffic_only=True,
#         is_hns_enabled=True,
#         access_tier="Hot",
#         minimum_tls_version="TLS1_2",
#         allow_blob_public_access=False,
#         network_rule_set=NetworkRuleSet(
#             bypass="AzureServices,Logging,Metrics",
#             default_action="Deny",
#             virtual_network_rules=[
#                 VirtualNetworkRule(virtual_network_resource_id=subnet_id)
#             ],
#             ip_rules=[
#                 IPRule(ip_address_or_range=ip_range)
#             ]
#         ),
#         routing_preference=RoutingPreference(
#             publish_microsoft_endpoints=True,
#             publish_internet_endpoints=True
#         )
#     )

#     # Create the storage account
#     storage_account = storage_client.storage_accounts.begin_create(
#         resource_group_name,
#         storage_account_name,
#         parameters
#     ).result()

#     # Check if storage account creation was successful
#     created_account = storage_client.storage_accounts.get_properties(resource_group_name, storage_account_name)
#     if created_account:
#         print(f"Storage account '{storage_account_name}' created successfully.")
#         return storage_account
#     else:
#         print(f"Failed to confirm the creation of storage account '{storage_account_name}'")
#         return None

# def add_vnet_to_storage_account(credential, subscription_id, resource_group_name, storage_account_name, vnet_name, subnet_name):
#     # Initialize Azure credentials and clients
#     storage_client = StorageManagementClient(credential, subscription_id)
#     network_client = NetworkManagementClient(credential, subscription_id)

#     # Fetch the subnet details
#     subnet = network_client.subnets.get(resource_group_name, vnet_name, subnet_name)
    
#     # Enable Microsoft.Storage service endpoint if not already enabled
#     service_endpoints = [endpoint.service for endpoint in subnet.service_endpoints]
#     if "Microsoft.Storage" not in service_endpoints:
#         subnet.service_endpoints.append({
#             "service": "Microsoft.Storage",
#             "locations": [subnet.location]
#         })
        
#         # Update the subnet with the new service endpoint
#         network_client.subnets.begin_create_or_update(
#             resource_group_name,
#             vnet_name,
#             subnet_name,
#             subnet
#         ).result()
#         print(f"Service endpoint for Microsoft.Storage enabled on subnet {subnet_name} in VNet {vnet_name}")

#     # Construct the VNet resource ID for the storage account network rules
#     vnet_resource_id = subnet.id

#     # Fetch the current storage account properties
#     storage_account = storage_client.storage_accounts.get_properties(resource_group_name, storage_account_name)

#     # Initialize or update the network rule set to add the VNet
#     network_rule_set = storage_account.network_rule_set or {
#         "virtual_network_rules": [],
#         "bypass": "AzureServices",
#         "default_action": "Deny"
#     }

#     # Add the VNet to the list of allowed virtual networks
#     network_rule_set.virtual_network_rules.append({
#         "virtual_network_resource_id": vnet_resource_id,
#         "action": "Allow"
#     })

#     # Update the storage account with the new network rule set
#     storage_client.storage_accounts.update(
#         resource_group_name=resource_group_name,
#         account_name=storage_account_name,
#         parameters={
#             "network_rule_set": network_rule_set
#         }
#     )

#     print(f"VNet {vnet_name} added to storage account {storage_account_name}")
