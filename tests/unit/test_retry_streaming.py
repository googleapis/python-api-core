# Copyright 2017 Google LLC
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
from google.api_core import retry
from google.api_core import retry_streaming


class TestStreamingRetry(object):
    def test_constructor_defaults(self):
        retry_ = retry_streaming.StreamingRetry()
        assert retry_._predicate == retry.if_transient_error
        assert retry_._initial == 1
        assert retry_._maximum == 60
        assert retry_._multiplier == 2
        assert retry_._deadline == 120
        assert retry_._on_error is None
        assert retry_.deadline == 120
        assert retry_.timeout == 120

    def test_constructor_options(self):
        _some_function = mock.Mock()

        retry_ = retry_streaming.StreamingRetry(
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
        retry_ = retry_streaming.StreamingRetry(
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
        retry_ = retry_streaming.StreamingRetry(
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
        retry_ = retry_streaming.StreamingRetry(
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
        retry_ = retry_streaming.StreamingRetry(
            predicate=mock.sentinel.predicate,
            initial=1,
            maximum=2,
            multiplier=3,
            deadline=4,
            on_error=mock.sentinel.on_error,
        )
        new_retry = retry_.with_delay(initial=5, maximum=6, multiplier=7)
        assert retry_ is not new_retry
        assert new_retry._initial == 5
        assert new_retry._maximum == 6
        assert new_retry._multiplier == 7

        # the rest of the attributes should remain the same
        assert new_retry._deadline == retry_._deadline
        assert new_retry._predicate is retry_._predicate
        assert new_retry._on_error is retry_._on_error

    def test_with_delay_partial_options(self):
        retry_ = retry_streaming.StreamingRetry(
            predicate=mock.sentinel.predicate,
            initial=1,
            maximum=2,
            multiplier=3,
            deadline=4,
            on_error=mock.sentinel.on_error,
        )
        new_retry = retry_.with_delay(initial=4)
        assert retry_ is not new_retry
        assert new_retry._initial == 4
        assert new_retry._maximum == 2
        assert new_retry._multiplier == 3

        new_retry = retry_.with_delay(maximum=4)
        assert retry_ is not new_retry
        assert new_retry._initial == 1
        assert new_retry._maximum == 4
        assert new_retry._multiplier == 3

        new_retry = retry_.with_delay(multiplier=4)
        assert retry_ is not new_retry
        assert new_retry._initial == 1
        assert new_retry._maximum == 2
        assert new_retry._multiplier == 4

        # the rest of the attributes should remain the same
        assert new_retry._deadline == retry_._deadline
        assert new_retry._predicate is retry_._predicate
        assert new_retry._on_error is retry_._on_error

    def test___str__(self):
        def if_exception_type(exc):
            return bool(exc)  # pragma: NO COVER

        # Explicitly set all attributes as changed Retry defaults should not
        # cause this test to start failing.
        retry_ = retry_streaming.StreamingRetry(
            predicate=if_exception_type,
            initial=1.0,
            maximum=60.0,
            multiplier=2.0,
            deadline=120.0,
            on_error=None,
        )
        assert re.match(
            (
                r"<StreamingRetry predicate=<function.*?if_exception_type.*?>, "
                r"initial=1.0, maximum=60.0, multiplier=2.0, timeout=120.0, "
                r"on_error=None>"
            ),
            str(retry_),
        )

    def _generator_mock(
        self,
        num=5,
        error_on=None,
        return_val=None,
        exceptions_seen=None,
    ):
        """
        Helper to create a mock generator that yields a number of values
        Generator can optionally raise an exception on a specific iteration

        Args:
          - num (int): the number of values to yield. After this, the generator will return `return_val`
          - error_on (int): if given, the generator will raise a ValueError on the specified iteration
          - return_val (any): if given, the generator will return this value after yielding num values
          - exceptions_seen (list): if given, the generator will append any exceptions to this list before raising
        """
        try:
            for i in range(num):
                if error_on and i == error_on:
                    raise ValueError("generator mock error")
                yield i
            return return_val
        except (Exception, BaseException, GeneratorExit) as e:
            # keep track of exceptions seen by generator
            if exceptions_seen is not None:
                exceptions_seen.append(e)
            raise

    @mock.patch("time.sleep", autospec=True)
    def test___call___success(self, sleep):
        """
        Test that a retry-decorated generator yields values as expected
        This test checks a generator with no issues
        """
        import types
        import collections

        retry_ = retry_streaming.StreamingRetry()

        decorated = retry_(self._generator_mock)

        num = 10
        result = decorated(num)
        # check types
        assert isinstance(decorated(num), collections.abc.Iterable)
        assert isinstance(decorated(num), types.GeneratorType)
        assert isinstance(self._generator_mock(num), collections.abc.Iterable)
        assert isinstance(self._generator_mock(num), types.GeneratorType)
        # check yield contents
        unpacked = [i for i in result]
        assert len(unpacked) == num
        for a, b in zip(unpacked, self._generator_mock(num)):
            assert a == b
        sleep.assert_not_called()

    @mock.patch("time.sleep", autospec=True)
    def test___call___retry(self, sleep):
        """
        Tests that a retry-decorated generator will retry on errors
        """
        on_error = mock.Mock(return_value=None)
        retry_ = retry_streaming.StreamingRetry(
            on_error=on_error,
            predicate=retry.if_exception_type(ValueError),
            timeout=None,
        )
        result = retry_(self._generator_mock)(error_on=3)
        # error thrown on 3
        # generator should contain 0, 1, 2 looping
        unpacked = [next(result) for i in range(10)]
        assert unpacked == [0, 1, 2, 0, 1, 2, 0, 1, 2, 0]
        assert on_error.call_count == 3

    @mock.patch("random.uniform", autospec=True, side_effect=lambda m, n: n)
    @mock.patch("time.sleep", autospec=True)
    def test___call___retry_hitting_deadline(self, sleep, uniform):
        """
        Tests that a retry-decorated generator will throw a RetryError
        after using the time budget
        """
        import time

        on_error = mock.Mock(return_value=None)
        retry_ = retry_streaming.StreamingRetry(
            predicate=retry.if_exception_type(ValueError),
            initial=1.0,
            maximum=1024.0,
            multiplier=2.0,
            deadline=30.9,
        )

        timenow = time.monotonic()
        now_patcher = mock.patch(
            "time.monotonic",
            return_value=timenow,
        )

        decorated = retry_(self._generator_mock, on_error=on_error)
        generator = decorated(error_on=1)
        with now_patcher as patched_now:
            # Make sure that calls to fake time.sleep() also advance the mocked
            # time clock.
            def increase_time(sleep_delay):
                patched_now.return_value += sleep_delay

            sleep.side_effect = increase_time
            with pytest.raises(exceptions.RetryError):
                [i for i in generator]

        assert on_error.call_count == 5
        # check the delays
        assert sleep.call_count == 4  # once between each successive target calls
        last_wait = sleep.call_args.args[0]
        total_wait = sum(call_args.args[0] for call_args in sleep.call_args_list)
        assert last_wait == 8.0
        assert total_wait == 15.0

    @mock.patch("time.sleep", autospec=True)
    def test___call___with_generator_send(self, sleep):
        """
        Send should be passed through retry into target generator
        """

        def _mock_send_gen():
            """
            always yield whatever was sent in
            """
            in_ = yield
            while True:
                in_ = yield in_

        retry_ = retry_streaming.StreamingRetry()

        decorated = retry_(_mock_send_gen)

        generator = decorated()
        result = next(generator)
        # first yield should be None
        assert result is None
        in_messages = ["test_1", "hello", "world"]
        out_messages = []
        for msg in in_messages:
            recv = generator.send(msg)
            out_messages.append(recv)
        assert in_messages == out_messages

    @mock.patch("time.sleep", autospec=True)
    def test___call___with_generator_send_retry(self, sleep):
        """
        Send should support retries like next
        """
        on_error = mock.Mock(return_value=None)
        retry_ = retry_streaming.StreamingRetry(
            on_error=on_error,
            predicate=retry.if_exception_type(ValueError),
            timeout=None,
        )
        result = retry_(self._generator_mock)(error_on=3)
        with pytest.raises(TypeError) as exc_info:
            result.send("can not send to fresh generator")
            assert exc_info.match("can't send non-None value")
        # initiate iteration with None
        result = retry_(self._generator_mock)(error_on=3)
        assert result.send(None) == 0
        # error thrown on 3
        # generator should contain 0, 1, 2 looping
        unpacked = [result.send(i) for i in range(10)]
        assert unpacked == [1, 2, 0, 1, 2, 0, 1, 2, 0, 1]
        assert on_error.call_count == 3

    @mock.patch("time.sleep", autospec=True)
    def test___call___with_iterable_send(self, sleep):
        """
        send should raise attribute error if wrapped iterator does not support it
        """
        retry_ = retry_streaming.StreamingRetry()

        def iterable_fn(n):
            return iter(range(n))

        decorated = retry_(iterable_fn)
        generator = decorated(5)
        # initialize
        next(generator)
        # call send
        with pytest.raises(AttributeError):
            generator.send("test")

    @mock.patch("time.sleep", autospec=True)
    def test___call___with_iterable_close(self, sleep):
        """
        close should be handled by wrapper if wrapped iterable does not support it
        """
        retry_ = retry_streaming.StreamingRetry()

        def iterable_fn(n):
            return iter(range(n))

        decorated = retry_(iterable_fn)

        # try closing active generator
        retryable = decorated(10)
        assert next(retryable) == 0
        retryable.close()
        with pytest.raises(StopIteration):
            next(retryable)

        # try closing a new generator
        retryable = decorated(10)
        retryable.close()
        with pytest.raises(StopIteration):
            next(retryable)

    @mock.patch("time.sleep", autospec=True)
    def test___call___with_iterable_throw(self, sleep):
        """
        Throw should work even if the wrapped iterable does not support it
        """
        predicate = retry.if_exception_type(ValueError)
        retry_ = retry_streaming.StreamingRetry(predicate=predicate)

        def iterable_fn(n):
            return iter(range(n))

        decorated = retry_(iterable_fn)

        # try throwing with active generator
        retryable = decorated(10)
        assert next(retryable) == 0
        # should swallow errors in predicate
        retryable.throw(ValueError)
        assert next(retryable) == 1
        # should raise on other errors
        with pytest.raises(TypeError):
            retryable.throw(TypeError)
        with pytest.raises(StopIteration):
            next(retryable)

        # try throwing with a new generator
        retryable = decorated(10)
        with pytest.raises(ValueError):
            retryable.throw(ValueError)
        with pytest.raises(StopIteration):
            next(retryable)

    @mock.patch("time.sleep", autospec=True)
    def test___call___with_generator_return(self, sleep):
        """
        Generator return value should be passed through retry decorator
        """
        retry_ = retry_streaming.StreamingRetry()

        decorated = retry_(self._generator_mock)

        expected_value = "done"
        generator = decorated(5, return_val=expected_value)
        found_value = None
        try:
            while True:
                next(generator)
        except StopIteration as e:
            found_value = e.value
        assert found_value == expected_value

    @mock.patch("time.sleep", autospec=True)
    def test___call___with_generator_close(self, sleep):
        """
        Close should be passed through retry into target generator
        """
        retry_ = retry_streaming.StreamingRetry()

        decorated = retry_(self._generator_mock)

        exception_list = []
        generator = decorated(10, exceptions_seen=exception_list)
        for i in range(2):
            next(generator)
        generator.close()
        assert isinstance(exception_list[0], GeneratorExit)
        with pytest.raises(StopIteration):
            # calling next on closed generator should raise error
            next(generator)

    @mock.patch("time.sleep", autospec=True)
    def test___call___with_generator_throw(self, sleep):
        """
        Throw should be passed through retry into target generator
        """
        retry_ = retry_streaming.StreamingRetry(
            predicate=retry.if_exception_type(ValueError),
        )
        decorated = retry_(self._generator_mock)

        exception_list = []
        generator = decorated(10, exceptions_seen=exception_list)
        for i in range(2):
            next(generator)
        with pytest.raises(BufferError):
            generator.throw(BufferError("test"))
        assert isinstance(exception_list[0], BufferError)
        with pytest.raises(StopIteration):
            # calling next on closed generator should raise error
            next(generator)
        # should retry if throw retryable exception
        exception_list = []
        generator = decorated(10, exceptions_seen=exception_list)
        for i in range(2):
            next(generator)
        val = generator.throw(ValueError("test"))
        assert val == 0
        assert isinstance(exception_list[0], ValueError)
        # calling next on closed generator should not raise error
        assert next(generator) == 1

    def test_exc_factory_non_retryable_error(self):
        """
        generator should give the option to override exception creation logic
        test when non-retryable error is thrown
        """
        from google.api_core.retry import RetryFailureReason
        from google.api_core.retry_streaming import retry_target_stream

        timeout = None
        sent_errors = [ValueError("test"), ValueError("test2"), BufferError("test3")]
        expected_final_err = RuntimeError("done")
        expected_source_err = ZeroDivisionError("test4")

        def factory(*args, **kwargs):
            assert len(kwargs) == 0
            assert args[0] == sent_errors
            assert args[1] == RetryFailureReason.NON_RETRYABLE_ERROR
            assert args[2] == timeout
            return expected_final_err, expected_source_err

        generator = retry_target_stream(
            self._generator_mock,
            retry.if_exception_type(ValueError),
            [0] * 3,
            timeout=timeout,
            exception_factory=factory,
        )
        # initialize generator
        next(generator)
        # trigger some retryable errors
        generator.throw(sent_errors[0])
        generator.throw(sent_errors[1])
        # trigger a non-retryable error
        with pytest.raises(expected_final_err.__class__) as exc_info:
            generator.throw(sent_errors[2])
        assert exc_info.value == expected_final_err
        assert exc_info.value.__cause__ == expected_source_err

    def test_exc_factory_timeout(self):
        """
        generator should give the option to override exception creation logic
        test when timeout is exceeded
        """
        import time
        from google.api_core.retry import RetryFailureReason
        from google.api_core.retry_streaming import retry_target_stream

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
                assert len(kwargs) == 0
                assert args[0] == sent_errors
                assert args[1] == RetryFailureReason.TIMEOUT
                assert args[2] == timeout
                return expected_final_err, expected_source_err

            generator = retry_target_stream(
                self._generator_mock,
                retry.if_exception_type(ValueError),
                [0] * 3,
                timeout=timeout,
                exception_factory=factory,
                check_timeout_on_yield=True,
            )
            # initialize generator
            next(generator)
            # trigger some retryable errors
            generator.throw(sent_errors[0])
            generator.throw(sent_errors[1])
            # trigger a timeout
            patched_now.return_value += timeout + 1
            with pytest.raises(expected_final_err.__class__) as exc_info:
                generator.throw(sent_errors[2])
            assert exc_info.value == expected_final_err
            assert exc_info.value.__cause__ == expected_source_err
