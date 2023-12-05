# Copyright 2020 Google LLC
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

import datetime
import re

import mock
import pytest

from google.api_core import exceptions
from google.api_core import retry_async

from ...unit.retry.test_retry_base import Test_BaseRetry


@mock.patch("asyncio.sleep", autospec=True)
@mock.patch(
    "google.api_core.datetime_helpers.utcnow",
    return_value=datetime.datetime.min,
    autospec=True,
)
@pytest.mark.asyncio
async def test_retry_target_success(utcnow, sleep):
    predicate = retry_async.if_exception_type(ValueError)
    call_count = [0]

    async def target():
        call_count[0] += 1
        if call_count[0] < 3:
            raise ValueError()
        return 42

    result = await retry_async.retry_target(target, predicate, range(10), None)

    assert result == 42
    assert call_count[0] == 3
    sleep.assert_has_calls([mock.call(0), mock.call(1)])


@mock.patch("asyncio.sleep", autospec=True)
@mock.patch(
    "google.api_core.datetime_helpers.utcnow",
    return_value=datetime.datetime.min,
    autospec=True,
)
@pytest.mark.asyncio
async def test_retry_target_w_on_error(utcnow, sleep):
    predicate = retry_async.if_exception_type(ValueError)
    call_count = {"target": 0}
    to_raise = ValueError()

    async def target():
        call_count["target"] += 1
        if call_count["target"] < 3:
            raise to_raise
        return 42

    on_error = mock.Mock()

    result = await retry_async.retry_target(
        target, predicate, range(10), None, on_error=on_error
    )

    assert result == 42
    assert call_count["target"] == 3

    on_error.assert_has_calls([mock.call(to_raise), mock.call(to_raise)])
    sleep.assert_has_calls([mock.call(0), mock.call(1)])


@mock.patch("asyncio.sleep", autospec=True)
@mock.patch(
    "google.api_core.datetime_helpers.utcnow",
    return_value=datetime.datetime.min,
    autospec=True,
)
@pytest.mark.asyncio
async def test_retry_target_non_retryable_error(utcnow, sleep):
    predicate = retry_async.if_exception_type(ValueError)
    exception = TypeError()
    target = mock.Mock(side_effect=exception)

    with pytest.raises(TypeError) as exc_info:
        await retry_async.retry_target(target, predicate, range(10), None)

    assert exc_info.value == exception
    sleep.assert_not_called()


@mock.patch("asyncio.sleep", autospec=True)
@mock.patch("time.monotonic", autospec=True)
@pytest.mark.asyncio
async def test_retry_target_deadline_exceeded(monotonic, sleep):
    predicate = retry_async.if_exception_type(ValueError)
    exception = ValueError("meep")
    target = mock.Mock(side_effect=exception)
    # Setup the timeline so that the first call takes 5 seconds but the second
    # call takes 6, which puts the retry over the deadline.
    monotonic.side_effect = [0, 5, 11]

    with pytest.raises(exceptions.RetryError) as exc_info:
        await retry_async.retry_target(target, predicate, range(10), deadline=10)

    assert exc_info.value.cause == exception
    assert exc_info.match("Timeout of 10.0s exceeded")
    assert exc_info.match("last exception: meep")
    assert target.call_count == 2

    # Ensure the exception message does not include the target fn:
    # it may be a partial with user data embedded
    assert str(target) not in exc_info.exconly()


@pytest.mark.asyncio
async def test_retry_target_bad_sleep_generator():
    with pytest.raises(ValueError, match="Sleep generator"):
        await retry_async.retry_target(
            mock.sentinel.target, mock.sentinel.predicate, [], None
        )


@pytest.mark.asyncio
async def test_retry_streaming_target_bad_sleep_generator():
    from google.api_core.retry.retry_streaming_async import retry_target_stream

    with pytest.raises(ValueError, match="Sleep generator"):
        await retry_target_stream(None, None, [], None).__anext__()


