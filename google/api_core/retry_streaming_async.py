# Copyright 2023 Google LLC
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

"""
Generator wrapper for retryable streaming RPCs.
This function will be used when initilizing a retry with
``AsyncRetry(is_stream=True)``.
"""

from typing import (
    cast,
    Callable,
    Optional,
    Iterable,
    List,
    Tuple,
    AsyncIterator,
    AsyncIterable,
    Awaitable,
    Union,
    TypeVar,
    AsyncGenerator,
    TYPE_CHECKING,
)

import asyncio
import logging
import time
import sys
from functools import partial

from google.api_core.retry import _build_retry_error
from google.api_core.retry import RetryFailureReason

if TYPE_CHECKING:
    _Y = TypeVar("_Y")  # yielded values

_LOGGER = logging.getLogger(__name__)


async def retry_target_stream(
    target: Union[
        Callable[[], AsyncIterable["_Y"]],
        Callable[[], Awaitable[AsyncIterable["_Y"]]],
    ],
    predicate: Callable[[Exception], bool],
    sleep_generator: Iterable[float],
    timeout: Optional[float] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    exception_factory: Optional[
        Callable[[List[Exception], bool, float], Tuple[Exception, Optional[Exception]]]
    ] = None,
    **kwargs,
) -> AsyncGenerator["_Y", None]:
    """Create a generator wrapper that retries the wrapped stream if it fails.

    This is the lowest-level retry helper. Generally, you'll use the
    higher-level retry helper :class:`AsyncRetry`.

    Args:
        target: The generator function to call and retry. This must be a
            nullary function - apply arguments with `functools.partial`.
        predicate: A callable used to determine if an
            exception raised by the target should be considered retryable.
            It should return True to retry or False otherwise.
        sleep_generator: An infinite iterator that determines
            how long to sleep between retries.
        timeout: How long to keep retrying the target.
            Note: timeout is only checked before initiating a retry, so the target may
            run past the timeout value as long as it is healthy.
        on_error: If given, the on_error callback will be called with each
            retryable exception raised by the target. Any error raised by this
            function will *not* be caught.
        exception_factory: A function that is called when the retryable reaches
            a terminal failure state, used to construct an exception to be raised.
            It it given a list of all exceptions encountered, a boolean indicating
            whether the failure was due to a timeout, and the original timeout value
            as arguments. It should return a tuple of the exception to be raised,
            along with the cause exception if any.
            If not provided, a default implementation will raise a RetryError
            on timeout, or the last exception encountered otherwise.

    Returns:
        AsyncGenerator: A retryable generator that wraps the target generator function.

    Raises:
        ValueError: If the sleep generator stops yielding values.
        Exception: a custom exception specified by the exception_factory if provided.
            If no exception_factory is provided:
                google.api_core.RetryError: If the deadline is exceeded while retrying.
                Exception: If the target raises an error that isn't retryable.
    """

    async_iterator: Optional[AsyncIterator[_Y]] = None
    timeout = kwargs.get("deadline", timeout)
    deadline: Optional[float] = time.monotonic() + timeout if timeout else None
    # keep track of retryable exceptions we encounter to pass in to exception_factory
    error_list: List[Exception] = []
    # override exception_factory to build a more complex exception
    exc_factory = partial(exception_factory or _build_retry_error, timeout_val=timeout)
    target_is_generator: Optional[bool] = None

    for sleep in sleep_generator:
        # Start a new retry loop
        try:
            target_output: Union[
                AsyncIterable[_Y], Awaitable[AsyncIterable[_Y]]
            ] = target()
            try:
                # gapic functions return the generator behind an awaitable
                # unwrap the awaitable so we can work with the generator directly
                target_output = await target_output  # type: ignore
            except TypeError:
                # was not awaitable, continue
                pass
            async_iterator = cast(AsyncIterable["_Y"], target_output).__aiter__()

            if target_is_generator is None:
                # Check if target supports generator features (asend, athrow, aclose)
                target_is_generator = bool(getattr(async_iterator, "asend", None))

            sent_in = None
            while True:
                ## Read from async_iterator
                # If the target is a generator, we will advance it with `asend`
                # otherwise, we will use `anext`
                if target_is_generator:
                    next_value = await async_iterator.asend(sent_in)  # type: ignore
                else:
                    next_value = await async_iterator.__anext__()
                ## Yield from Wrapper to caller
                try:
                    # yield latest value from target
                    # exceptions from `athrow` and `aclose` are injected here
                    sent_in = yield next_value
                except GeneratorExit:
                    # if wrapper received `aclose` while waiting on yield,
                    # it will raise GeneratorExit here
                    if target_is_generator:
                        # pass to inner async_iterator for handling
                        await cast(AsyncGenerator["_Y", None], async_iterator).aclose()
                    else:
                        raise
                    return
                except:  # noqa: E722
                    # bare except catches any exception passed to `athrow`
                    if target_is_generator:
                        # delegate error handling to async_iterator
                        await cast(AsyncGenerator["_Y", None], async_iterator).athrow(
                            *sys.exc_info()
                        )
                    else:
                        raise
            return
        except StopAsyncIteration:
            # if iterator exhausted, return
            return
        # handle exceptions raised by the async_iterator
        # pylint: disable=broad-except
        # This function explicitly must deal with broad exceptions.
        except (Exception, asyncio.CancelledError) as exc:
            error_list.append(exc)
            if not predicate(exc):
                exc, source_exc = exc_factory(
                    exc_list=error_list, reason=RetryFailureReason.NON_RETRYABLE_ERROR
                )
                raise exc from source_exc
            if on_error is not None:
                on_error(exc)
        finally:
            if target_is_generator and async_iterator is not None:
                await cast(AsyncGenerator["_Y", None], async_iterator).aclose()

        # sleep and adjust timeout budget
        if deadline is not None and time.monotonic() + sleep > deadline:
            final_exc, source_exc = exc_factory(
                exc_list=error_list, reason=RetryFailureReason.TIMEOUT
            )
            raise final_exc from source_exc
        _LOGGER.debug(
            "Retrying due to {}, sleeping {:.1f}s ...".format(error_list[-1], sleep)
        )
        await asyncio.sleep(sleep)
    raise ValueError("Sleep generator stopped yielding sleep values.")
