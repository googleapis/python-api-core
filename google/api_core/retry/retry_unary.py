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
import sys
import time
import inspect
import warnings
from typing import Any, Callable, TypeVar, TYPE_CHECKING

from google.api_core import datetime_helpers
from google.api_core import exceptions

from google.api_core.retry.retry_base import _BaseRetry
from google.api_core.retry.retry_base import _LOGGER
from google.api_core.retry import exponential_sleep_generator


if TYPE_CHECKING:
    if sys.version_info >= (3, 10):
        from typing import ParamSpec
    else:
        from typing_extensions import ParamSpec

    _P = ParamSpec("_P")  # target function call parameters
    _R = TypeVar("_R")  # target function returned value

_ASYNC_RETRY_WARNING = "Using the synchronous google.api_core.retry.Retry with asynchronous calls may lead to unexpected results. Please use google.api_core.retry_async.AsyncRetry instead."


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
        timeout (Optional[float]): How long to keep retrying the target.
        on_error (Optional[Callable[Exception]]): If given, the on_error
            callback will be called with each retryable exception raised by the
            target. Any error raised by this function will *not* be caught.
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
            result = target()
            if inspect.isawaitable(result):
                warnings.warn(_ASYNC_RETRY_WARNING)
            return result

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


class Retry(_BaseRetry):
    """Exponential retry decorator for unary synchronous RPCs.

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
    status of an operation. In other words: we will poll a long-running operation until
    the operation is done or the polling timeout expires. Each poll will inform us of
    the status of the operation. The poll consists of an RPC to the server that may
    itself be retried as per the poll-specific retry settings in case of errors. The
    operation-level retry settings do NOT apply to polling-RPC retries.

    With the actual timeout types being defined above, the client libraries
    often refer to just Timeout without clarifying which type specifically
    that is. In that case the actual timeout type (sometimes also referred to as
    Logical Timeout) can be determined from the context. If it is a unary rpc
    call (i.e. a regular one) Timeout usually stands for the RPC Timeout (if
    provided directly as a standalone value) or Retry Timeout (if provided as
    ``retry.timeout`` property of the unary RPC's retry config). For
    ``Operation`` or ``PollingFuture`` in general Timeout stands for
    Polling Timeout.

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
        deadline (float): DEPRECATED: use `timeout` instead. For backward
            compatibility, if specified it will override the ``timeout`` parameter.
    """

    def __call__(
        self,
        func: Callable[_P, _R],
        on_error: Callable[[Exception], Any] | None = None,
    ) -> Callable[_P, _R]:
        """Wrap a callable with retry behavior.

        Args:
            func (Callable): The callable to add retry behavior to.
            on_error (Optional[Callable[Exception]]): If given, the
                on_error callback will be called with each retryable exception
                raised by the wrapped function. Any error raised by this
                function will *not* be caught. If on_error was specified in the
                constructor, this value will be ignored.

        Returns:
            Callable: A callable that will invoke ``func`` with retry
                behavior.
        """
        if self._on_error is not None:
            on_error = self._on_error

        @functools.wraps(func)
        def retry_wrapped_func(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            """A wrapper that calls target function with retry."""
            target = functools.partial(func, *args, **kwargs)
            sleep_generator = exponential_sleep_generator(
                self._initial, self._maximum, multiplier=self._multiplier
            )
            return retry_target(
                target,
                self._predicate,
                sleep_generator,
                timeout=self._timeout,
                on_error=on_error,
            )

        return retry_wrapped_func
