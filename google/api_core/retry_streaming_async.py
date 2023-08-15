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
    **kwargs,
) -> AsyncGenerator[T, None]:
    """
    Generator wrapper for retryable streaming RPCs.
    This function will be used when initilizing a retry with
    ``AsyncRetry(is_stream=True)``.

    When ``is_stream=False``, the target is treated as a coroutine,
    and will retry when the coroutine returns an error. When ``is_stream=True``,
    the target will be treated as a callable that retruns an AsyncIterable. Instead
    of just wrapping the initial call in retry logic, the entire iterable is
    wrapped, with each yield passing through the retryable generatpr. If any yield
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
        grpc call in a function that modifies the request based on what has
        already been returned:

        ```
        async def attempt_with_modified_request(target, request, seen_items=[]):
            # remove seen items from request on each attempt
            new_request = modify_request(request, seen_items)
            new_generator = await target(new_request)
            async for item in new_generator:
                yield item
                seen_items.append(item)

        retry_wrapped = AsyncRetry(is_stream=True)(attempt_with_modified_request, target, request, [])
        ```

        2. Wrap the retry generator
            Alternatively, you can wrap the retryable generator itself before
            passing it to the end-user to add a filter on the stream. For
            example, you can keep track of the items that were successfully yielded
            in previous retry attempts, and only yield new items when the
            new attempt surpasses the previous ones:

            ``
            async def retryable_with_filter(target):
                stream_idx = 0
                # reset stream_idx when the stream is retried
                def on_error(e):
                    nonlocal stream_idx
                    stream_idx = 0
                # build retryable
                retryable_gen = AsyncRetry(is_stream=True, on_error=on_error, ...)(target)
                # keep track of what has been yielded out of filter
                yielded_items = []
                async for item in retryable_gen:
                    if stream_idx >= len(yielded_items):
                        yield item
                        yielded_items.append(item)
                    elif item != previous_stream[stream_idx]:
                        raise ValueError("Stream differs from last attempt")"
                    stream_idx += 1

            filter_retry_wrapped = retryable_with_filter(target)
            ```
    """
    subgenerator : Optional[AsyncIterator[T]] = None
    timeout = kwargs.get("deadline", timeout)
    deadline: Optional[float] = time.monotonic() + timeout if timeout else None
    # keep track of retryable exceptions we encounter to pass in to exception_factory
    error_list: List[Exception] = []
    # override exception_factory to build a more complex exception
    exc_factory = partial(
        exception_factory or _build_timeout_error, timeout_val=timeout
    )

    for sleep in sleep_generator:
        # Start a new retry loop
        try:
            # generator may be raw iterator, or wrapped in an awaitable
            gen_instance: Union[AsyncIterable[T], Awaitable[AsyncIterable[T]]] = target()
            try:
                gen_instance = await gen_instance # type: ignore
            except TypeError:
                # was not awaitable
                pass
            subgenerator = cast(AsyncIterable[T], gen_instance).__aiter__()

            # if target is a generator, we will advance it using asend
            # otherwise, we will use anext
            supports_send = bool(getattr(subgenerator, "asend", None))

            sent_in = None
            while True:
                ## Read from Subgenerator
                if supports_send:
                    next_value = await subgenerator.asend(sent_in) # type: ignore
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
                        await cast(AsyncGenerator[T, None], subgenerator).aclose()
                    else:
                        raise
                    return
                except:  # noqa: E722
                    # bare except catches any exception passed to `athrow`
                    # delegate error handling to subgenerator
                    if getattr(subgenerator, "athrow", None):
                        await cast(AsyncGenerator[T, None], subgenerator).athrow(*sys.exc_info())
                    else:
                        raise
            return
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
                await cast(AsyncGenerator[T, None], subgenerator).aclose()

        # sleep and adjust timeout budget
        if deadline is not None and time.monotonic() + sleep > deadline:
            final_exc, source_exc = exc_factory(exc_list=error_list, is_timeout=True)
            raise final_exc from source_exc
        _LOGGER.debug(
            "Retrying due to {}, sleeping {:.1f}s ...".format(error_list[-1], sleep)
        )
        await asyncio.sleep(sleep)
    raise ValueError("Sleep generator stopped yielding sleep values.")
