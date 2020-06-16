# (generated with --quick)

import __future__
from typing import Any, Optional, Type

_GRPC_CODE_TO_EXCEPTION: dict
_HTTP_CODE_TO_EXCEPTION: dict
absolute_import: __future__._Feature
grpc: Optional[module]
http_client: module
six: module
unicode_literals: __future__._Feature

class Aborted(Conflict):
    __doc__: str
    _errors: Any
    _response: Any
    grpc_status_code: Any
    message: Any

class AlreadyExists(Conflict):
    __doc__: str
    _errors: Any
    _response: Any
    grpc_status_code: Any
    message: Any

class BadGateway(ServerError):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    message: Any

class BadRequest(ClientError):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    message: Any

class Cancelled(ClientError):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    grpc_status_code: Any
    message: Any

class ClientError(GoogleAPICallError):
    __doc__: str
    _errors: Any
    _response: Any
    message: Any

class Conflict(ClientError):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    message: Any

class DataLoss(ServerError):
    __doc__: str
    _errors: Any
    _response: Any
    grpc_status_code: Any
    message: Any

class DeadlineExceeded(GatewayTimeout):
    __doc__: str
    _errors: Any
    _response: Any
    grpc_status_code: Any
    message: Any

class FailedPrecondition(BadRequest):
    __doc__: str
    _errors: Any
    _response: Any
    grpc_status_code: Any
    message: Any

class Forbidden(ClientError):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    message: Any

class GatewayTimeout(ServerError):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    message: Any

class GoogleAPICallError(GoogleAPIError, metaclass=_GoogleAPICallErrorMeta):
    __doc__: str
    _errors: Any
    _response: Any
    code: Any
    errors: list
    grpc_status_code: Any
    message: Any
    response: Any
    def __init__(self, message, errors = ..., response = ...) -> None: ...
    def __str__(self) -> str: ...

class GoogleAPIError(Exception):
    __doc__: str

class InternalServerError(ServerError):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    grpc_status_code: Any
    message: Any

class InvalidArgument(BadRequest):
    __doc__: str
    _errors: Any
    _response: Any
    grpc_status_code: Any
    message: Any

class LengthRequired(ClientError):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    message: Any

class MethodNotAllowed(ClientError):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    message: Any

class MethodNotImplemented(ServerError):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    grpc_status_code: Any
    message: Any

class MovedPermanently(Redirection):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    message: Any

class NotFound(ClientError):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    grpc_status_code: Any
    message: Any

class NotModified(Redirection):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    message: Any

class OutOfRange(BadRequest):
    __doc__: str
    _errors: Any
    _response: Any
    grpc_status_code: Any
    message: Any

class PermissionDenied(Forbidden):
    __doc__: str
    _errors: Any
    _response: Any
    grpc_status_code: Any
    message: Any

class PreconditionFailed(ClientError):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    message: Any

class Redirection(GoogleAPICallError):
    __doc__: str
    _errors: Any
    _response: Any
    message: Any

class RequestRangeNotSatisfiable(ClientError):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    message: Any

class ResourceExhausted(TooManyRequests):
    __doc__: str
    _errors: Any
    _response: Any
    grpc_status_code: Any
    message: Any

class ResumeIncomplete(Redirection):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    message: Any

class RetryError(GoogleAPIError):
    __doc__: str
    _cause: Any
    cause: Any
    message: Any
    def __init__(self, message, cause) -> None: ...
    def __str__(self) -> str: ...

class ServerError(GoogleAPICallError):
    __doc__: str
    _errors: Any
    _response: Any
    message: Any

class ServiceUnavailable(ServerError):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    grpc_status_code: Any
    message: Any

class TemporaryRedirect(Redirection):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    message: Any

class TooManyRequests(ClientError):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    message: Any

class Unauthenticated(Unauthorized):
    __doc__: str
    _errors: Any
    _response: Any
    grpc_status_code: Any
    message: Any

class Unauthorized(ClientError):
    __doc__: str
    _errors: Any
    _response: Any
    code: int
    message: Any

class Unknown(ServerError):
    __doc__: str
    _errors: Any
    _response: Any
    grpc_status_code: Any
    message: Any

class _GoogleAPICallErrorMeta(type):
    __doc__: str
    def __new__(mcs: Type[_GoogleAPICallErrorMeta], name, bases, class_dict) -> Any: ...

def _is_informative_grpc_error(rpc_exc) -> bool: ...
def exception_class_for_grpc_status(status_code) -> Any: ...
def exception_class_for_http_status(status_code) -> Any: ...
def from_grpc_error(rpc_exc) -> Any: ...
def from_grpc_status(status_code, message, **kwargs) -> Any: ...
def from_http_response(response) -> Any: ...
def from_http_status(status_code, message, **kwargs) -> Any: ...
