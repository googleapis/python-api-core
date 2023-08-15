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
import asyncio

import mock
import pytest

from google.api_core import exceptions
from google.api_core import retry_async


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
@mock.patch("google.api_core.datetime_helpers.utcnow", autospec=True)
@pytest.mark.asyncio
async def test_retry_target_deadline_exceeded(utcnow, sleep):
    predicate = retry_async.if_exception_type(ValueError)
    exception = ValueError("meep")
    target = mock.Mock(side_effect=exception)
    # Setup the timeline so that the first call takes 5 seconds but the second
    # call takes 6, which puts the retry over the deadline.
    utcnow.side_effect = [
        # The first call to utcnow establishes the start of the timeline.
        datetime.datetime.min,
        datetime.datetime.min + datetime.timedelta(seconds=5),
        datetime.datetime.min + datetime.timedelta(seconds=11),
    ]

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
    from google.api_core.retry_streaming_async import retry_target_stream

    with pytest.raises(ValueError, match="Sleep generator"):
        await retry_target_stream(None, None, [], None).__anext__()


class TestAsyncRetry:
    def test_constructor_defaults(self):
        retry_ = retry_async.AsyncRetry()
        assert retry_._predicate == retry_async.if_transient_error
        assert retry_._initial == 1
        assert retry_._maximum == 60
        assert retry_._multiplier == 2
        assert retry_._deadline == 120
        assert retry_._on_error is None

    def test_constructor_options(self):
        _some_function = mock.Mock()

        retry_ = retry_async.AsyncRetry(
            predicate=mock.sentinel.predicate,
            initial=1,
            maximum=2,
            multiplier=3,
            deadline=4,
            on_error=_some_function,
        )
        assert retry_._predicate == mock.sentinel.predicate
        assert retry_._initial == 1
        assert retry_._maximum == 2
        assert retry_._multiplier == 3
        assert retry_._deadline == 4
        assert retry_._on_error is _some_function

    def test_with_deadline(self):
        retry_ = retry_async.AsyncRetry(
            predicate=mock.sentinel.predicate,
            initial=1,
            maximum=2,
            multiplier=3,
            deadline=4,
            on_error=mock.sentinel.on_error,
        )
        new_retry = retry_.with_deadline(42)
        assert retry_ is not new_retry
        assert new_retry._deadline == 42

        # the rest of the attributes should remain the same
        assert new_retry._predicate is retry_._predicate
        assert new_retry._initial == retry_._initial
        assert new_retry._maximum == retry_._maximum
        assert new_retry._multiplier == retry_._multiplier
        assert new_retry._on_error is retry_._on_error

    def test_with_predicate(self):
        retry_ = retry_async.AsyncRetry(
            predicate=mock.sentinel.predicate,
            initial=1,
            maximum=2,
            multiplier=3,
            deadline=4,
            on_error=mock.sentinel.on_error,
        )
        new_retry = retry_.with_predicate(mock.sentinel.predicate)
        assert retry_ is not new_retry
        assert new_retry._predicate == mock.sentinel.predicate

        # the rest of the attributes should remain the same
        assert new_retry._deadline == retry_._deadline
        assert new_retry._initial == retry_._initial
        assert new_retry._maximum == retry_._maximum
        assert new_retry._multiplier == retry_._multiplier
        assert new_retry._on_error is retry_._on_error

    def test_with_delay_noop(self):
        retry_ = retry_async.AsyncRetry(
            predicate=mock.sentinel.predicate,
            initial=1,
            maximum=2,
            multiplier=3,
            deadline=4,
            on_error=mock.sentinel.on_error,
        )
        new_retry = retry_.with_delay()
        assert retry_ is not new_retry
        assert new_retry._initial == retry_._initial
        assert new_retry._maximum == retry_._maximum
        assert new_retry._multiplier == retry_._multiplier

    def test_with_delay(self):
        retry_ = retry_async.AsyncRetry(
            predicate=mock.sentinel.predicate,
            initial=1,
            maximum=2,
            multiplier=3,
            deadline=4,
            on_error=mock.sentinel.on_error,
        )
        new_retry = retry_.with_delay(initial=1, maximum=2, multiplier=3)
        assert retry_ is not new_retry
        assert new_retry._initial == 1
        assert new_retry._maximum == 2
        assert new_retry._multiplier == 3

        # the rest of the attributes should remain the same
        assert new_retry._deadline == retry_._deadline
        assert new_retry._predicate is retry_._predicate
        assert new_retry._on_error is retry_._on_error

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
            deadline=9.9,
        )

        utcnow = datetime.datetime.utcnow()
        utcnow_patcher = mock.patch(
            "google.api_core.datetime_helpers.utcnow", return_value=utcnow
        )

        target = mock.AsyncMock(spec=["__call__"], side_effect=[ValueError()] * 10)
        # __name__ is needed by functools.partial.
        target.__name__ = "target"

        decorated = retry_(target, on_error=on_error)
        target.assert_not_called()

        with utcnow_patcher as patched_utcnow:
            # Make sure that calls to fake asyncio.sleep() also advance the mocked
            # time clock.
            def increase_time(sleep_delay):
                patched_utcnow.return_value += datetime.timedelta(seconds=sleep_delay)

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

        assert last_wait == 2.9  # and not 8.0, because the last delay was shortened
        assert total_wait == 9.9  # the same as the deadline

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

    async def _generator_mock(
        self,
        num=5,
        error_on=None,
        exceptions_seen=None,
        sleep_time=0,
        ignore_sent=False,
    ):
        """
        Helper to create a mock generator that yields a number of values
        Generator can optionally raise an exception on a specific iteration
        """
        try:
            sent_in = None
            for i in range(num):
                if sleep_time:
                    await asyncio.sleep(sleep_time)
                if error_on and i == error_on:
                    raise ValueError("generator mock error")

                sent_in = yield (sent_in if sent_in else i)
                if ignore_sent:
                    sent_in = None
        except (Exception, BaseException, GeneratorExit) as e:
            # keep track of exceptions seen by generator
            if exceptions_seen is not None:
                exceptions_seen.append(e)
            raise

    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___generator_success(self, sleep):
        """
        Test that a retry-decorated generator yields values as expected
        This test checks a generator with no issues
        """
        from collections.abc import AsyncGenerator

        retry_ = retry_async.AsyncRetry(is_stream=True)

        decorated = retry_(self._generator_mock)

        num = 10
        generator = decorated(num)
        # check types
        assert isinstance(decorated(num), AsyncGenerator)
        assert isinstance(self._generator_mock(num), AsyncGenerator)
        # check yield contents
        unpacked = [i async for i in generator]
        assert len(unpacked) == num
        expected = [i async for i in self._generator_mock(num)]
        for a, b in zip(unpacked, expected):
            assert a == b
        sleep.assert_not_called()

    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___generator_retry(self, sleep):
        """
        Tests that a retry-decorated generator will retry on errors
        """
        on_error = mock.Mock(return_value=None)
        retry_ = retry_async.AsyncRetry(
            on_error=on_error,
            predicate=retry_async.if_exception_type(ValueError),
            is_stream=True,
            timeout=None,
        )
        generator = retry_(self._generator_mock)(error_on=3)
        # error thrown on 3
        # generator should contain 0, 1, 2 looping
        unpacked = [await generator.__anext__() for i in range(10)]
        assert unpacked == [0, 1, 2, 0, 1, 2, 0, 1, 2, 0]
        assert on_error.call_count == 3

    @mock.patch("random.uniform", autospec=True, side_effect=lambda m, n: n)
    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___generator_retry_hitting_deadline(self, sleep, uniform):
        """
        Tests that a retry-decorated generator will throw a RetryError
        after using the time budget
        """
        import time

        on_error = mock.Mock()
        retry_ = retry_async.AsyncRetry(
            predicate=retry_async.if_exception_type(ValueError),
            initial=1.0,
            maximum=1024.0,
            multiplier=2.0,
            deadline=9.9,
            is_stream=True,
        )

        time_now = time.monotonic()
        now_patcher = mock.patch(
            "time.monotonic",
            return_value=time_now,
        )

        decorated = retry_(self._generator_mock, on_error=on_error)
        generator = decorated(error_on=1)

        with now_patcher as patched_now:
            # Make sure that calls to fake asyncio.sleep() also advance the mocked
            # time clock.
            def increase_time(sleep_delay):
                patched_now.return_value += sleep_delay

            sleep.side_effect = increase_time

            with pytest.raises(exceptions.RetryError):
                [i async for i in generator]

        assert on_error.call_count == 4
        # check the delays
        assert sleep.call_count == 3  # once between each successive target calls
        last_wait = sleep.call_args.args[0]
        total_wait = sum(call_args.args[0] for call_args in sleep.call_args_list)
        # next wait would have put us over, so ended early
        assert last_wait == 4
        assert total_wait == 7

    @pytest.mark.asyncio
    async def test___call___generator_cancellations(self):
        """
        cancel calls should propagate to the generator
        """
        # test without cancel as retryable
        retry_ = retry_async.AsyncRetry(is_stream=True)
        utcnow = datetime.datetime.utcnow()
        mock.patch("google.api_core.datetime_helpers.utcnow", return_value=utcnow)
        generator = retry_(self._generator_mock)(sleep_time=0.2)
        await generator.__anext__() == 0
        task = asyncio.create_task(generator.__anext__())
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(StopAsyncIteration):
            await generator.__anext__()

    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___with_generator_send(self, sleep):
        """
        Send should be passed through retry into target generator
        """
        retry_ = retry_async.AsyncRetry(is_stream=True)

        decorated = retry_(self._generator_mock)

        generator = decorated(10)
        result = await generator.__anext__()
        assert result == 0
        in_messages = ["test_1", "hello", "world"]
        out_messages = []
        for msg in in_messages:
            recv = await generator.asend(msg)
            out_messages.append(recv)
        assert in_messages == out_messages
        assert await generator.__anext__() == 4
        assert await generator.__anext__() == 5

    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___generator_send_retry(self, sleep):
        """
        Send should be retried if target generator raises an error
        """
        on_error = mock.Mock(return_value=None)
        retry_ = retry_async.AsyncRetry(
            on_error=on_error,
            predicate=retry_async.if_exception_type(ValueError),
            is_stream=True,
            timeout=None,
        )
        generator = retry_(self._generator_mock)(error_on=3, ignore_sent=True)
        with pytest.raises(TypeError) as exc_info:
            await generator.asend("can not send to fresh generator")
            assert exc_info.match("can't send non-None value")

        # error thrown on 3
        # generator should contain 0, 1, 2 looping
        generator = retry_(self._generator_mock)(error_on=3, ignore_sent=True)
        assert await generator.__anext__() == 0
        unpacked = [await generator.asend(i) for i in range(10)]
        assert unpacked == [1, 2, 0, 1, 2, 0, 1, 2, 0, 1]
        assert on_error.call_count == 3

    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___with_generator_close(self, sleep):
        """
        Close should be passed through retry into target generator
        """
        retry_ = retry_async.AsyncRetry(is_stream=True)
        decorated = retry_(self._generator_mock)
        exception_list = []
        generator = decorated(10, exceptions_seen=exception_list)
        for i in range(2):
            await generator.__anext__()
        await generator.aclose()

        assert isinstance(exception_list[0], GeneratorExit)
        with pytest.raises(StopAsyncIteration):
            # calling next on closed generator should raise error
            await generator.__anext__()

    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___with_new_generator_close(self, sleep):
        """
        Close should be passed through retry into target generator,
        even when it hasn't been iterated yet
        """
        retry_ = retry_async.AsyncRetry(is_stream=True)
        decorated = retry_(self._generator_mock)
        exception_list = []
        generator = decorated(10, exceptions_seen=exception_list)
        await generator.aclose()

        with pytest.raises(StopAsyncIteration):
            # calling next on closed generator should raise error
            await generator.__anext__()

    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___with_generator_throw(self, sleep):
        """
        Throw should be passed through retry into target generator
        """
        retry_ = retry_async.AsyncRetry(
            predicate=retry_async.if_exception_type(ValueError),
            is_stream=True,
        )
        decorated = retry_(self._generator_mock)
        exception_list = []
        generator = decorated(10, exceptions_seen=exception_list)
        for i in range(2):
            await generator.__anext__()
        with pytest.raises(BufferError):
            await generator.athrow(BufferError("test"))
        assert isinstance(exception_list[0], BufferError)
        with pytest.raises(StopAsyncIteration):
            # calling next on closed generator should raise error
            await generator.__anext__()
        # should retry if throw retryable exception
        exception_list = []
        generator = decorated(10, exceptions_seen=exception_list)
        for i in range(2):
            await generator.__anext__()
        throw_val = await generator.athrow(ValueError("test"))
        assert throw_val == 0
        assert isinstance(exception_list[0], ValueError)
        # calling next on closed generator should not raise error
        assert await generator.__anext__() == 1

    @pytest.mark.parametrize("awaitale_wrapped", [True, False])
    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___with_iterable_send(self, sleep, awaitale_wrapped):
        """
        Send should work like next if the wrapped iterable does not support it
        """
        retry_ = retry_async.AsyncRetry(is_stream=True)

        def iterable_fn():
            class CustomIterable:
                def __init__(self):
                    self.i = -1

                def __aiter__(self):
                    return self

                async def __anext__(self):
                    self.i += 1
                    return self.i

            return CustomIterable()

        if awaitale_wrapped:

            async def wrapper():
                return iterable_fn()

            decorated = retry_(wrapper)
        else:
            decorated = retry_(iterable_fn)

        retryable = decorated()
        result = await retryable.__anext__()
        assert result == 0
        await retryable.asend("test") == 1
        await retryable.asend("test2") == 2
        await retryable.asend("test3") == 3

    @pytest.mark.parametrize("awaitale_wrapped", [True, False])
    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___with_iterable_close(self, sleep, awaitale_wrapped):
        """
        close should be handled by wrapper if wrapped iterable does not support it
        """
        retry_ = retry_async.AsyncRetry(is_stream=True)

        def iterable_fn():
            class CustomIterable:
                def __init__(self):
                    self.i = -1

                def __aiter__(self):
                    return self

                async def __anext__(self):
                    self.i += 1
                    return self.i

            return CustomIterable()

        if awaitale_wrapped:

            async def wrapper():
                return iterable_fn()

            decorated = retry_(wrapper)
        else:
            decorated = retry_(iterable_fn)

        # try closing active generator
        retryable = decorated()
        assert await retryable.__anext__() == 0
        await retryable.aclose()
        with pytest.raises(StopAsyncIteration):
            await retryable.__anext__()
        # try closing new generator
        new_retryable = decorated()
        await new_retryable.aclose()
        with pytest.raises(StopAsyncIteration):
            await new_retryable.__anext__()

    @pytest.mark.parametrize("awaitale_wrapped", [True, False])
    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___with_iterable_throw(self, sleep, awaitale_wrapped):
        """
        Throw should work even if the wrapped iterable does not support it
        """

        predicate = retry_async.if_exception_type(ValueError)
        retry_ = retry_async.AsyncRetry(is_stream=True, predicate=predicate)

        def iterable_fn():
            class CustomIterable:
                def __init__(self):
                    self.i = -1

                def __aiter__(self):
                    return self

                async def __anext__(self):
                    self.i += 1
                    return self.i

            return CustomIterable()

        if awaitale_wrapped:

            async def wrapper():
                return iterable_fn()

            decorated = retry_(wrapper)
        else:
            decorated = retry_(iterable_fn)

        # try throwing with active generator
        retryable = decorated()
        assert await retryable.__anext__() == 0
        # should swallow errors in predicate
        await retryable.athrow(ValueError("test"))
        # should raise errors not in predicate
        with pytest.raises(BufferError):
            await retryable.athrow(BufferError("test"))
        with pytest.raises(StopAsyncIteration):
            await retryable.__anext__()
        # try throwing with new generator
        new_retryable = decorated()
        with pytest.raises(BufferError):
            await new_retryable.athrow(BufferError("test"))
        with pytest.raises(StopAsyncIteration):
            await new_retryable.__anext__()

    @pytest.mark.asyncio
    async def test_exc_factory_non_retryable_error(self):
        """
        generator should give the option to override exception creation logic
        test when non-retryable error is thrown
        """
        from google.api_core.retry_streaming_async import retry_target_stream

        timeout = 6
        sent_errors = [ValueError("test"), ValueError("test2"), BufferError("test3")]
        expected_final_err = RuntimeError("done")
        expected_source_err = ZeroDivisionError("test4")

        def factory(*args, **kwargs):
            assert len(args) == 0
            assert kwargs["exc_list"] == sent_errors
            assert kwargs["is_timeout"] is False
            assert kwargs["timeout_val"] == timeout
            return expected_final_err, expected_source_err

        generator = retry_target_stream(
            self._generator_mock,
            retry_async.if_exception_type(ValueError),
            [0] * 3,
            timeout=timeout,
            exception_factory=factory,
        )
        # initialize the generator
        await generator.__anext__()
        # trigger some retryable errors
        await generator.athrow(sent_errors[0])
        await generator.athrow(sent_errors[1])
        # trigger a non-retryable error
        with pytest.raises(expected_final_err.__class__) as exc_info:
            await generator.athrow(sent_errors[2])
        assert exc_info.value == expected_final_err
        assert exc_info.value.__cause__ == expected_source_err

    @pytest.mark.asyncio
    async def test_exc_factory_timeout(self):
        """
        generator should give the option to override exception creation logic
        test when timeout is exceeded
        """
        import time
        from google.api_core.retry_streaming_async import retry_target_stream

        timeout = 2
        time_now = time.monotonic()
        now_patcher = mock.patch(
            "time.monotonic",
            return_value=time_now,
        )

        with now_patcher as patched_now:
            timeout = 2
            sent_errors = [ValueError("test"), ValueError("test2"), ValueError("test3")]
            expected_final_err = RuntimeError("done")
            expected_source_err = ZeroDivisionError("test4")

            def factory(*args, **kwargs):
                assert len(args) == 0
                assert kwargs["exc_list"] == sent_errors
                assert kwargs["is_timeout"] is True
                assert kwargs["timeout_val"] == timeout
                return expected_final_err, expected_source_err

            generator = retry_target_stream(
                self._generator_mock,
                retry_async.if_exception_type(ValueError),
                [0] * 3,
                timeout=timeout,
                exception_factory=factory,
            )
            # initialize the generator
            await generator.__anext__()
            # trigger some retryable errors
            await generator.athrow(sent_errors[0])
            await generator.athrow(sent_errors[1])
            # trigger a timeout
            patched_now.return_value += timeout + 1
            with pytest.raises(expected_final_err.__class__) as exc_info:
                await generator.athrow(sent_errors[2])
            assert exc_info.value == expected_final_err
            assert exc_info.value.__cause__ == expected_source_err
