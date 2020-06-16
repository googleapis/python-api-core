# (generated with --quick)

import __future__
from typing import Any, Callable, Generator, TypeVar

_DEFAULT_DEADLINE: float
_DEFAULT_DELAY_MULTIPLIER: float
_DEFAULT_INITIAL_DELAY: float
_DEFAULT_MAXIMUM_DELAY: float
_LOGGER: logging.Logger
datetime: module
datetime_helpers: module
exceptions: module
functools: module
general_helpers: module
logging: module
random: module
six: module
time: module
unicode_literals: __future__._Feature

_TRetry = TypeVar('_TRetry', bound=Retry)

class Retry:
    __doc__: str
    _deadline: Any
    _initial: Any
    _maximum: Any
    _multiplier: Any
    _on_error: Any
    _predicate: Any
    deadline: Any
    def __call__(self, func, on_error = ...) -> Callable: ...
    def __init__(self, predicate = ..., initial = ..., maximum = ..., multiplier = ..., deadline = ..., on_error = ...) -> None: ...
    def __str__(self) -> str: ...
    def with_deadline(self: _TRetry, deadline) -> _TRetry: ...
    def with_delay(self: _TRetry, initial = ..., maximum = ..., multiplier = ...) -> _TRetry: ...
    def with_predicate(self: _TRetry, predicate) -> _TRetry: ...

def exponential_sleep_generator(initial, maximum, multiplier = ...) -> Generator[nothing, Any, Any]: ...
def if_exception_type(*exception_types) -> Callable[[Any], Any]: ...
def if_transient_error(exception) -> bool: ...
def retry_target(target, predicate, sleep_generator, deadline, on_error = ...) -> Any: ...
