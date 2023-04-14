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

    def __init__(self, target, predicate, sleep_generator, timeout=None, on_error=None):
        self.subgenerator_fn = target
        self.subgenerator = None
        self.predicate = predicate
        self.sleep_generator = sleep_generator
        self.on_error = on_error
        self.timeout = timeout
        self.remaining_timeout_budget = timeout if timeout else None

    async def _ensure_subgenerator(self):
        if not self.subgenerator:
            if inspect.iscoroutinefunction(self.subgenerator_fn):
                self.subgenerator = await self.subgenerator_fn()
            else:
                self.subgenerator = self.subgenerator_fn()

    def __aiter__(self):
        return self

    async def _handle_exception(self, exc):
        if not self.predicate(exc) and not isinstance(exc, asyncio.TimeoutError):
            raise exc
        else:
            if self.on_error:
                self.on_error(exc)
            try:
                next_sleep = next(self.sleep_generator)
            except StopIteration:
                raise ValueError('Sleep generator stopped yielding sleep values')

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
            await asyncio.sleep(next_sleep)
            self.subgenerator = None
            await self._ensure_subgenerator()

    def _subtract_time_from_budget(self, start_timestamp):
        if self.remaining_timeout_budget is not None:
            self.remaining_timeout_budget -= (
                datetime_helpers.utcnow() - start_timestamp
            ).total_seconds()

    async def __anext__(self):
        await self._ensure_subgenerator()
        if self.remaining_timeout_budget is not None and self.remaining_timeout_budget <= 0:
            raise exceptions.RetryError(
                "Timeout of {:.1f}s exceeded".format(self.timeout),
                None,
            )
        try:
            start_timestamp = datetime_helpers.utcnow()
            next_val_routine = asyncio.wait_for(
                self.subgenerator.__anext__(),
                self.remaining_timeout_budget
            )
            next_val = await next_val_routine
            self._subtract_time_from_budget(start_timestamp)
            return next_val
        except (Exception, asyncio.CancelledError) as exc:
            self._subtract_time_from_budget(start_timestamp)
            await self._handle_exception(exc)
        # if retryable exception was handled, try again with new subgenerator
        return await self.__anext__()

    async def aclose(self):
        await self._ensure_subgenerator()
        if getattr(self.subgenerator, "aclose", None):
            return await self.subgenerator.aclose()
        else:
            raise AttributeError("aclose is not implemented for retried stream")

    async def asend(self, value):
        await self._ensure_subgenerator()
        if getattr(self.subgenerator, "asend", None):
            if self.remaining_timeout_budget is not None and self.remaining_timeout_budget <= 0:
                raise exceptions.RetryError(
                    "Timeout of {:.1f}s exceeded".format(self.timeout),
                    None,
                )
            try:
                start_timestamp = datetime_helpers.utcnow()
                next_val_routine = asyncio.wait_for(
                    self.subgenerator.asend(value),
                    self.remaining_timeout_budget
                )
                next_val = await next_val_routine
                self._subtract_time_from_budget(start_timestamp)
                return next_val
            except (Exception, asyncio.CancelledError) as exc:
                self._subtract_time_from_budget(start_timestamp)
                await self._handle_exception(exc)
            # if retryable exception was handled, try again with new subgenerator
            return await self.__asend__(value)
        else:
            raise AttributeError("asend is not implemented for retried stream")

    async def athrow(self, typ, val=None, tb=None):
        await self._ensure_subgenerator()
        if getattr(self.subgenerator, "athrow", None):
            try:
                return await self.subgenerator.athrow(typ, val, tb)
            except Exception as exc:
                await self._handle_exception(exc)
            # if retryable exception was handled, return next from new subgenerator
            return await self.__anext__()
        else:
            raise AttributeError("athrow is not implemented for retried stream")

