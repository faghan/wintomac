from typing import Coroutine, Any

from msgraph import GraphServiceClient
from msgraph.generated.models.user import User

from permission_setter.settings import APP_CREDENTIALS

graph_client = GraphServiceClient(APP_CREDENTIALS)
users_client = graph_client.users


async def get_user(**kwargs) -> User:
    query_parameters = users_client.UsersRequestBuilderGetQueryParameters(**kwargs)
    request_configuration = users_client.UsersRequestBuilderGetRequestConfiguration(
        query_parameters=query_parameters
    )
    user_collection_response = await users_client.get(request_configuration)
    users = user_collection_response.value
    assert len(users) == 1, f"Expected 1 user, got {len(users)}"
    return users[0]


def get_user_by_mail(mail: str) -> Coroutine[Any, Any, User]:
    return get_user(filter=f"mail eq '{mail}'", select=["id", "mail", "displayName"])


def get_user_by_id(user_id: str) -> Coroutine[Any, Any, User]:
    return get_user(filter=f"id eq '{user_id}'", select=["id", "mail", "displayName"])
