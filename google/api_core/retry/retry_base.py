# Copyright 2017 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared classes and functions for retrying requests.

:class:`_BaseRetry` is the base class for :class:`Retry`,
:class:`AsyncRetry`, :class:`StreamingRetry`, and :class:`AsyncStreamingRetry`.
"""

from __future__ import annotations

import logging
import random
from enum import Enum
from typing import Any, Callable, TYPE_CHECKING

import requests.exceptions

from google.api_core import exceptions
from google.auth import exceptions as auth_exceptions

if TYPE_CHECKING:
    import sys

    if sys.version_info >= (3, 11):
        from typing import Self
    else:
        from typing_extensions import Self

_DEFAULT_INITIAL_DELAY = 1.0  # seconds
_DEFAULT_MAXIMUM_DELAY = 60.0  # seconds
_DEFAULT_DELAY_MULTIPLIER = 2.0
_DEFAULT_DEADLINE = 60.0 * 2.0  # seconds

_LOGGER = logging.getLogger("google.api_core.retry")


def if_exception_type(
    *exception_types: type[Exception],
) -> Callable[[Exception], bool]:
    """Creates a predicate to check if the exception is of a given type.

    Args:
        exception_types (Sequence[:func:`type`]): The exception types to check
            for.

    Returns:
        Callable[Exception]: A predicate that returns True if the provided
            exception is of the given type(s).
    """

    def if_exception_type_predicate(exception: Exception) -> bool:
        """Bound predicate for checking an exception type."""
        return isinstance(exception, exception_types)

    return if_exception_type_predicate


# pylint: disable=invalid-name
# Pylint sees this as a constant, but it is also an alias that should be
# considered a function.
if_transient_error = if_exception_type(
    exceptions.InternalServerError,
    exceptions.TooManyRequests,
    exceptions.ServiceUnavailable,
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
    auth_exceptions.TransportError,
)
"""A predicate that checks if an exception is a transient API error.

The following server errors are considered transient:

- :class:`google.api_core.exceptions.InternalServerError` - HTTP 500, gRPC
    ``INTERNAL(13)`` and its subclasses.
- :class:`google.api_core.exceptions.TooManyRequests` - HTTP 429
- :class:`google.api_core.exceptions.ServiceUnavailable` - HTTP 503
- :class:`requests.exceptions.ConnectionError`
- :class:`requests.exceptions.ChunkedEncodingError` - The server declared
    chunked encoding but sent an invalid chunk.
- :class:`google.auth.exceptions.TransportError` - Used to indicate an
    error occurred during an HTTP request.
