# (generated with --quick)

import __future__
from typing import Any, Callable, TypeVar

_DEFAULT_DEADLINE: None
_DEFAULT_INITIAL_TIMEOUT: float
_DEFAULT_MAXIMUM_TIMEOUT: float
_DEFAULT_TIMEOUT_MULTIPLIER: float
datetime: module
datetime_helpers: module
general_helpers: module
six: module
unicode_literals: __future__._Feature

_TExponentialTimeout = TypeVar('_TExponentialTimeout', bound=ExponentialTimeout)

class ConstantTimeout:
    __doc__: str
    _timeout: Any
    def __call__(self, func) -> Callable: ...
    def __init__(self, timeout = ...) -> None: ...
    def __str__(self) -> str: ...

class ExponentialTimeout:
    __doc__: str
    _deadline: Any
    _initial: Any
    _maximum: Any
    _multiplier: Any
    def __call__(self, func) -> Callable: ...
    def __init__(self, initial = ..., maximum = ..., multiplier = ..., deadline = ...) -> None: ...
    def __str__(self) -> str: ...
    def with_deadline(self: _TExponentialTimeout, deadline) -> _TExponentialTimeout: ...

def _exponential_timeout_generator(initial, maximum, multiplier, deadline) -> generator: ...
