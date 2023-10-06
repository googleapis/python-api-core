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
)

import logging
import time
from functools import partial

import google.api_core.retry as retries

_Y = TypeVar("_Y")  # yielded values

_LOGGER = logging.getLogger(__name__)


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
    exc_factory = partial(
        exception_factory or retries._build_retry_error, timeout_val=timeout
    )

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
                    exc_list=error_list,
                    reason=retries.RetryFailureReason.NON_RETRYABLE_ERROR,
                )
                raise final_exc from source_exc
            if on_error is not None:
                on_error(exc)

        if deadline is not None and time.monotonic() + sleep > deadline:
            final_exc, source_exc = exc_factory(
                exc_list=error_list, reason=retries.RetryFailureReason.TIMEOUT
            )
            raise final_exc from source_exc
        _LOGGER.debug(
            "Retrying due to {}, sleeping {:.1f}s ...".format(error_list[-1], sleep)
        )
        time.sleep(sleep)

    raise ValueError("Sleep generator stopped yielding sleep values.")
