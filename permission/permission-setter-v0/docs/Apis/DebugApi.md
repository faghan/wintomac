# DebugApi

All URIs are relative to *https://func-permission-setter-dev-001.azurewebsites.net/api*

| Method | HTTP request | Description |
|------------- | ------------- | -------------|
| [**getUserId**](DebugApi.md#getUserId) | **GET** /get_user_id |  |
| [**health**](DebugApi.md#health) | **GET** /health |  |
| [**me**](DebugApi.md#me) | **GET** /me |  |


<a name="getUserId"></a>
# **getUserId**
> String getUserId(email)



    Get user id

### Parameters

|Name | Type | Description  | Notes |
|------------- | ------------- | ------------- | -------------|
| **email** | **String**| Email address | [default to null] |

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
 "https://func-permission-setter-dev-001.azurewebsites.net/api/get_user_id?email=email_example"
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
    'https://func-permission-setter-dev-001.azurewebsites.net/api/get_user_id?email=email_example',
    headers=dict(Authorization='Bearer ' + cred.get_token('api://4209c9a4-1789-49f0-9c50-92e4cf402805/.default').token)
)

client = PipelineClient(base_url='https://func-permission-setter-dev-001.azurewebsites.net/api')
response = client.send_request(request)
pprint(response)
```

<a name="health"></a>
# **health**
> String health()



    Health check

### Parameters
This endpoint does not need any parameter.

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
 "https://func-permission-setter-dev-001.azurewebsites.net/api/health"
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
    'https://func-permission-setter-dev-001.azurewebsites.net/api/health',
    headers=dict(Authorization='Bearer ' + cred.get_token('api://4209c9a4-1789-49f0-9c50-92e4cf402805/.default').token)
)

client = PipelineClient(base_url='https://func-permission-setter-dev-001.azurewebsites.net/api')
response = client.send_request(request)
pprint(response)
```

<a name="me"></a>
# **me**
> String me()



    Get user info

### Parameters
This endpoint does not need any parameter.

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
 "https://func-permission-setter-dev-001.azurewebsites.net/api/me"
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
    'https://func-permission-setter-dev-001.azurewebsites.net/api/me',
    headers=dict(Authorization='Bearer ' + cred.get_token('api://4209c9a4-1789-49f0-9c50-92e4cf402805/.default').token)
)

client = PipelineClient(base_url='https://func-permission-setter-dev-001.azurewebsites.net/api')
response = client.send_request(request)
pprint(response)
```

