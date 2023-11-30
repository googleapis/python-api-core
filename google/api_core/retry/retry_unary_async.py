# Copyright 2020 Google LLC
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

"""Helpers for retrying coroutine functions with exponential back-off.

The :class:`AsyncRetry` decorator shares most functionality and behavior with
:class:`Retry`, but supports coroutine functions. Please refer to description
of :class:`Retry` for more details.

By default, this decorator will retry transient
API errors (see :func:`if_transient_error`). For example:

.. code-block:: python

    @retry_async.AsyncRetry()
    async def call_flaky_rpc():
        return await client.flaky_rpc()

    # Will retry flaky_rpc() if it raises transient API errors.
    result = await call_flaky_rpc()

You can pass a custom predicate to retry on different exceptions, such as
waiting for an eventually consistent item to be available:

.. code-block:: python

    @retry_async.AsyncRetry(predicate=retry_async.if_exception_type(exceptions.NotFound))
    async def check_if_exists():
        return await client.does_thing_exist()

    is_available = await check_if_exists()

Some client library methods apply retry automatically. These methods can accept
a ``retry`` parameter that allows you to configure the behavior:

.. code-block:: python

    my_retry = retry_async.AsyncRetry(deadline=60)
    result = await client.some_method(retry=my_retry)

"""

from __future__ import annotations

import asyncio
import datetime
import functools
import logging
from typing import (
    Awaitable,
    Any,
    Callable,
    TypeVar,
    TYPE_CHECKING,
)

from google.api_core import datetime_helpers
from google.api_core import exceptions
from google.api_core.retry.retry_base import _BaseRetry
from google.api_core.retry.retry_base import _LOGGER
from google.api_core.retry import exponential_sleep_generator

# for backwards compatibility, expose helpers in this module
from google.api_core.retry.retry_base import if_exception_type  # noqa

if TYPE_CHECKING:
    import sys

    if sys.version_info >= (3, 10):
        from typing import ParamSpec
    else:
        from typing_extensions import ParamSpec

    _P = ParamSpec("_P")  # target function call parameters
    _R = TypeVar("_R")  # target function returned value

_DEFAULT_INITIAL_DELAY = 1.0  # seconds
_DEFAULT_MAXIMUM_DELAY = 60.0  # seconds
_DEFAULT_DELAY_MULTIPLIER = 2.0
_DEFAULT_DEADLINE = 60.0 * 2.0  # seconds
_DEFAULT_TIMEOUT = 60.0 * 2.0  # seconds


async def retry_target(
    target, predicate, sleep_generator, timeout=None, on_error=None, **kwargs
):
    """Await a coroutine and retry if it fails.

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
        timeout (Optional[float]): How long to keep retrying the target, in seconds.
        on_error (Optional[Callable[Exception]]): If given, the on_error
            callback will be called with each retryable exception raised by the
            target. Any error raised by this function will *not* be caught.
        deadline (float): DEPRECATED use ``timeout`` instead. For backward
        compatibility, if set it will override the ``timeout`` parameter.

    Returns:
        Any: the return value of the target function.

    Raises:
        google.api_core.RetryError: If the deadline is exceeded while retrying.
        ValueError: If the sleep generator stops yielding values.
        Exception: If the target raises a method that isn't retryable.
    """

    timeout = kwargs.get("deadline", timeout)

    deadline_dt = (
        (datetime_helpers.utcnow() + datetime.timedelta(seconds=timeout))
        if timeout
        else None
    )

    last_exc = None

    for sleep in sleep_generator:
        try:
            if not deadline_dt:
                return await target()
            else:
                return await asyncio.wait_for(
                    target(),
                    timeout=(deadline_dt - datetime_helpers.utcnow()).total_seconds(),
                )
        # pylint: disable=broad-except
        # This function explicitly must deal with broad exceptions.
        except Exception as exc:
            if not predicate(exc) and not isinstance(exc, asyncio.TimeoutError):
                raise
            last_exc = exc
            if on_error is not None:
                on_error(exc)

        now = datetime_helpers.utcnow()

        if deadline_dt:
            if deadline_dt <= now:
                # Chains the raising RetryError with the root cause error,
                # which helps observability and debugability.
                raise exceptions.RetryError(
                    "Timeout of {:.1f}s exceeded while calling target function".format(
                        timeout
                    ),
                    last_exc,
                ) from last_exc
            else:
                time_to_deadline = (deadline_dt - now).total_seconds()
                sleep = min(time_to_deadline, sleep)

        _LOGGER.debug(
            "Retrying due to {}, sleeping {:.1f}s ...".format(last_exc, sleep)
        )
        await asyncio.sleep(sleep)

    raise ValueError("Sleep generator stopped yielding sleep values.")


class AsyncRetry(_BaseRetry):
    """Exponential retry decorator for async coroutines.

    This class is a decorator used to add exponential back-off retry behavior
    to an RPC call.

    Although the default behavior is to retry transient API errors, a
    different predicate can be provided to retry other exceptions.

    Args:
        predicate (Callable[Exception]): A callable that should return ``True``
            if the given exception is retryable.
        initial (float): The minimum a,out of time to delay in seconds. This
            must be greater than 0.
        maximum (float): The maximum amount of time to delay in seconds.
        multiplier (float): The multiplier applied to the delay.
        timeout (Optional[float]): How long to keep retrying in seconds.
        on_error (Optional[Callable[Exception]]): A function to call while processing
            a retryable exception. Any error raised by this function will
            *not* be caught.
        deadline (float): DEPRECATED use ``timeout`` instead. If set it will
        override ``timeout`` parameter.
    """

    def __call__(
        self,
        func: Callable[..., Awaitable[_R]],
        on_error: Callable[[Exception], Any] | None = None,
    ) -> Callable[_P, Awaitable[_R]]:
        """Wrap a callable with retry behavior.

        Args:
            func (Callable): The callable or stream to add retry behavior to.
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
        async def retry_wrapped_func(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            """A wrapper that calls target function with retry."""
            sleep_generator = exponential_sleep_generator(
                self._initial, self._maximum, multiplier=self._multiplier
            )
            return await retry_target(
                functools.partial(func, *args, **kwargs),
                predicate=self._predicate,
                sleep_generator=sleep_generator,
                timeout=self._timeout,
                on_error=on_error,
            )

        return retry_wrapped_func
