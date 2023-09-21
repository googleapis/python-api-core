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

"""Helpers for retrying functions with exponential back-off.

The :class:`Retry` decorator can be used to retry functions that raise
exceptions using exponential backoff. Because a exponential sleep algorithm is
used, the retry is limited by a `deadline`. The deadline is the maximum amount
of time a method can block. This is used instead of total number of retries
because it is difficult to ascertain the amount of time a function can block
when using total number of retries and exponential backoff.

By default, this decorator will retry transient
API errors (see :func:`if_transient_error`). For example:

.. code-block:: python

    @retry.Retry()
    def call_flaky_rpc():
        return client.flaky_rpc()

    # Will retry flaky_rpc() if it raises transient API errors.
    result = call_flaky_rpc()

You can pass a custom predicate to retry on different exceptions, such as
waiting for an eventually consistent item to be available:

.. code-block:: python

    @retry.Retry(predicate=if_exception_type(exceptions.NotFound))
    def check_if_exists():
        return client.does_thing_exist()

    is_available = check_if_exists()

Some client library methods apply retry automatically. These methods can accept
a ``retry`` parameter that allows you to configure the behavior:

.. code-block:: python

    my_retry = retry.Retry(deadline=60)
    result = client.some_method(retry=my_retry)

"""

from __future__ import annotations

import datetime
import functools
import logging
import random
import sys
import time
from enum import Enum
from typing import Any, Callable, TypeVar, Generator, Iterable, cast, TYPE_CHECKING

import requests.exceptions

from google.api_core import datetime_helpers
from google.api_core import exceptions
import google.api_core.retry_streaming as retry_streaming
from google.auth import exceptions as auth_exceptions

if TYPE_CHECKING:
    if sys.version_info >= (3, 10):
        from typing import ParamSpec
    else:
        from typing_extensions import ParamSpec

    _P = ParamSpec("_P")  # target function call parameters
    _R = TypeVar("_R")  # target function returned value
    _Y = TypeVar("_Y")  # target stream yielded values

_LOGGER = logging.getLogger(__name__)
_DEFAULT_INITIAL_DELAY = 1.0  # seconds
_DEFAULT_MAXIMUM_DELAY = 60.0  # seconds
_DEFAULT_DELAY_MULTIPLIER = 2.0
_DEFAULT_DEADLINE = 60.0 * 2.0  # seconds


class RetryFailureReason(Enum):
    """
    The cause of a failed retry, used when building exceptions
    """

    TIMEOUT = "TIMEOUT"
    NON_RETRYABLE_ERROR = "NON_RETRYABLE_ERROR"


