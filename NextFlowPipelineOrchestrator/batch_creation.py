import uuid
import random
import string
from azure.identity import DefaultAzureCredential
from azure.mgmt.batch import BatchManagementClient
from azure.mgmt.batch.models import (
    BatchAccountCreateParameters,
    AutoStorageBaseProperties,
    BatchAccountIdentity,
    BatchAccountUpdateParameters
)
from azure.mgmt.authorization import AuthorizationManagementClient
from azure.mgmt.authorization.models import RoleAssignmentCreateParameters

def create_batch_account_with_identity(
    credential,
    subscription_id,
    resource_group_name,
    storage_account_id,
    user_assigned_identity_id,
    batch_account_name,
    location
):
    
    batch_client = BatchManagementClient(credential, subscription_id)
    
    identity = BatchAccountIdentity(
        type="UserAssigned",
        user_assigned_identities={user_assigned_identity_id: {}}
    )

    batch_params = BatchAccountCreateParameters(
        location=location,
        identity=identity,
        auto_storage=AutoStorageBaseProperties(
            storage_account_id=storage_account_id,
            authentication_mode="BatchAccountManagedIdentity",
            node_identity_reference={
                "resourceId": user_assigned_identity_id  
            }
        ),
        public_network_access="Enabled"
    )

    batch_account = batch_client.batch_account.begin_create(
        resource_group_name=resource_group_name,
        account_name=batch_account_name,
        parameters=batch_params
    ).result()  
    print(f"Batch account '{batch_account_name}' created in '{location}' with managed identity for storage access.")

    update_params = BatchAccountUpdateParameters(
        identity=BatchAccountIdentity(
            type="UserAssigned",
            user_assigned_identities={user_assigned_identity_id: {}}
        )
    )

    batch_client.batch_account.update(
        resource_group_name=resource_group_name,
        account_name=batch_account_name,
        parameters=update_params
    )

    print(f"User-assigned managed identity added to Node Identity Reference for Batch account '{batch_account_name}'.")

    return batch_account

def assign_contributor_role_to_identity(credential, subscription_id, batch_account_id, user_assigned_identity_object_id):
    auth_client = AuthorizationManagementClient(credential, subscription_id)

    role_assignment_name = str(uuid.uuid4())  
    role_definition_id = f"/subscriptions/{subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b24988ac-6180-42a0-ab88-20f7382dd24c"

    role_assignment_params = RoleAssignmentCreateParameters(
        role_definition_id=role_definition_id,
        principal_id = user_assigned_identity_object_id,  
        principal_type="ServicePrincipal",
        scope=batch_account_id
    )

    auth_client.role_assignments.create(
        scope=batch_account_id,
        role_assignment_name=role_assignment_name,
        parameters=role_assignment_params
    )

    print(f"Assigned 'Contributor' role to the user-assigned managed identity at the scope of Batch account {batch_account_id}.")

def delete_batch_account(credential, subscription_id: str, resource_group: str, batch_account_name: str):
    # Use DefaultAzureCredential for authentication (will use environment or CLI credentials)
    # credential = DefaultAzureCredential()

    # Create a BatchManagementClient
    batch_client = BatchManagementClient(credential, subscription_id)

    try:
        # Delete the Batch account
        delete_poller=batch_client.batch_account.begin_delete(
            resource_group_name=resource_group,
            account_name=batch_account_name
        )

        delete_poller.result()

        print(f"Batch account '{batch_account_name}' in resource group '{resource_group}' has been deleted successfully.")
    
    except Exception as e:
        print(f"Error deleting Batch account: {e}")
# def delete_batch_account(credential, subscription_id: str, resource_group: str, batch_account_name: str):
#     """
#     Deletes an Azure Batch account.
    
#     :param subscription_id: Your Azure Subscription ID.
#     :param resource_group: The resource group that contains the Batch account.
#     :param batch_account_name: The name of the Batch account to delete.
#     """
#     # Use DefaultAzureCredential for authentication (will use environment or CLI credentials)
#     # credential = DefaultAzureCredential()

#     # Create a BatchManagementClient
#     batch_client = BatchManagementClient(credential, subscription_id)

#     try:
#         # Delete the Batch account
#         batch_client.batch_account.delete(
#             resource_group_name=resource_group,
#             account_name=batch_account_name
#         )

#         print(f"Batch account '{batch_account_name}' in resource group '{resource_group}' has been deleted successfully.")
    
#     except Exception as e:
#         print(f"Error deleting Batch account: {e}")