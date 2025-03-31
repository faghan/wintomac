import json
import logging
import requests

from urllib.parse import quote


class SavvyError(Exception):
    pass


# https://incyght.exputec.com/api_docs/data/
# List API end-points:
BATCHES = "batches"
UNIT_OPERATIONS = "unitoperations"
USERS = "users"
VARIABLES_DETAILED_LIST = "variables/detailed_list"

# Detail API end-points:
BATCHES_VARIABLE_DATA = "batches/{id}/variable_data"

# Other API end-points:
AUTHENTICATION = "token_auth"


class Client:
    __slots__ = ("_user", "_server_url", "_session")

    def __init__(self, server_url, username, password):
        self._session = requests.Session()
        self._server_url = server_url
        self._user = User(username, password)
        self._user.connect(self._server_url, session=self._session)

    def api_list(self, endpoint, **kwargs):
        kwargs.setdefault("page", 1)
        kwargs.setdefault("pageSize", 100)
        args = "&".join(f"{key}={quote(str(value))}" for key, value in kwargs.items())

        log = logging.getLogger(__name__)
        endpoint = f"{self._server_url}/api/{endpoint}/"
        page_url = f"{endpoint}?{args}"

        while page_url:

            log.info("listing objects from API endpoint %r", page_url)

            data = self._get(page_url)
            page_url = data["next"]

            # HACK: The next url does not include port number, so we need to get the args and concat with endpoint
            if page_url:
                args = page_url.split("?")[1]
                page_url = f"{endpoint}?{args}"

            yield from data["results"]

    def api_get(self, endpoint, id):
        log = logging.getLogger(__name__)
        endpoint = endpoint.format(id=id)

        log.info("getting object from API endpoint %r with id %i", endpoint, id)
        return self._get(f"{self._server_url}/api/{endpoint}/")

    def _get(self, url):
        try:
            resp = self._session.get(url, cookies={"jwt": self._user.token})
            resp.raise_for_status()
        except requests.RequestException as error:
            raise SavvyError(f"error calling API at {url}") from error

        try:
            return resp.json()
        except json.JSONDecodeError as error:
            raise SavvyError(f"error decoding API response from {url}") from error


class User:
    __slots__ = ("username", "password", "token")

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.token = None

    def connect(self, server_url, session=requests):
        log = logging.getLogger(__name__)
        log.info("authenticating user %r for %r", self.username, server_url)

        try:
            resp = requests.post(
                f"{server_url}/api/{AUTHENTICATION}/",
                data={"username": self.username, "password": self.password,},
            )

            resp.raise_for_status()
        except requests.RequestException as error:
            raise SavvyError("failed to authenticate") from error

        log.info("decoding JSON response from server")
        try:
            data = resp.json()
        except json.JSONDecodeError as error:
            raise SavvyError("invalid response to authentication request") from error

        log.info("client authenticated")
        self.token = data["token"]
