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

import datetime
import logging
import time

from collections.abc import Generator

from google.api_core import datetime_helpers
from google.api_core import exceptions

_LOGGER = logging.getLogger(__name__)


class RetryableGenerator(Generator):
    """
    Helper class for retrying Iterator and Generator-based
    streaming APIs.
    """

    def __init__(self, target, predicate, sleep_generator, timeout=None, on_error=None):
        self.subgenerator_fn = target
        self.subgenerator = self.subgenerator_fn()
        self.predicate = predicate
        self.sleep_generator = sleep_generator
        self.on_error = on_error
        self.timeout = timeout
        if self.timeout is not None:
            self.deadline = datetime_helpers.utcnow() + datetime.timedelta(
                seconds=self.timeout
            )
        else:
            self.deadline = None

    def __iter__(self):
        return self

    def _handle_exception(self, exc):
        if not self.predicate(exc):
            raise exc
        else:
            if self.on_error:
                self.on_error(exc)
            try:
                next_sleep = next(self.sleep_generator)
            except StopIteration:
                raise ValueError("Sleep generator stopped yielding sleep values")
            if self.deadline is not None:
                next_attempt = datetime_helpers.utcnow() + datetime.timedelta(
                    seconds=next_sleep
                )
                if self.deadline < next_attempt:
                    raise exceptions.RetryError(
                        f"Deadline of {self.timeout:.1f} seconds exceeded", exc
                    ) from exc
            _LOGGER.debug(
                "Retrying due to {}, sleeping {:.1f}s ...".format(exc, next_sleep)
            )
            time.sleep(next_sleep)
            self.subgenerator = self.subgenerator_fn()

    def __next__(self):
        try:
            return next(self.subgenerator)
        except Exception as exc:
            self._handle_exception(exc)
        # if retryable exception was handled, try again with new subgenerator
        return self.__next__()

    def close(self):
        if getattr(self.subgenerator, "close", None):
            return self.subgenerator.close()
        else:
            raise AttributeError(
                "close() not implemented for {}".format(self.subgenerator)
            )

    def send(self, value):
        if getattr(self.subgenerator, "send", None):
            try:
                return self.subgenerator.send(value)
            except Exception as exc:
                self._handle_exception(exc)
            # if retryable exception was handled, try again with new subgenerator
            return self.send(value)
        else:
            raise AttributeError(
                "send() not implemented for {}".format(self.subgenerator)
            )

    def throw(self, typ, val=None, tb=None):
        if getattr(self.subgenerator, "throw", None):
            try:
                return self.subgenerator.throw(typ, val, tb)
            except Exception as exc:
                self._handle_exception(exc)
            # if retryable exception was handled, return next from new subgenerator
            return self.__next__()
        else:
            raise AttributeError(
                "throw() not implemented for {}".format(self.subgenerator)
            )
