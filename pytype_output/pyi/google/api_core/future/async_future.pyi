# (generated with --quick)

import asyncio.futures
import asyncio.tasks
import google.api_core.future.base
import google.api_core.retry_async
from typing import Any, Callable, Coroutine, Optional

DEFAULT_RETRY: google.api_core.retry_async.AsyncRetry
RETRY_PREDICATE: Callable[[Any], Any]
asyncio: module
base: module
exceptions: module
retry: module
retry_async: module

class AsyncFuture(google.api_core.future.base.Future):
    __doc__: str
    _background_task: Optional[asyncio.tasks.Task[None]]
    _future: asyncio.futures.Future
    _retry: Any
    def __init__(self, retry = ...) -> None: ...
    def _blocking_poll(self, timeout = ...) -> Coroutine[Any, Any, None]: ...
    def _done_or_raise(self) -> Coroutine[Any, Any, None]: ...
    def add_done_callback(self, fn) -> None: ...
    def done(self, retry = ...) -> Coroutine[Any, Any, nothing]: ...
    def exception(self, timeout = ...) -> Coroutine[Any, Any, Optional[BaseException]]: ...
    def result(self, timeout = ...) -> coroutine: ...
    def running(self) -> Coroutine[Any, Any, bool]: ...
    def set_exception(self, exception) -> None: ...
    def set_result(self, result) -> None: ...

class _OperationNotComplete(Exception):
    __doc__: str
