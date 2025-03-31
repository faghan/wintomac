from azure.identity import DefaultAzureCredential
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.keyvault.secrets import SecretClient

def allow_vnet_in_key_vault(
    credential,
    subscription_id,
    resource_group,
    vault_name,
    vnet_id,
):
   
    try:
        keyvault_client = KeyVaultManagementClient(credential, subscription_id)
        keyvault = keyvault_client.vaults.get(resource_group, vault_name)
        network_acls = keyvault.properties.network_acls

        network_acls.virtual_network_rules.append({
            'id': vnet_id,
            'ignore_missing_vnet_service_endpoint': False
        })

        keyvault_client.vaults.update(
            resource_group,
            vault_name,
            {
                'properties': {
                    'network_acls': network_acls
                }
            }
        )
        print(f"VNet {vnet_id} successfully added to Key Vault {vault_name}'s allowed networks.")

    except Exception as e:
        print(f"An error occurred: {e}")
