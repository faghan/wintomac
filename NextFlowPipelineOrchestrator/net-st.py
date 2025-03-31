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
    Sku,
    Kind,
    NetworkRuleSet,
    VirtualNetworkRule,
    IPRule,
    RoutingPreference
)
from azure.mgmt.authorization.models import RoleAssignmentCreateParameters

# Replace these with your values
subscription_id = "<your_subscription_id>"
resource_group_name = "<your_resource_group_name>"
storage_account_name = "<your_storage_account_name>"
vnet_id = "<your_vnet_resource_id>"  # Resource ID of the VNet
subnet_id = "<your_subnet_resource_id>"  # Resource ID of the Subnet
ip_range = "192.168.0.0/24"  # Replace with your IP range

# Authenticate using AzureDefaultCredential
credential = AzureDefaultCredential()
storage_client = StorageManagementClient(credential, subscription_id)

# Get the current storage account properties
storage_account = storage_client.storage_accounts.get_properties(
    resource_group_name, storage_account_name
)

# Update the network rule set
network_rule_set = storage_account.network_rule_set
if network_rule_set is None:
    network_rule_set = {
        "default_action": "Deny",  # Default to deny traffic
        "virtual_network_rules": [],
        "ip_rules": []
    }

# Add the VNet and subnet
network_rule_set["virtual_network_rules"].append({"virtual_network_resource_id": vnet_id})

# Add the IP range
network_rule_set["ip_rules"].append({"ip_address_or_range": ip_range})

# Update the storage account with the new network rule set
parameters = {
    "network_rule_set": network_rule_set
}
storage_client.storage_accounts.update(
    resource_group_name,
    storage_account_name,
    parameters
)

print("Storage account networking configuration updated successfully.")