# AclApi

All URIs are relative to *https://func-permission-setter-dev-001.azurewebsites.net/api*

| Method | HTTP request | Description |
|------------- | ------------- | -------------|
| [**getAcl**](AclApi.md#getAcl) | **GET** /acl |  |
| [**setAcl**](AclApi.md#setAcl) | **PUT** /acl |  |
| [**updateAcl**](AclApi.md#updateAcl) | **PATCH** /acl |  |


<a name="getAcl"></a>
# **getAcl**
> String getAcl(container, path)



    Get (email based) ACL for a file/folder

### Parameters

|Name | Type | Description  | Notes |
|------------- | ------------- | ------------- | -------------|
| **container** | **String**| Container name | [default to null] |
| **path** | **String**| Path to the file/folder | [default to null] |

### Return type

**String**

### Authorization

[EntraIdToken](../README.md#EntraIdToken), [EntraId](../README.md#EntraId)

### HTTP request headers

- **Content-Type**: Not defined
- **Accept**: text/plain, application/json

### Example usage

Curl request:
```bash
curl -X  \
 -H "Authorization: Bearer $(az account get-access-token --scope api://4209c9a4-1789-49f0-9c50-92e4cf402805/.default -s aee8556f-d2fd-4efd-a6bd-f341a90fa76e --query accessToken -o tsv)" \
 \
 -H "Accept: text/plain,application/json" \
 "https://func-permission-setter-dev-001.azurewebsites.net/api/acl?container=sandbox&path=permission-setter-test"
```

Python azure sdk request:
```python
from azure.core import PipelineClient
from azure.core.rest import HttpRequest
from azure.identity import DefaultAzureCredential
from pprint import pprint


cred = DefaultAzureCredential()


request = HttpRequest(
    '',
    'https://func-permission-setter-dev-001.azurewebsites.net/api/acl?container=sandbox&path=permission-setter-test',
    headers=dict(Authorization='Bearer ' + cred.get_token('api://4209c9a4-1789-49f0-9c50-92e4cf402805/.default').token)
)

client = PipelineClient(base_url='https://func-permission-setter-dev-001.azurewebsites.net/api')
response = client.send_request(request)
pprint(response)
```

<a name="setAcl"></a>
# **setAcl**
> setAcl_200_response setAcl(container, path, acl, recursive)



    Set (email based) ACL for a file/folder

### Parameters

|Name | Type | Description  | Notes |
|------------- | ------------- | ------------- | -------------|
| **container** | **String**| Container name | [default to null] |
| **path** | **String**| Path to the file/folder | [default to null] |
| **acl** | **String**| Email based ACL | [default to null] |
| **recursive** | **Boolean**| Set ACL recursively | [optional] [default to null] |

### Return type

[**setAcl_200_response**](../Models/setAcl_200_response.md)

### Authorization

[EntraIdToken](../README.md#EntraIdToken), [EntraId](../README.md#EntraId)

### HTTP request headers

- **Content-Type**: Not defined
- **Accept**: application/json, text/plain

### Example usage

Curl request:
```bash
curl -X  \
 -H "Authorization: Bearer $(az account get-access-token --scope api://4209c9a4-1789-49f0-9c50-92e4cf402805/.default -s aee8556f-d2fd-4efd-a6bd-f341a90fa76e --query accessToken -o tsv)" \
 \
 -H "Accept: application/json,text/plain" \
 "https://func-permission-setter-dev-001.azurewebsites.net/api/acl?container=sandbox&path=permission-setter-test&acl=user:test@test.test:rwx,group::r--,other::r--&recursive=false"
```

Python azure sdk request:
```python
from azure.core import PipelineClient
from azure.core.rest import HttpRequest
from azure.identity import DefaultAzureCredential
from pprint import pprint


cred = DefaultAzureCredential()


request = HttpRequest(
    '',
    'https://func-permission-setter-dev-001.azurewebsites.net/api/acl?container=sandbox&path=permission-setter-test&acl=user:test@test.test:rwx,group::r--,other::r--&recursive=false',
    headers=dict(Authorization='Bearer ' + cred.get_token('api://4209c9a4-1789-49f0-9c50-92e4cf402805/.default').token)
)

client = PipelineClient(base_url='https://func-permission-setter-dev-001.azurewebsites.net/api')
response = client.send_request(request)
pprint(response)
```

<a name="updateAcl"></a>
# **updateAcl**
> AclChangeRecursiveResponse updateAcl(container, path, acl)



    Update (email based) ACL for a file/folder and its children

### Parameters

|Name | Type | Description  | Notes |
|------------- | ------------- | ------------- | -------------|
| **container** | **String**| Container name | [default to null] |
| **path** | **String**| Path to the file/folder | [default to null] |
| **acl** | **String**| Email based ACL | [default to null] |

### Return type

[**AclChangeRecursiveResponse**](../Models/AclChangeRecursiveResponse.md)

### Authorization

[EntraIdToken](../README.md#EntraIdToken), [EntraId](../README.md#EntraId)

### HTTP request headers

- **Content-Type**: Not defined
- **Accept**: application/json, text/plain

### Example usage

Curl request:
```bash
curl -X  \
 -H "Authorization: Bearer $(az account get-access-token --scope api://4209c9a4-1789-49f0-9c50-92e4cf402805/.default -s aee8556f-d2fd-4efd-a6bd-f341a90fa76e --query accessToken -o tsv)" \
 \
 -H "Accept: application/json,text/plain" \
 "https://func-permission-setter-dev-001.azurewebsites.net/api/acl?container=sandbox&path=permission-setter-test&acl=user:test@test.test:rwx,group::r--,other::r--"
```

Python azure sdk request:
```python
from azure.core import PipelineClient
from azure.core.rest import HttpRequest
from azure.identity import DefaultAzureCredential
from pprint import pprint


cred = DefaultAzureCredential()


request = HttpRequest(
    '',
    'https://func-permission-setter-dev-001.azurewebsites.net/api/acl?container=sandbox&path=permission-setter-test&acl=user:test@test.test:rwx,group::r--,other::r--',
    headers=dict(Authorization='Bearer ' + cred.get_token('api://4209c9a4-1789-49f0-9c50-92e4cf402805/.default').token)
)

client = PipelineClient(base_url='https://func-permission-setter-dev-001.azurewebsites.net/api')
response = client.send_request(request)
pprint(response)
```

