# Documentation for Permission setter

<a name="documentation-for-api-endpoints"></a>
## Documentation for API Endpoints

All URIs are relative to *https://func-permission-setter-dev-001.azurewebsites.net/api*

| Class | Method | HTTP request | Description |
|------------ | ------------- | ------------- | -------------|
| *AclApi* | [**getAcl**](Apis/AclApi.md#getacl) | **GET** /acl | Get (email based) ACL for a file/folder |
*AclApi* | [**setAcl**](Apis/AclApi.md#setacl) | **PUT** /acl | Set (email based) ACL for a file/folder |
*AclApi* | [**updateAcl**](Apis/AclApi.md#updateacl) | **PATCH** /acl | Update (email based) ACL for a file/folder and its children |
| *DebugApi* | [**getUserId**](Apis/DebugApi.md#getuserid) | **GET** /get_user_id | Get user id |
*DebugApi* | [**health**](Apis/DebugApi.md#health) | **GET** /health | Health check |
*DebugApi* | [**me**](Apis/DebugApi.md#me) | **GET** /me | Get user info |


<a name="documentation-for-models"></a>
## Documentation for Models

 - [AclChangeRecursiveResponse](./Models/AclChangeRecursiveResponse.md)
 - [AclChangeRecursiveResponse_counters](./Models/AclChangeRecursiveResponse_counters.md)
 - [AclChangeResponse](./Models/AclChangeResponse.md)
 - [setAcl_200_response](./Models/setAcl_200_response.md)


<a name="documentation-for-authorization"></a>
## Documentation for Authorization

<a name="EntraId"></a>
### EntraId


<a name="EntraIdToken"></a>
### EntraIdToken

- **Type**: HTTP Bearer Token authentication (JWT)

