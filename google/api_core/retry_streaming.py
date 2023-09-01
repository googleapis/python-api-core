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
``Retry(is_stream=True)``.

When ``is_stream=False``, the target is treated as a callable,
and will retry when the callable returns an error. When ``is_stream=True``,
the target will be treated as a callable that returns an iterable. Instead
of just wrapping the initial call in retry logic, the entire iterable is
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

    ```
    def attempt_with_modified_request(target, request, seen_items=[]):
        # remove seen items from request on each attempt
        new_request = modify_request(request, seen_items)
        new_generator = target(new_request)
        for item in new_generator:
            yield item
            seen_items.append(item)

    retry_wrapped_fn = Retry(is_stream=True)(attempt_with_modified_request)
    retryable_generator = retry_wrapped_fn(target, request)
    ```

2. Wrap the retry generator
    Alternatively, you can wrap the retryable generator itself before
    passing it to the end-user to add a filter on the stream. For
    example, you can keep track of the items that were successfully yielded
    in previous retry attempts, and only yield new items when the
    new attempt surpasses the previous ones:

    ``
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
    ```
"""

from typing import (
    Callable,
    Optional,
    List,
    Tuple,
    Iterable,
    Generator,
    TypeVar,
    Any,
    cast,
)

import logging
import time
from functools import partial

from google.api_core import exceptions

_Y = TypeVar("_Y")  # yielded values

_LOGGER = logging.getLogger(__name__)


def _build_retry_error(
    exc_list: List[Exception], is_timeout: bool, timeout_val: float
) -> Tuple[Exception, Optional[Exception]]:
    """
    Default exception_factory implementation. Builds an exception after the retry fails

    Args:
      - exc_list (list[Exception]): list of exceptions that occurred during the retry
      - is_timeout (bool): whether the failure is due to the timeout value being exceeded,
          or due to a non-retryable exception
      - timeout_val (float): the original timeout value for the retry, for use in the exception message

    Returns:
      - tuple[Exception, Exception|None]: a tuple of the exception to be raised, and the cause exception if any
    """
    if is_timeout:
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


def retry_target_stream(
    target: Callable[[], Iterable[_Y]],
    predicate: Callable[[Exception], bool],
    sleep_generator: Iterable[float],
    timeout: Optional[float] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    exception_factory: Optional[
        Callable[[List[Exception], bool, float], Tuple[Exception, Optional[Exception]]]
    ] = None,
    **kwargs,
) -> Generator[_Y, Any, None]:
    """Create a generator wrapper that retries the wrapped stream if it fails.

    This is the lowest-level retry helper. Generally, you'll use the
    higher-level retry helper :class:`Retry`.

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
        on_error: A function to call while processing a
            retryable exception.  Any error raised by this function will *not*
            be caught.
        exception_factory: A function that is called when the retryable reaches
            a terminal failure state, used to construct an exception to be raised.
            It it given a list of all exceptions encountered, a boolean indicating
            whether the failure was due to a timeout, and the original timeout value
            as arguments. It should return a tuple of the exception to be raised,
            along with the cause exception if any.
            If not provided, a default implementation will raise a RetryError
            on timeout, or the last exception encountered otherwise.

    Returns:
        Generator: A retryable generator that wraps the target generator function.

    Raises:
        ValueError: If the sleep generator stops yielding values.
        Exception: a custom exception specified by the exception_factory if provided.
            If no exception_factory is provided:
                google.api_core.RetryError: If the deadline is exceeded while retrying.
                Exception: If the target raises an error that isn't retryable.
    """

    timeout = kwargs.get("deadline", timeout)
    deadline: Optional[float] = time.monotonic() + timeout if timeout else None
    error_list: List[Exception] = []
    exc_factory = partial(exception_factory or _build_retry_error, timeout_val=timeout)

    for sleep in sleep_generator:
        # Start a new retry loop
        try:
            # create and yield from a new instance of the generator from input generator function
            subgenerator = target()
            return (yield from subgenerator)
        # handle exceptions raised by the subgenerator
        # pylint: disable=broad-except
        # This function explicitly must deal with broad exceptions.
        except Exception as exc:
            error_list.append(exc)
            if not predicate(exc):
                final_exc, source_exc = exc_factory(
                    exc_list=error_list, is_timeout=False
                )
                raise final_exc from source_exc
            if on_error is not None:
                on_error(exc)
        finally:
            if subgenerator is not None and getattr(subgenerator, "close", None):
                cast(Generator, subgenerator).close()

        if deadline is not None and time.monotonic() + sleep > deadline:
            final_exc, source_exc = exc_factory(exc_list=error_list, is_timeout=True)
            raise final_exc from source_exc
        _LOGGER.debug(
            "Retrying due to {}, sleeping {:.1f}s ...".format(error_list[-1], sleep)
        )
        time.sleep(sleep)

    raise ValueError("Sleep generator stopped yielding sleep values.")
