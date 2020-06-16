# (generated with --quick)

import google.api_core.page_iterator_async
from typing import Any, Callable, Coroutine

functools: module
gapic_v1: module
operations_client_config: module
operations_pb2: module
page_iterator_async: module

class OperationsAsyncClient:
    __doc__: str
    _cancel_operation: Callable
    _delete_operation: Callable
    _get_operation: Callable
    _list_operations: Callable
    operations_stub: Any
    def __init__(self, channel, client_config = ...) -> None: ...
    def cancel_operation(self, name, retry = ..., timeout = ...) -> Coroutine[Any, Any, None]: ...
    def delete_operation(self, name, retry = ..., timeout = ...) -> Coroutine[Any, Any, None]: ...
    def get_operation(self, name, retry = ..., timeout = ...) -> coroutine: ...
    def list_operations(self, name, filter_, retry = ..., timeout = ...) -> Coroutine[Any, Any, google.api_core.page_iterator_async.AsyncGRPCIterator]: ...
