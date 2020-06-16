# (generated with --quick)

from typing import Any, Callable

DEFAULT: Any
USE_DEFAULT_METADATA: Any
client_info: module
general_helpers: module
grpc_helpers: module
timeout: module

class _GapicCallable:
    __doc__: str
    _metadata: Any
    _retry: Any
    _target: Any
    _timeout: Any
    def __call__(self, *args, **kwargs) -> Any: ...
    def __init__(self, target, retry, timeout, metadata = ...) -> None: ...

def _apply_decorators(func, decorators) -> Any: ...
def _determine_timeout(default_timeout, specified_timeout, retry) -> Any: ...
def _is_not_none_or_false(value) -> bool: ...
def wrap_method(func, default_retry = ..., default_timeout = ..., client_info = ...) -> Callable: ...