def _build_retry_error(
    exc_list: list[Exception],
    reason: RetryFailureReason,
    timeout_val: float,
    **kwargs: Any,
) -> tuple[Exception, Exception | None]:
    """
    Default exception_factory implementation. Builds an exception after the retry fails

    Args:
      - exc_list (list[Exception]): list of exceptions that occurred during the retry
      - reason (google.api_core.retry.RetryFailureReason): reason for the retry failure.
            Can be TIMEOUT or NON_RETRYABLE_ERROR
      - timeout_val (float): the original timeout value for the retry, for use in the exception message

    Returns:
      - tuple[Exception, Exception|None]: a tuple of the exception to be raised, and the cause exception if any
    """
    if reason == RetryFailureReason.TIMEOUT:
        # return RetryError with the most recent exception as the cause
        src_exc = exc_list[-1] if exc_list else None
        return (
            exceptions.RetryError(
                "Timeout of {:.1f}s exceeded".format(timeout_val),
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


def if_exception_type(
    *exception_types: type[BaseException],
) -> Callable[[BaseException], bool]:
    """Creates a predicate to check if the exception is of a given type.

    Args:
        exception_types (Sequence[:func:`type`]): The exception types to check
            for.

    Returns:
        Callable[Exception]: A predicate that returns True if the provided
            exception is of the given type(s).
    """

    def if_exception_type_predicate(exception: BaseException) -> bool:
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


def retry_target(
    target, predicate, sleep_generator, timeout=None, on_error=None, **kwargs
):
    """Call a function and retry if it fails.

    This is the lowest-level retry helper. Generally, you'll use the
    higher-level retry helper :class:`Retry`.

    Args:
        target(Callable[[], Any]): The function to call and retry. This must be a
            nullary function - apply arguments with `functools.partial`.
        predicate (Callable[Exception]): A callable used to determine if an
            exception raised by the target should be considered retryable.
            It should return True to retry or False otherwise.
        sleep_generator (Iterable[float]): An infinite iterator that determines
            how long to sleep between retries.
        timeout (float): How long to keep retrying the target.
        on_error (Callable[Exception]): A function to call while processing a
            retryable exception.  Any error raised by this function will *not*
            be caught.
        deadline (float): DEPRECATED: use ``timeout`` instead. For backward
            compatibility, if specified it will override ``timeout`` parameter.

    Returns:
        Any: the return value of the target function.

    Raises:
        google.api_core.RetryError: If the deadline is exceeded while retrying.
        ValueError: If the sleep generator stops yielding values.
        Exception: If the target raises a method that isn't retryable.
    """

    timeout = kwargs.get("deadline", timeout)

    if timeout is not None:
        deadline = datetime_helpers.utcnow() + datetime.timedelta(seconds=timeout)
    else:
        deadline = None

    last_exc = None

    for sleep in sleep_generator:
        try:
            return target()

        # pylint: disable=broad-except
        # This function explicitly must deal with broad exceptions.
        except Exception as exc:
            if not predicate(exc):
                raise
            last_exc = exc
            if on_error is not None:
                on_error(exc)

        if deadline is not None:
            next_attempt_time = datetime_helpers.utcnow() + datetime.timedelta(
                seconds=sleep
            )
            if deadline < next_attempt_time:
                raise exceptions.RetryError(
                    "Deadline of {:.1f}s exceeded while calling target function".format(
                        timeout
                    ),
                    last_exc,
                ) from last_exc

        _LOGGER.debug(
            "Retrying due to {}, sleeping {:.1f}s ...".format(last_exc, sleep)
        )
        time.sleep(sleep)

    raise ValueError("Sleep generator stopped yielding sleep values.")


class Retry(object):
    """Exponential retry decorator.

    This class is a decorator used to add retry or polling behavior to an RPC
    call.

    Although the default behavior is to retry transient API errors, a
    different predicate can be provided to retry other exceptions.

    There two important concepts that retry/polling behavior may operate on,
    Deadline and Timeout, which need to be properly defined for the correct
    usage of this class and the rest of the library.

    Deadline: a fixed point in time by which a certain operation must
    terminate. For example, if a certain operation has a deadline
    "2022-10-18T23:30:52.123Z" it must terminate (successfully or with an
    error) by that time, regardless of when it was started or whether it
    was started at all.

    Timeout: the maximum duration of time after which a certain operation
    must terminate (successfully or with an error). The countdown begins right
    after an operation was started. For example, if an operation was started at
    09:24:00 with timeout of 75 seconds, it must terminate no later than
    09:25:15.

    Unfortunately, in the past this class (and the api-core library as a whole) has not been
    properly distinguishing the concepts of "timeout" and "deadline", and the
    ``deadline`` parameter has meant ``timeout``. That is why
    ``deadline`` has been deprecated and ``timeout`` should be used instead. If the
    ``deadline`` parameter is set, it will override the ``timeout`` parameter. In other words,
    ``retry.deadline`` should be treated as just a deprecated alias for
    ``retry.timeout``.

    Said another way, it is safe to assume that this class and the rest of this
    library operate in terms of timeouts (not deadlines) unless explicitly
    noted the usage of deadline semantics.

    It is also important to
    understand the three most common applications of the Timeout concept in the
    context of this library.

    Usually the generic Timeout term may stand for one of the following actual
    timeouts: RPC Timeout, Retry Timeout, or Polling Timeout.

    RPC Timeout: a value supplied by the client to the server so
    that the server side knows the maximum amount of time it is expected to
    spend handling that specific RPC. For example, in the case of gRPC transport,
    RPC Timeout is represented by setting "grpc-timeout" header in the HTTP2
    request. The `timeout` property of this class normally never represents the
    RPC Timeout as it is handled separately by the ``google.api_core.timeout``
    module of this library.

    Retry Timeout: this is the most common meaning of the ``timeout`` property
    of this class, and defines how long a certain RPC may be retried in case
    the server returns an error.

    Polling Timeout: defines how long the
    client side is allowed to call the polling RPC repeatedly to check a status of a
    long-running operation. Each polling RPC is
    expected to succeed (its errors are supposed to be handled by the retry
    logic). The decision as to whether a new polling attempt needs to be made is based
    not on the RPC status code but  on the status of the returned
    status of an operation. In other words: we will poll a long-running operation until the operation is done or the polling timeout expires. Each poll will inform us of the status of the operation. The poll consists of an RPC to the server that may itself be retried as per the poll-specific retry settings in case of errors. The operation-level retry settings do NOT apply to polling-RPC retries.

    With the actual timeout types being defined above, the client libraries
    often refer to just Timeout without clarifying which type specifically
    that is. In that case the actual timeout type (sometimes also referred to as
    Logical Timeout) can be determined from the context. If it is a unary rpc
    call (i.e. a regular one) Timeout usually stands for the RPC Timeout (if
    provided directly as a standalone value) or Retry Timeout (if provided as
    ``retry.timeout`` property of the unary RPC's retry config). For
    ``Operation`` or ``PollingFuture`` in general Timeout stands for
    Polling Timeout.

    When ``is_stream=False``, the target is treated as a callable,
    and will retry when the callable returns an error. When ``is_stream=True``,
    the target will be treated as a generator function. Instead of just wrapping
    the initial call in retry logic, the entire output iterable is
    wrapped, with each yield passing through the retryable generator. If any yield
    in the stream raises a retryable exception, the entire stream will be
    retried.

    NOTE: when a stream encounters a retryable error, it will
    silently construct a fresh iterator instance in the background
    and continue yielding (likely duplicate) values as if no error occurred.
    This is the most general way to retry a stream, but it often is not the
    desired behavior. Example: iter([1, 2, 1/0]) -> [1, 2, 1, 2, ...]

    There are two ways to build more advanced retry logic for streams:

    1. Wrap the target
        Use a ``target`` that maintains state between retries, and creates a
        different generator on each retry call. For example, you can wrap a
        network call in a function that modifies the request based on what has
        already been returned:

        .. code-block:: python

            def attempt_with_modified_request(target, request, seen_items=[]):
                # remove seen items from request on each attempt
                new_request = modify_request(request, seen_items)
                new_generator = target(new_request)
                for item in new_generator:
                    yield item
                    seen_items.append(item)

            retry_wrapped_fn = Retry(is_stream=True)(attempt_with_modified_request)
            retryable_generator = retry_wrapped_fn(target, request)

    2. Wrap the retry generator
        Alternatively, you can wrap the retryable generator itself before
        passing it to the end-user to add a filter on the stream. For
        example, you can keep track of the items that were successfully yielded
        in previous retry attempts, and only yield new items when the
        new attempt surpasses the previous ones:

        .. code-block:: python

            def retryable_with_filter(target):
                stream_idx = 0
                # reset stream_idx when the stream is retried
                def on_error(e):
                    nonlocal stream_idx
                    stream_idx = 0
                # build retryable
                retryable_gen = Retry(is_stream=True, on_error=on_error, ...)(target)
                # keep track of what has been yielded out of filter
                yielded_items = []
                for item in retryable_gen():
                    if stream_idx >= len(yielded_items):
                        yielded_items.append(item)
                        yield item
                    elif item != yielded_items[stream_idx]:
                        raise ValueError("Stream differs from last attempt")
                    stream_idx += 1

            filter_retry_wrapped = retryable_with_filter(target)

    Args:
        predicate (Callable[Exception]): A callable that should return ``True``
            if the given exception is retryable.
        initial (float): The minimum amount of time to delay in seconds. This
            must be greater than 0.
        maximum (float): The maximum amount of time to delay in seconds.
        multiplier (float): The multiplier applied to the delay.
        timeout (float): How long to keep retrying, in seconds.
        on_error (Callable[Exception]): A function to call while processing
            a retryable exception. Any error raised by this function will
            *not* be caught.
        is_stream (bool): Indicates whether the input function
            should be treated as an stream function (i.e. a Generator,
            or function that returns an Iterable). If True, the iterable
            will be wrapped with retry logic, and any failed outputs will
            restart the stream. If False, only the input function call itself
            will be retried. Defaults to False.
            To avoid duplicate values, retryable streams should typically be
            wrapped in additional filter logic before use. For more details, see
            ``google.api_core.retry_streaming.retry_target_stream``.
        deadline (float): DEPRECATED: use `timeout` instead. For backward
            compatibility, if specified it will override the ``timeout`` parameter.
    """

    def __init__(
        self,
        predicate: Callable[[BaseException], bool] = if_transient_error,
        initial: float = _DEFAULT_INITIAL_DELAY,
        maximum: float = _DEFAULT_MAXIMUM_DELAY,
        multiplier: float = _DEFAULT_DELAY_MULTIPLIER,
        timeout: float = _DEFAULT_DEADLINE,
        on_error: Callable[[BaseException], Any] | None = None,
        is_stream: bool = False,
        **kwargs: Any,
    ) -> None:
        self._predicate = predicate
        self._initial = initial
        self._multiplier = multiplier
        self._maximum = maximum
        self._timeout = kwargs.get("deadline", timeout)
        self._deadline = self._timeout
        self._on_error = on_error
        self._is_stream = is_stream

    def __call__(
        self,
        func: Callable[_P, _R | Iterable[_Y]],
        on_error: Callable[[BaseException], Any] | None = None,
    ) -> Callable[_P, _R | Generator[_Y, Any, None]]:
        """Wrap a callable with retry behavior.

        Args:
            func (Callable): The callable to add retry behavior to.
            on_error (Callable[Exception]): A function to call while processing
                a retryable exception. Any error raised by this function will
                *not* be caught.
                If on_error was specified in the constructor, this value will
                be ignored.

        Returns:
            Callable: A callable that will invoke ``func`` with retry
                behavior.
        """
        if self._on_error is not None:
            on_error = self._on_error

        @functools.wraps(func)
        def retry_wrapped_func(
            *args: _P.args, **kwargs: _P.kwargs
        ) -> _R | Generator[_Y, Any, None]:
            """A wrapper that calls target function with retry."""
            target = functools.partial(func, *args, **kwargs)
            sleep_generator = exponential_sleep_generator(
                self._initial, self._maximum, multiplier=self._multiplier
            )
            retry_args = (self._predicate, sleep_generator, self._timeout, on_error)
            if self._is_stream:
                # when stream is enabled, assume target returns an iterable that yields _Y
                stream_target = cast(Callable[[], Iterable["_Y"]], target)
                return retry_streaming.retry_target_stream(stream_target, *retry_args)
            else:
                return retry_target(target, *retry_args)

        return retry_wrapped_func

    @property
    def deadline(self):
        """
        DEPRECATED: use ``timeout`` instead.  Refer to the ``Retry`` class
        documentation for details.
        """
        return self._timeout

    @property
    def timeout(self):
        return self._timeout

    def with_deadline(self, deadline):
        """Return a copy of this retry with the given timeout.

        DEPRECATED: use :meth:`with_timeout` instead. Refer to the ``Retry`` class
        documentation for details.

        Args:
            deadline (float): How long to keep retrying in seconds.

        Returns:
            Retry: A new retry instance with the given timeout.
        """
        return self.with_timeout(timeout=deadline)

    def with_timeout(self, timeout):
        """Return a copy of this retry with the given timeout.

        Args:
            timeout (float): How long to keep retrying, in seconds.

        Returns:
            Retry: A new retry instance with the given timeout.
        """
        return Retry(
            predicate=self._predicate,
            initial=self._initial,
            maximum=self._maximum,
            multiplier=self._multiplier,
            timeout=timeout,
            on_error=self._on_error,
        )

    def with_predicate(self, predicate):
        """Return a copy of this retry with the given predicate.

        Args:
            predicate (Callable[Exception]): A callable that should return
                ``True`` if the given exception is retryable.

        Returns:
            Retry: A new retry instance with the given predicate.
        """
        return Retry(
            predicate=predicate,
            initial=self._initial,
            maximum=self._maximum,
            multiplier=self._multiplier,
            timeout=self._timeout,
            on_error=self._on_error,
        )

    def with_delay(self, initial=None, maximum=None, multiplier=None):
        """Return a copy of this retry with the given delay options.

        Args:
            initial (float): The minimum amount of time to delay. This must
                be greater than 0.
            maximum (float): The maximum amount of time to delay.
            multiplier (float): The multiplier applied to the delay.

        Returns:
            Retry: A new retry instance with the given predicate.
        """
        return Retry(
            predicate=self._predicate,
            initial=initial if initial is not None else self._initial,
            maximum=maximum if maximum is not None else self._maximum,
            multiplier=multiplier if multiplier is not None else self._multiplier,
            timeout=self._timeout,
            on_error=self._on_error,
        )

    def __str__(self):
        return (
            "<Retry predicate={}, initial={:.1f}, maximum={:.1f}, "
            "multiplier={:.1f}, timeout={}, on_error={}>".format(
                self._predicate,
                self._initial,
                self._maximum,
                self._multiplier,
                self._timeout,  # timeout can be None, thus no {:.1f}
                self._on_error,
            )
        )
