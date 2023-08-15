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
    cast,
)

import logging
import time
from functools import partial

from google.api_core import exceptions

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class _TerminalException(Exception):
    """
    Exception to bypasses retry logic and raises __cause__ immediately.
    """
    pass


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
    target: Callable[[], Iterable[T]],
    predicate: Callable[[Exception], bool],
    sleep_generator: Iterable[float],
    timeout: Optional[float] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    exception_factory: Optional[
        Callable[
            [List[Exception], bool, float], Tuple[Exception, Optional[Exception]]
        ]
    ] = None,
    **kwargs,
) -> Generator[T, Any, None]:
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
                exc, source_exc = exc_factory(exc_list=error_list, is_timeout=False)
                raise exc from source_exc
            if on_error is not None:
                on_error(exc)
        finally:
            if subgenerator is not None and getattr(subgenerator, "close", None):
                subgenerator.close()

        if deadline is not None and time.monotonic() + sleep > deadline:
            exc, source_exc = exc_factory(exc_list=error_list, is_timeout=True)
            raise exc from source_exc
        _LOGGER.debug(
            "Retrying due to {}, sleeping {:.1f}s ...".format(error_list[-1], sleep)
        )
        time.sleep(sleep)

    raise ValueError("Sleep generator stopped yielding sleep values.")
