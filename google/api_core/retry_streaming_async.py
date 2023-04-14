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

from typing import Callable, Optional, Iterable, AsyncIterable, Awaitable, Union

import asyncio
import inspect
import logging

from collections.abc import AsyncGenerator

from google.api_core import datetime_helpers
from google.api_core import exceptions

_LOGGER = logging.getLogger(__name__)


class AsyncRetryableGenerator(AsyncGenerator):
    """
    Helper class for retrying AsyncIterator and AsyncGenerator-based
    streaming APIs.
    """

    def __init__(
        self,
        target: Union[
            Callable[[], AsyncIterable], Callable[[], Awaitable[AsyncIterable]]
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
        self.active_target: Optional[AsyncIterable] = None
        self.predicate = predicate
        self.sleep_generator = sleep_generator
        self.on_error = on_error
        self.timeout = timeout
        self.remaining_timeout_budget = timeout if timeout else None

    async def _ensure_active_target(self):
        """
        Ensure that the active target is populated and ready to be iterated over.
        """
        if not self.active_target:
            if inspect.iscoroutinefunction(self.target_fn):
                self.active_target = await self.target_fn()
            else:
                self.active_target = self.target_fn()

    def __aiter__(self):
        """Implement the async iterator protocol."""
        return self

    async def _handle_exception(self, exc):
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
            # if time budget is exceeded, raise RetryError
            if self.remaining_timeout_budget is not None:
                if self.remaining_timeout_budget <= next_sleep:
                    raise exceptions.RetryError(
                        "Timeout of {:.1f}s exceeded".format(self.timeout),
                        exc,
                    ) from exc
                else:
                    self.remaining_timeout_budget -= next_sleep
            _LOGGER.debug(
                "Retrying due to {}, sleeping {:.1f}s ...".format(exc, next_sleep)
            )
            # sleep before retrying
            await asyncio.sleep(next_sleep)
            self.active_target = None
            await self._ensure_active_target()

    def _subtract_time_from_budget(self, start_timestamp):
        """
        Subtract the time elapsed since start_timestamp from the remaining
        timeout budget.

        Args:
        - start_timestamp (datetime): The time at which the last operation
            started.
        """
        if self.remaining_timeout_budget is not None:
            self.remaining_timeout_budget -= (
                datetime_helpers.utcnow() - start_timestamp
            ).total_seconds()

    async def _iteration_helper(
        self, iteration_fn: Callable[..., Awaitable], try_again_fn: Callable, *args
    ):
        """
        Helper function for sharing logic between __anext__ and asend.

        Args:
          - iteration_fn: The function to call to get the next value from the
                iterator (e.g. __anext__ or asend)
          - try_again_fn: The function to call after a retryable exception is
                encountered, to get a value from the new active_target
                (e.g. self.__anext__ or self.asend)
          - *args: Any additional arguments to pass to iteration_fn and
                try_again_fn (e.g. the value to send to asend)
        """
        # check for expired timeouts before attempting to iterate
        if (
            self.remaining_timeout_budget is not None
            and self.remaining_timeout_budget <= 0
            and self.timeout is not None
        ):
            raise exceptions.RetryError(
                "Timeout of {:.1f}s exceeded".format(self.timeout),
                None,
            )
        try:
            # start the timer for the current operation
            start_timestamp = datetime_helpers.utcnow()
            # grab the next value from the active_target
            next_val_routine = asyncio.wait_for(
                iteration_fn(*args), self.remaining_timeout_budget
            )
            next_val = await next_val_routine
            # subtract the time spent waiting for the next value from the
            # remaining timeout budget
            self._subtract_time_from_budget(start_timestamp)
            return next_val
        except (Exception, asyncio.CancelledError) as exc:
            self._subtract_time_from_budget(start_timestamp)
            await self._handle_exception(exc)
        # if retryable exception was handled, try again with new active_target
        return await try_again_fn(*args)

    async def __anext__(self):
        """
        Implement the async iterator protocol.
        """
        await self._ensure_active_target()
        return await self._iteration_helper(
            self.active_target.__anext__, self.__anext__
        )

    async def aclose(self):
        """
        Close the active_target if supported. (e.g. target is an async generator)

        Raises:
          - AttributeError if the active_target does not have a aclose() method
        """
        await self._ensure_active_target()
        if getattr(self.active_target, "aclose", None):
            return await self.active_target.aclose()
        else:
            raise AttributeError(
                "aclose() not implemented for {}".format(self.active_target)
            )

    async def asend(self, value):
        """
        Call asend on the active_target if supported. (e.g. target is an async generator)

        If an exception is raised, a retry may be attempted before returning
        a result.

        Returns:
          - the result of calling asend() on the active_target

        Raises:
          - AttributeError if the active_target does not have a asend() method
        """
        await self._ensure_active_target()
        if getattr(self.active_target, "asend", None):
            return await self._iteration_helper(
                self.active_target.asend, self.asend, value
            )
        else:
            raise AttributeError(
                "asend() not implemented for {}".format(self.active_target)
            )

    async def athrow(self, typ, val=None, tb=None):
        """
        Call athrow on the active_target if supported. (e.g. target is an async generator)

        If an exception is raised, a retry may be attempted before returning

        Returns:
          - the result of calling athrow() on the active_target
        Raises:
          - AttributeError if the active_target does not have a athrow() method
        """
        await self._ensure_active_target()
        if getattr(self.active_target, "athrow", None):
            try:
                return await self.active_target.athrow(typ, val, tb)
            except Exception as exc:
                await self._handle_exception(exc)
            # if retryable exception was handled, return next from new active_target
            return await self.__anext__()
        else:
            raise AttributeError(
                "athrow() not implemented for {}".format(self.active_target)
            )
