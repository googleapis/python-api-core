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

"""Helpers for retries for streaming APIs."""

from typing import (
    Callable,
    Optional,
    List,
    Tuple,
    Iterable,
    Iterator,
    Generator,
    TypeVar,
    Any,
    Union,
    cast,
)

import logging
import time
from functools import partial

from google.api_core import exceptions

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


def _build_timeout_error(
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
    src_exc = exc_list[-1] if exc_list else None
    if is_timeout:
        return (
            exceptions.RetryError(
                "Timeout of {:.1f}s exceeded".format(timeout_val),
                src_exc,
            ),
            src_exc,
        )
    else:
        return exc_list[-1], None


def retry_target_generator(
    target: Callable[[], Union[Iterable[T], Generator[T, Any, None]]],
    predicate: Callable[[Exception], bool],
    sleep_generator: Iterable[float],
    timeout: Optional[float] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    exception_factory: Optional[
        Callable[[List[Exception], bool, float], Tuple[Exception, Optional[Exception]]]
    ] = None,
    **kwargs,
) -> Generator[T, Any, None]:
    """
    Generator wrapper for retryable streaming RPCs.
    This function will be used when initilizing a retry with
    ``Retry(is_stream=True)``.

    When ``is_stream=False``, the target is treated as a callable,
    and will retry when the callable returns an error. When ``is_stream=True``,
    the target will be treated as a callable that retruns an iterable. Instead
    of just wrapping the initial call in retry logic, the entire iterable is
    wrapped, with each yield passing through the retryable generator. If any yield
    in the stream raises a retryable exception, the entire stream will be
    retried.

    Important Note: when a stream is encounters a retryable error, it will
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

        retry_wrapped = Retry(is_stream=True)(attempt_with_modified_request, target, request, [])
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
                for item in retryable_gen:
                    if stream_idx >= len(yielded_items):
                        yield item
                        yielded_items.append(item)
                    elif item != previous_stream[stream_idx]:
                        raise ValueError("Stream differs from last attempt")"
                    stream_idx += 1

            filter_retry_wrapped = retryable_with_filter(target)
            ```
    """
    timeout = kwargs.get("deadline", timeout)
    deadline: Optional[float] = time.monotonic() + timeout if timeout else None
    error_list: List[Exception] = []
    exc_factory = partial(
        exception_factory or _build_timeout_error, timeout_val=timeout
    )

    for sleep in sleep_generator:
        # Start a new retry loop
        try:
            # create and yeild from a new instance of the generator from input generator function
            subgenerator = target()
            return (yield from subgenerator)
        # handle exceptions raised by the subgenerator
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
