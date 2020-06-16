# (generated with --quick)

import google.api_core.future.base
import google.api_core.retry
import threading
from typing import Any, Callable, Optional

DEFAULT_RETRY: google.api_core.retry.Retry
RETRY_PREDICATE: Callable[[Any], Any]
_helpers: module
abc: module
base: module
concurrent: module
exceptions: module
retry: module

class PollingFuture(google.api_core.future.base.Future):
    __doc__: str
    _done_callbacks: list
    _exception: Any
    _polling_thread: Optional[threading.Thread]
    _result: Any
    _result_set: bool
    _retry: Any
    def __init__(self, retry = ...) -> None: ...
    def _blocking_poll(self, timeout = ...) -> None: ...
    def _done_or_raise(self) -> None: ...
    def _invoke_callbacks(self, *args, **kwargs) -> None: ...
    def add_done_callback(self, fn) -> None: ...
    @abstractmethod
    def done(self, retry = ...) -> Any: ...
    def exception(self, timeout = ...) -> Any: ...
    def result(self, timeout = ...) -> Any: ...
    def running(self) -> bool: ...
    def set_exception(self, exception) -> None: ...
    def set_result(self, result) -> None: ...

class _OperationNotComplete(Exception):
    __doc__: str
