# (generated with --quick)

from typing import Any, Callable, Generator, TypeVar

_DEFAULT_DEADLINE: float
_DEFAULT_DELAY_MULTIPLIER: float
_DEFAULT_INITIAL_DELAY: float
_DEFAULT_MAXIMUM_DELAY: float
_LOGGER: logging.Logger
asyncio: module
datetime: module
datetime_helpers: module
exceptions: module
functools: module
logging: module

_TAsyncRetry = TypeVar('_TAsyncRetry', bound=AsyncRetry)

class AsyncRetry:
    __doc__: str
    _deadline: Any
    _initial: Any
    _maximum: Any
    _multiplier: Any
    _on_error: Any
    _predicate: Any
    def __call__(self, func, on_error = ...) -> Callable: ...
    def __init__(self, predicate = ..., initial = ..., maximum = ..., multiplier = ..., deadline = ..., on_error = ...) -> None: ...
    def __str__(self) -> str: ...
    def _replace(self: _TAsyncRetry, predicate = ..., initial = ..., maximum = ..., multiplier = ..., deadline = ..., on_error = ...) -> _TAsyncRetry: ...
    def with_deadline(self: _TAsyncRetry, deadline) -> _TAsyncRetry: ...
    def with_delay(self: _TAsyncRetry, initial = ..., maximum = ..., multiplier = ...) -> _TAsyncRetry: ...
    def with_predicate(self: _TAsyncRetry, predicate) -> _TAsyncRetry: ...

def exponential_sleep_generator(initial, maximum, multiplier = ...) -> Generator[nothing, Any, Any]: ...
def if_exception_type(*exception_types) -> Callable[[Any], Any]: ...
def if_transient_error(exception) -> bool: ...
def retry_target(target, predicate, sleep_generator, deadline, on_error = ...) -> coroutine: ...