"""
# pylint: enable=invalid-name


def exponential_sleep_generator(initial, maximum, multiplier=_DEFAULT_DELAY_MULTIPLIER):
    """Generates sleep intervals based on the exponential back-off algorithm.

    This implements the `Truncated Exponential Back-off`_ algorithm.

    .. _Truncated Exponential Back-off:
        https://cloud.google.com/storage/docs/exponential-backoff

    Args:
        initial (float): The minimum amount of time to delay. This must
            be greater than 0.
        maximum (float): The maximum amount of time to delay.
        multiplier (float): The multiplier applied to the delay.

    Yields:
        float: successive sleep intervals.
    """
    delay = min(initial, maximum)
    while True:
        yield random.uniform(0.0, delay)
        delay = min(delay * multiplier, maximum)


class RetryFailureReason(Enum):
    """
    The cause of a failed retry, used when building exceptions
    """

    TIMEOUT = 0
    NON_RETRYABLE_ERROR = 1


def _build_retry_error(
    exc_list: list[Exception],
    reason: RetryFailureReason,
    timeout_val: float | None,
    **kwargs: Any,
) -> tuple[Exception, Exception | None]:
    """
    Default exception_factory implementation. Builds an exception after the retry fails

    Args:
      - exc_list: list of exceptions that occurred during the retry
      - reason: reason for the retry failure.
            Can be TIMEOUT or NON_RETRYABLE_ERROR
      - timeout_val: the original timeout value for the retry, for use in the exception message

    Returns:
      - tuple: a tuple of the exception to be raised, and the cause exception if any
    """
    if reason == RetryFailureReason.TIMEOUT:
        # return RetryError with the most recent exception as the cause
        src_exc = exc_list[-1] if exc_list else None
        timeout_val_str = f"of {timeout_val:0.1f}s " if timeout_val is not None else ""
        return (
            exceptions.RetryError(
                f"Timeout {timeout_val_str}exceeded",
                src_exc,
            ),
            src_exc,
        )
    elif exc_list:
        # return most recent exception encountered
        return exc_list[-1], None
    else:
        # no exceptions were given in exc_list. Raise generic RetryError
        return exceptions.RetryError("Unknown error", None), None


class _BaseRetry(object):
    """
    Base class for retry configuration objects. This class is intended to capture retry
    and backoff configuration that is common to both synchronous and asynchronous retries,
    for both unary and streaming RPCs. It is not intended to be instantiated directly,
    but rather to be subclassed by the various retry configuration classes.
    """

    def __init__(
        self,
        predicate: Callable[[Exception], bool] = if_transient_error,
        initial: float = _DEFAULT_INITIAL_DELAY,
        maximum: float = _DEFAULT_MAXIMUM_DELAY,
        multiplier: float = _DEFAULT_DELAY_MULTIPLIER,
        timeout: float = _DEFAULT_DEADLINE,
        on_error: Callable[[Exception], Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._predicate = predicate
        self._initial = initial
        self._multiplier = multiplier
        self._maximum = maximum
        self._timeout = kwargs.get("deadline", timeout)
        self._deadline = self._timeout
        self._on_error = on_error

    def __call__(self, *args, **kwargs) -> Any:
        raise NotImplementedError("Not implemented in base class")

    @property
    def deadline(self) -> float | None:
        """
        DEPRECATED: use ``timeout`` instead.  Refer to the ``Retry`` class
        documentation for details.
        """
        return self._timeout

    @property
    def timeout(self) -> float | None:
        return self._timeout

    def _replace(
        self,
        predicate=None,
        initial=None,
        maximum=None,
        multiplier=None,
        timeout=None,
        on_error=None,
    ) -> Self:
        return type(self)(
            predicate=predicate or self._predicate,
            initial=initial or self._initial,
            maximum=maximum or self._maximum,
            multiplier=multiplier or self._multiplier,
            timeout=timeout or self._timeout,
            on_error=on_error or self._on_error,
        )

    def with_deadline(self, deadline) -> Self:
        """Return a copy of this retry with the given timeout.

        DEPRECATED: use :meth:`with_timeout` instead. Refer to the ``Retry`` class
        documentation for details.

        Args:
            deadline (float): How long to keep retrying in seconds.

        Returns:
            Retry: A new retry instance with the given timeout.
        """
        return self._replace(timeout=deadline)

    def with_timeout(self, timeout) -> Self:
        """Return a copy of this retry with the given timeout.

        Args:
            timeout (float): How long to keep retrying, in seconds.

        Returns:
            Retry: A new retry instance with the given timeout.
        """
        return self._replace(timeout=timeout)

    def with_predicate(self, predicate) -> Self:
        """Return a copy of this retry with the given predicate.

        Args:
            predicate (Callable[Exception]): A callable that should return
                ``True`` if the given exception is retryable.

        Returns:
            Retry: A new retry instance with the given predicate.
        """
        return self._replace(predicate=predicate)

    def with_delay(self, initial=None, maximum=None, multiplier=None) -> Self:
        """Return a copy of this retry with the given delay options.

        Args:
            initial (float): The minimum amount of time to delay. This must
                be greater than 0.
            maximum (float): The maximum amount of time to delay.
            multiplier (float): The multiplier applied to the delay.

        Returns:
            Retry: A new retry instance with the given predicate.
        """
        return self._replace(initial=initial, maximum=maximum, multiplier=multiplier)

    def __str__(self) -> str:
        return (
            "<{} predicate={}, initial={:.1f}, maximum={:.1f}, "
            "multiplier={:.1f}, timeout={}, on_error={}>".format(
                type(self).__name__,
                self._predicate,
                self._initial,
                self._maximum,
                self._multiplier,
                self._timeout,  # timeout can be None, thus no {:.1f}
                self._on_error,
            )
        )
