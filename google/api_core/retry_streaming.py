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

from typing import Callable, Optional, Iterable, Iterator, Generator, TypeVar, Any, cast

import datetime
import logging
import time

from google.api_core import datetime_helpers
from google.api_core import exceptions

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class RetryableGenerator(Generator[T, Any, None]):
    """
    Helper class for retrying Iterator and Generator-based
    streaming APIs.
    """

    def __init__(
        self,
        target: Callable[[], Iterable[T]],
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
            timeout: How long to keep retrying the target, in seconds.
            on_error: A function to call while processing a
                retryable exception.  Any error raised by this function will *not*
                be caught.
        """
        self.target_fn = target
        self.active_target: Iterator[T] = self.target_fn().__iter__()
        self.predicate = predicate
        self.sleep_generator = iter(sleep_generator)
        self.on_error = on_error
        self.timeout = timeout
        if self.timeout is not None:
            self.deadline = datetime_helpers.utcnow() + datetime.timedelta(
                seconds=self.timeout
            )
        else:
            self.deadline = None

    def __iter__(self) -> Generator[T, Any, None]:
        """
        Implement the iterator protocol.
        """
        return self

    def _handle_exception(self, exc) -> None:
        """
        When an exception is raised while iterating over the active_target,
        check if it is retryable. If so, create a new active_target and
        continue iterating. If not, raise the exception.
        """
        if not self.predicate(exc):
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
            # sleep before retrying
            _LOGGER.debug(
                "Retrying due to {}, sleeping {:.1f}s ...".format(exc, next_sleep)
            )
            time.sleep(next_sleep)
            self.active_target = self.target_fn().__iter__()

    def _check_timeout(self, current_time:float, source_exception: Optional[Exception] = None) -> None:
        """
        Helper function to check if the timeout has been exceeded, and raise a RetryError if so.

        Args:
          - current_time: the timestamp to check against the deadline
          - source_exception: the exception that triggered the timeout check, if any
        Raises:
          - RetryError if the deadline has been exceeded
        """
        if self.deadline is not None and self.deadline < current_time:
            raise exceptions.RetryError(
                "Timeout of {:.1f}s exceeded".format(self.timeout),
                source_exception,
            ) from source_exception

    def __next__(self) -> T:
        """
        Implement the iterator protocol.

        Returns:
          - the next value of the active_target iterator
        """
        # check for expired timeouts before attempting to iterate
        self._check_timeout(datetime_helpers.utcnow())
        try:
            return next(self.active_target)
        except Exception as exc:
            self._handle_exception(exc)
        # if retryable exception was handled, try again with new active_target
        return self.__next__()

    def close(self) -> None:
        """
        Close the active_target if supported. (e.g. target is a generator)

        Raises:
          - AttributeError if the active_target does not have a close() method
        """
        if getattr(self.active_target, "close", None):
            casted_target = cast(Generator, self.active_target)
            return casted_target.close()
        else:
            raise AttributeError(
                "close() not implemented for {}".format(self.active_target)
            )

    def send(self, *args, **kwargs) -> T:
        """
        Call send on the active_target if supported. (e.g. target is a generator)

        If an exception is raised, a retry may be attempted before returning
        a result.

        Args:
          - *args: arguments to pass to the wrapped generator's send method
          - **kwargs: keyword arguments to pass to the wrapped generator's send method
        Returns:
          - the next value of the active_target iterator after calling send
        Raises:
          - AttributeError if the active_target does not have a send() method
        """
        # check for expired timeouts before attempting to iterate
        self._check_timeout(datetime_helpers.utcnow())
        if getattr(self.active_target, "send", None):
            casted_target = cast(Generator, self.active_target)
            try:
                return casted_target.send(*args, **kwargs)
            except Exception as exc:
                self._handle_exception(exc)
            # if exception was retryable, use new target for return value
            return self.__next__()
        else:
            raise AttributeError(
                "send() not implemented for {}".format(self.active_target)
            )

    def throw(self, *args, **kwargs) -> T:
        """
        Call throw on the active_target if supported. (e.g. target is a generator)

        If an exception is raised, a retry may be attempted before returning
        a result.

        Args:
          - *args: arguments to pass to the wrapped generator's throw method
          - **kwargs: keyword arguments to pass to the wrapped generator's throw method
        Returns:
          - the next vale of the active_target iterator after calling throw
        Raises:
          - AttributeError if the active_target does not have a throw() method
        """
        if getattr(self.active_target, "throw", None):
            casted_target = cast(Generator, self.active_target)
            try:
                return casted_target.throw(*args, **kwargs)
            except Exception as exc:
                self._handle_exception(exc)
            # if retryable exception was handled, return next from new active_target
            return self.__next__()
        else:
            raise AttributeError(
                "throw() not implemented for {}".format(self.active_target)
            )
