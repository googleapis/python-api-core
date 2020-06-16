# (generated with --quick)

import google.api_core.page_iterator
from typing import Any, Callable

functools: module
gapic_v1: module
operations_client_config: module
operations_pb2: module
page_iterator: module

class OperationsClient:
    __doc__: str
    _cancel_operation: Callable
    _delete_operation: Callable
    _get_operation: Callable
    _list_operations: Callable
    operations_stub: Any
    def __init__(self, channel, client_config = ...) -> None: ...
    def cancel_operation(self, name, retry = ..., timeout = ...) -> None: ...
    def delete_operation(self, name, retry = ..., timeout = ...) -> None: ...
    def get_operation(self, name, retry = ..., timeout = ...) -> Any: ...
    def list_operations(self, name, filter_, retry = ..., timeout = ...) -> google.api_core.page_iterator.GRPCIterator: ...
