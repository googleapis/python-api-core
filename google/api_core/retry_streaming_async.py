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

"""Helpers for retries for async streaming APIs."""

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
)

import asyncio
import logging
import time
import sys
from functools import partial

from google.api_core.retry_streaming import _build_timeout_error
from google.api_core.retry_streaming import _TerminalException

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_target_generator(
    target: Union[
        Callable[[], AsyncIterable[T]],
        Callable[[], Awaitable[AsyncIterable[T]]],
    ],
    predicate: Callable[[Exception], bool],
    sleep_generator: Iterable[float],
    timeout: Optional[float] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    exception_factory: Optional[
        Callable[
            [List[Exception], bool, float], Tuple[Exception, Optional[Exception]]
        ]
    ] = None,
    check_timeout_on_yield: bool = False,
    **kwargs,
) -> AsyncGenerator[T, None]:
    subgenerator = None

    timeout = kwargs.get("deadline", timeout)

    deadline: Optional[float] = time.monotonic() + timeout if timeout else None
    error_list: List[Exception] = []
    exc_factory = partial(
        exception_factory or _build_timeout_error, timeout_val=timeout
    )

    for sleep in sleep_generator:
        # Start a new retry loop
        try:
            # generator may be raw iterator, or wrapped in an awaitable
            subgenerator = target()
            try:
                subgenerator = await subgenerator
            except TypeError:
                # was not awaitable
                pass

            # if target is a generator, we will advance it using asend
            # otherwise, we will use anext
            supports_send = bool(getattr(subgenerator, "asend", None))

            sent_in = None
            while True:
                # Check for expiration before starting
                if check_timeout_on_yield is True and deadline is not None and time.monotonic() > deadline:
                    exc, source_exc = exc_factory(exc_list=error_list, is_timeout=True)
                    exc.__cause__ = source_exc
                    raise _TerminalException() from exc
                ## Read from Subgenerator
                if supports_send:
                    next_value = await subgenerator.asend(sent_in)
                else:
                    next_value = await subgenerator.__anext__()
                ## Yield from Wrapper to caller
                try:
                    # yield last value from subgenerator
                    # exceptions from `athrow` and `aclose` are injected here
                    sent_in = yield next_value
                except GeneratorExit:
                    # if wrapper received `aclose`, pass to subgenerator and close
                    if bool(getattr(subgenerator, "aclose", None)):
                        await subgenerator.aclose()
                    else:
                        raise
                    return
                except:  # noqa: E722
                    # bare except catches any exception passed to `athrow`
                    # delegate error handling to subgenerator
                    if getattr(subgenerator, "athrow", None):
                        await subgenerator.athrow(*sys.exc_info())
                    else:
                        raise
            return
        except _TerminalException as exc:
            raise exc.__cause__ from exc.__cause__.__cause__
        except StopAsyncIteration:
            # if generator exhausted, return
            return
        # pylint: disable=broad-except
        # This function handles exceptions thrown by subgenerator
        except (Exception, asyncio.CancelledError) as exc:
            error_list.append(exc)
            if not predicate(exc):
                exc, source_exc = exc_factory(exc_list=error_list, is_timeout=False)
                raise exc from source_exc
            if on_error is not None:
                on_error(exc)
        finally:
            if subgenerator is not None and getattr(subgenerator, "aclose", None):
                await subgenerator.aclose()

        # sleep and adjust timeout budget
        if deadline is not None and time.monotonic() + sleep > deadline:
            exc, source_exc = exc_factory(exc_list=error_list, is_timeout=True)
            raise exc from source_exc
        _LOGGER.debug(
            "Retrying due to {}, sleeping {:.1f}s ...".format(error_list[-1], sleep)
        )
        await asyncio.sleep(sleep)
    raise ValueError("Sleep generator stopped yielding sleep values.")
