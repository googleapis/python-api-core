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
    AsyncIterator,
    AsyncIterable,
    Awaitable,
    Union,
    TypeVar,
    AsyncGenerator,
)

import asyncio
import logging
import datetime

from google.api_core import datetime_helpers
from google.api_core import exceptions

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class AsyncRetryableGenerator(AsyncGenerator[T, None]):
    """
    Helper class for retrying AsyncIterator and AsyncGenerator-based
    streaming APIs.
    """

    def __init__(
        self,
        target: Union[
            Callable[[], AsyncIterable[T]],
            Callable[[], Awaitable[AsyncIterable[T]]],
        ],
        predicate: Callable[[Exception], bool],
        sleep_generator: Iterable[float],
        timeout: Optional[float] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ):
        """
        Args:
            target: The function to call to produce iterables for each retry.
                This must be a nullary function - apply arguments with
                `functools.partial`.
            predicate: A callable used to determine if an
                exception raised by the target should be considered retryable.
                It should return True to retry or False otherwise.
            sleep_generator: An infinite iterator that determines
                how long to sleep between retries.
            timeout: How long to keep retrying the target.
            on_error: A function to call while processing a
                retryable exception.  Any error raised by this function will *not*
                be caught.
        """
        self.target_fn = target
        # active target must be populated in an async context
        self.active_target: Optional[AsyncIterator[T]] = None
        self.predicate = predicate
        self.sleep_generator = iter(sleep_generator)
        self.on_error = on_error
        self.timeout = timeout
        self.timeout_task = None
        if self.timeout is not None:
            self.deadline = datetime_helpers.utcnow() + datetime.timedelta(
                seconds=self.timeout
            )
        else:
            self.deadline = None

    def _check_timeout(
        self, current_time: float, source_exception: Optional[Exception] = None
    ) -> None:
        """
        Helper function to check if the timeout has been exceeded, and raise a RetryError if so.

        Args:
          - current_time: the timestamp to check against the deadline
          - source_exception: the exception that triggered the timeout check, if any
        Raises:
          - RetryError if the deadline has been exceeded
        """
        if (
            self.deadline is not None
            and self.timeout is not None
            and self.deadline < current_time
        ):
            raise exceptions.RetryError(
                "Timeout of {:.1f}s exceeded".format(self.timeout),
                source_exception,
            ) from source_exception

    async def _ensure_active_target(self) -> AsyncIterator[T]:
        """
        Ensure that the active target is populated and ready to be iterated over.

        Returns:
          - The active_target iterable
        """
        if not self.active_target:
            new_iterable = self.target_fn()
            if isinstance(new_iterable, Awaitable):
                new_iterable = await new_iterable
            self.active_target = new_iterable.__aiter__()
        return self.active_target

    def __aiter__(self) -> AsyncIterator[T]:
        """Implement the async iterator protocol."""
        return self

    async def _handle_exception(self, exc) -> None:
        """
        When an exception is raised while iterating over the active_target,
        check if it is retryable. If so, create a new active_target and
        continue iterating. If not, raise the exception.
        """
        if not self.predicate(exc) and not isinstance(exc, asyncio.TimeoutError):
            raise exc
        else:
            # run on_error callback if provided
            if self.on_error:
                self.on_error(exc)
            try:
                next_sleep = next(self.sleep_generator)
            except StopIteration:
                raise ValueError("Sleep generator stopped yielding sleep values")
            # if deadline is exceeded, raise RetryError
            if self.deadline is not None:
                next_attempt = datetime_helpers.utcnow() + datetime.timedelta(
                    seconds=next_sleep
                )
                self._check_timeout(next_attempt, exc)
            _LOGGER.debug(
                "Retrying due to {}, sleeping {:.1f}s ...".format(exc, next_sleep)
            )
            # sleep before retrying
            await asyncio.sleep(next_sleep)
            self.active_target = None
            await self._ensure_active_target()

    async def _iteration_helper(self, iteration_routine: Awaitable) -> T:
        """
        Helper function for sharing logic between __anext__ and asend.

        Args:
          - iteration_routine: The coroutine to await to get the next value
                from the iterator (e.g. __anext__ or asend)
        Returns:
          - The next value from the active_target iterator.
        """
        # check for expired timeouts before attempting to iterate
        self._check_timeout(datetime_helpers.utcnow())
        try:
            # grab the next value from the active_target
            # Note: here would be a good place to add a timeout, like asyncio.wait_for.
            # But wait_for is expensive, so we only check for timeouts at the
            # start of each iteration.
            return await iteration_routine
        except Exception as exc:
            await self._handle_exception(exc)
        # if retryable exception was handled, find the next value to return
        return await self.__anext__()

    async def __anext__(self) -> T:
        """
        Implement the async iterator protocol.

        Returns:
          - The next value from the active_target iterator.
        """
        iterable = await self._ensure_active_target()
        return await self._iteration_helper(
            iterable.__anext__(),
        )

    async def aclose(self) -> None:
        """
        Close the active_target if supported. (e.g. target is an async generator)

        Raises:
          - AttributeError if the active_target does not have a aclose() method
        """
        await self._ensure_active_target()
        if getattr(self.active_target, "aclose", None):
            casted_target = cast(AsyncGenerator[T, None], self.active_target)
            return await casted_target.aclose()
        else:
            raise AttributeError(
                "aclose() not implemented for {}".format(self.active_target)
            )

    async def asend(self, *args, **kwargs) -> T:
        """
        Call asend on the active_target if supported. (e.g. target is an async generator)

        If an exception is raised, a retry may be attempted before returning
        a result.


        Args:
          - *args: arguments to pass to the wrapped generator's asend method
          - **kwargs: keyword arguments to pass to the wrapped generator's asend method
        Returns:
          - the next value of the active_target iterator after calling asend
        Raises:
          - AttributeError if the active_target does not have a asend() method
        """
        await self._ensure_active_target()
        if getattr(self.active_target, "asend", None):
            casted_target = cast(AsyncGenerator[T, None], self.active_target)
            return await self._iteration_helper(casted_target.asend(*args, **kwargs))
        else:
            raise AttributeError(
                "asend() not implemented for {}".format(self.active_target)
            )

    async def athrow(self, *args, **kwargs) -> T:
        """
        Call athrow on the active_target if supported. (e.g. target is an async generator)

        If an exception is raised, a retry may be attempted before returning

        Args:
          - *args: arguments to pass to the wrapped generator's athrow method
          - **kwargs: keyword arguments to pass to the wrapped generator's athrow method
        Returns:
          - the next value of the active_target iterator after calling athrow
        Raises:
          - AttributeError if the active_target does not have a athrow() method
        """
        await self._ensure_active_target()
        if getattr(self.active_target, "athrow", None):
            casted_target = cast(AsyncGenerator[T, None], self.active_target)
            try:
                return await casted_target.athrow(*args, **kwargs)
            except Exception as exc:
                await self._handle_exception(exc)
            # if retryable exception was handled, return next from new active_target
            return await self.__anext__()
        else:
            raise AttributeError(
                "athrow() not implemented for {}".format(self.active_target)
            )
