# (generated with --quick)

import google.api_core.future.async_future
from typing import Any, Coroutine

async_future: module
code_pb2: module
exceptions: module
functools: module
operations_pb2: module
protobuf_helpers: module
threading: module

class AsyncOperation(google.api_core.future.async_future.AsyncFuture):
    __doc__: str
    _cancel: Any
    _completion_lock: threading.Lock
    _metadata_type: Any
    _operation: Any
    _refresh: Any
    _result_type: Any
    metadata: Any
    operation: Any
    def __init__(self, operation, refresh, cancel, result_type, metadata_type = ..., retry = ...) -> None: ...
    def _refresh_and_update(self, retry = ...) -> Coroutine[Any, Any, None]: ...
    def _set_result_from_operation(self) -> None: ...
    def cancel(self) -> Coroutine[Any, Any, bool]: ...
    def cancelled(self) -> coroutine: ...
    @classmethod
    def deserialize(cls, payload) -> Any: ...
    def done(self, retry = ...) -> coroutine: ...

def from_gapic(operation, operations_client, result_type, **kwargs) -> AsyncOperation: ...
