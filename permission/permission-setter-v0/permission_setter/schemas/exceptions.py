from http import HTTPStatus
from typing import Optional, Union

from azure.functions import HttpResponse


class ServerError(Exception):
    """Base class for server errors."""

    def __init__(
            self,
            message: str,
            status_code: Optional[Union[HTTPStatus, int]],
            mimetype: Optional[str] = "text/plain",
    ) -> None:
        self.status_code = status_code
        self.mimetype = mimetype
        super().__init__(message)

    def to_http_response(self) -> HttpResponse:
        return HttpResponse(
            str(self),
            status_code=self.status_code,
            mimetype=self.mimetype,
        )


class BadRequest(ServerError):
    """Base class for bad request errors."""

    def __init__(self, message: str, status_code: int = HTTPStatus.BAD_REQUEST) -> None:
        super().__init__(message, status_code)


class Unauthorised(ServerError):
    """Base class for unauthorised errors."""

    def __init__(self, message: str, status_code: int = HTTPStatus.UNAUTHORIZED) -> None:
        super().__init__(message, status_code)


class NotFound(ServerError):
    """Base class for not found errors."""

    def __init__(self, message: str, status_code: int = HTTPStatus.NOT_FOUND) -> None:
        super().__init__(message, status_code)


class InternalServerError(ServerError):
    """Base class for internal server errors."""

    def __init__(self, message: str, status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR) -> None:
        super().__init__(message, status_code)
