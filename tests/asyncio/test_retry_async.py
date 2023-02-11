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
import inspect
import functools

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

    async def _generator_mock(self, num=5, error_on=None, exceptions_seen=None):
        try:
            sent_in = None
            for i in range(num):
                if error_on and i == error_on:
                    raise ValueError("generator mock error")
                sent_in = yield (sent_in if sent_in else i)
        except (Exception, BaseException, GeneratorExit) as e:
            # keep track of exceptions seen by generator
            if exceptions_seen is not None:
                exceptions_seen.append(e)
            raise

    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___generator_success(self, sleep):
        retry_ = retry_async.AsyncRetry()

        decorated = retry_(self._generator_mock)

        num = 10
        generator = decorated(num)
        # check types
        assert inspect.isasyncgen(generator)
        assert type(decorated(num)) == type(self._generator_mock(num))
        # check yield contents
        unpacked = [i async for i in generator]
        assert len(unpacked) == num
        expected = [i async for i in self._generator_mock(num)]
        for a,b in zip(unpacked, expected):
            assert a == b
        sleep.assert_not_called()


    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___generator_retry(self, sleep):
        on_error = mock.Mock()
        retry_ = retry_async.AsyncRetry(on_error=on_error, predicate=retry_async.if_exception_type(ValueError))
        generator = retry_(self._generator_mock)(error_on=3)
        assert inspect.isasyncgen(generator)
        # error thrown on 3
        # generator should contain 0, 1, 2 looping
        unpacked = [await anext(generator) for i in range(10)]
        assert unpacked == [0,1,2,0,1,2,0,1,2,0]
        assert on_error.call_count==3

    @mock.patch("random.uniform", autospec=True, side_effect=lambda m, n: n)
    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___generator_retry_hitting_deadline(self, sleep, uniform):
        on_error = mock.Mock()
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

        decorated = retry_(self._generator_mock, on_error=on_error)
        generator = decorated(error_on=1)

        with utcnow_patcher as patched_utcnow:
            # Make sure that calls to fake asyncio.sleep() also advance the mocked
            # time clock.
            def increase_time(sleep_delay):
                patched_utcnow.return_value += datetime.timedelta(seconds=sleep_delay)

            sleep.side_effect = increase_time

            with pytest.raises(exceptions.RetryError):
                unpacked = [i async for i in generator]

        assert on_error.call_count == 5

        # check the delays
        assert sleep.call_count == 4  # once between each successive target calls
        last_wait = sleep.call_args.args[0]
        total_wait = sum(call_args.args[0] for call_args in sleep.call_args_list)

        assert last_wait == 2.9  # and not 8.0, because the last delay was shortened
        assert total_wait == 9.9  # the same as the deadline

    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___with_generator_close(self, sleep):
        retry_ = retry_async.AsyncRetry()
        decorated = retry_(self._generator_mock)
        exception_list = []
        generator = decorated(10, exceptions_seen=exception_list)
        for i in range(2):
            await anext(generator)
        await generator.aclose()

        assert isinstance(exception_list[0], GeneratorExit)
        assert generator.ag_running == False
        with pytest.raises(StopAsyncIteration):
            # calling next on closed generator should raise error
            await anext(generator)

    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___with_generator_throw(self, sleep):
        retry_ = retry_async.AsyncRetry(predicate=retry_async.if_exception_type(ValueError))
        decorated = retry_(self._generator_mock)
        exception_list = []
        generator = decorated(10, exceptions_seen=exception_list)
        for i in range(2):
            await anext(generator)
        with pytest.raises(BufferError):
            await generator.athrow(BufferError("test"))
        assert isinstance(exception_list[0], BufferError)
        with pytest.raises(StopAsyncIteration):
            # calling next on closed generator should raise error
            await anext(generator)
        # should retry if throw retryable exception
        exception_list = []
        generator = decorated(10, exceptions_seen=exception_list)
        for i in range(2):
            await anext(generator)
        throw_val = await generator.athrow(ValueError("test"))
        assert throw_val == 0
        assert isinstance(exception_list[0], ValueError)
        # calling next on closed generator should not raise error
        assert await anext(generator) == 1

    @mock.patch("asyncio.sleep", autospec=True)
    @pytest.mark.asyncio
    async def test___call___with_is_generator(self, sleep):
        gen_retry_ = retry_async.AsyncRetry(is_generator=True, predicate=retry_async.if_exception_type(ValueError))
        not_gen_retry_ = retry_async.AsyncRetry(is_generator=False, predicate=retry_async.if_exception_type(ValueError))
        auto_retry_ = retry_async.AsyncRetry(predicate=retry_async.if_exception_type(ValueError))
        # force generator to act as non-generator
        with pytest.raises(TypeError):
            # error will be thrown because gen is coroutine
            gen = not_gen_retry_(self._generator_mock)(10, error_on=3)
            unpacked = [await anext(gen) for i in range(10)]
        # wrapped generators won't be detected as generator functions
        wrapped = functools.partial(self._generator_mock, 10, error_on=6)
        assert not inspect.isasyncgenfunction(wrapped)
        with pytest.raises(TypeError):
            # error will be thrown because gen is coroutine
            gen = auto_retry_(wrapped)()
            unpacked = [next(gen) for i in range(10)]
        # force non-detected to be accepted as generator
        gen = gen_retry_(wrapped)()
        unpacked = [await anext(gen) for i in range(10)]
        assert unpacked == [0,1,2,3,4,5,0,1,2,3]