class TestAsyncRetry(Test_BaseRetry):
    def _make_one(self, *args, **kwargs):
        return retry_async.AsyncRetry(*args, **kwargs)

    def test___str__(self):
        def if_exception_type(exc):
            return bool(exc)  # pragma: NO COVER

        # Explicitly set all attributes as changed Retry defaults should not
        # cause this test to start failing.
        retry_ = retry_async.AsyncRetry(
            predicate=if_exception_type,
            initial=1.0,
            maximum=60.0,
            multiplier=2.0,
            deadline=120.0,
            on_error=None,
        )
        assert re.match(
            (
                r"<AsyncRetry predicate=<function.*?if_exception_type.*?>, "
                r"initial=1.0, maximum=60.0, multiplier=2.0, timeout=120.0, "
                r"on_error=None>"
            ),
            str(retry_),
        )

    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___and_execute_success(self, sleep):
        retry_ = retry_async.AsyncRetry()
        target = mock.AsyncMock(spec=["__call__"], return_value=42)
        # __name__ is needed by functools.partial.
        target.__name__ = "target"

        decorated = retry_(target)
        target.assert_not_called()

        result = await decorated("meep")

        assert result == 42
        target.assert_called_once_with("meep")
        sleep.assert_not_called()

    @mock.patch("random.uniform", autospec=True, side_effect=lambda m, n: n)
    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___and_execute_retry(self, sleep, uniform):
        on_error = mock.Mock(spec=["__call__"], side_effect=[None])
        retry_ = retry_async.AsyncRetry(
            predicate=retry_async.if_exception_type(ValueError)
        )

        target = mock.AsyncMock(spec=["__call__"], side_effect=[ValueError(), 42])
        # __name__ is needed by functools.partial.
        target.__name__ = "target"

        decorated = retry_(target, on_error=on_error)
        target.assert_not_called()

        result = await decorated("meep")

        assert result == 42
        assert target.call_count == 2
        target.assert_has_calls([mock.call("meep"), mock.call("meep")])
        sleep.assert_called_once_with(retry_._initial)
        assert on_error.call_count == 1

    @mock.patch("random.uniform", autospec=True, side_effect=lambda m, n: n)
    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___and_execute_retry_hitting_deadline(self, sleep, uniform):
        on_error = mock.Mock(spec=["__call__"], side_effect=[None] * 10)
        retry_ = retry_async.AsyncRetry(
            predicate=retry_async.if_exception_type(ValueError),
            initial=1.0,
            maximum=1024.0,
            multiplier=2.0,
            deadline=30.9,
        )

        monotonic_patcher = mock.patch("time.monotonic", return_value=0)

        target = mock.AsyncMock(spec=["__call__"], side_effect=[ValueError()] * 10)
        # __name__ is needed by functools.partial.
        target.__name__ = "target"

        decorated = retry_(target, on_error=on_error)
        target.assert_not_called()

        with monotonic_patcher as patched_monotonic:
            # Make sure that calls to fake asyncio.sleep() also advance the mocked
            # time clock.
            def increase_time(sleep_delay):
                print(sleep_delay)
                patched_monotonic.return_value += sleep_delay

            sleep.side_effect = increase_time

            with pytest.raises(exceptions.RetryError):
                await decorated("meep")

        assert target.call_count == 5
        target.assert_has_calls([mock.call("meep")] * 5)
        assert on_error.call_count == 5

        # check the delays
        assert sleep.call_count == 4  # once between each successive target calls
        last_wait = sleep.call_args.args[0]
        total_wait = sum(call_args.args[0] for call_args in sleep.call_args_list)

        assert last_wait == 8.0
        # Next attempt would be scheduled in 16 secs, 15 + 16 = 31 > 30.9, thus
        # we do not even wait for it to be scheduled (30.9 is configured timeout).
        # This changes the previous logic of shortening the last attempt to fit
        # in the deadline. The previous logic was removed to make Python retry
        # logic consistent with the other languages and to not disrupt the
        # randomized retry delays distribution by artificially increasing a
        # probability of scheduling two (instead of one) last attempts with very
        # short delay between them, while the second retry having very low chance
        # of succeeding anyways.
        assert total_wait == 15.0

    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___init___without_retry_executed(self, sleep):
        _some_function = mock.Mock()

        retry_ = retry_async.AsyncRetry(
            predicate=retry_async.if_exception_type(ValueError), on_error=_some_function
        )
        # check the proper creation of the class
        assert retry_._on_error is _some_function

        target = mock.AsyncMock(spec=["__call__"], side_effect=[42])
        # __name__ is needed by functools.partial.
        target.__name__ = "target"

        wrapped = retry_(target)

        result = await wrapped("meep")

        assert result == 42
        target.assert_called_once_with("meep")
        sleep.assert_not_called()
        _some_function.assert_not_called()

    @mock.patch("random.uniform", autospec=True, side_effect=lambda m, n: n)
    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___init___when_retry_is_executed(self, sleep, uniform):
        _some_function = mock.Mock()

        retry_ = retry_async.AsyncRetry(
            predicate=retry_async.if_exception_type(ValueError), on_error=_some_function
        )
        # check the proper creation of the class
        assert retry_._on_error is _some_function

        target = mock.AsyncMock(
            spec=["__call__"], side_effect=[ValueError(), ValueError(), 42]
        )
        # __name__ is needed by functools.partial.
        target.__name__ = "target"

        wrapped = retry_(target)
        target.assert_not_called()

        result = await wrapped("meep")

        assert result == 42
        assert target.call_count == 3
        assert _some_function.call_count == 2
        target.assert_has_calls([mock.call("meep"), mock.call("meep")])
        sleep.assert_any_call(retry_._initial)