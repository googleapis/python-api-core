# Copyright 2025 Google LLC
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

"""
Test for exception chain preservation bug in retry mechanism.

This test demonstrates that the retry mechanism should preserve explicit
exception chaining (raise ... from ...) when re-raising non-retryable errors.
"""

import pytest

from google.api_core import exceptions
from google.api_core import retry_async


class CustomApplicationError(Exception):
    """Custom exception for testing exception chaining."""
    pass


@pytest.mark.asyncio
async def test_exception_chain_preserved_with_retry_decorator():
    """
    Test that explicit exception chaining is preserved when a non-retryable
    exception is raised through the retry mechanism.

    This test will FAIL with the current bug because __cause__ is cleared
    when the retry mechanism re-raises with "raise final_exc from None".

    This test will PASS once the bug is fixed to preserve __cause__.
    """
    # Create a decorated async function that raises a chained exception
    @retry_async.AsyncRetry(
        predicate=retry_async.if_exception_type(exceptions.InternalServerError),
        initial=0.1,
        multiplier=1,
        maximum=0.2
    )
    async def function_with_chained_exception():
        """Function that raises a non-retryable exception with explicit chaining."""
        try:
            # Raise the original exception (this would be retryable, but we catch it)
            raise exceptions.Unauthenticated("401 Invalid authentication credentials")
        except exceptions.Unauthenticated as original_exc:
            # Raise a non-retryable exception with explicit chaining
            # The retry decorator only retries InternalServerError, so this will
            # be immediately re-raised as non-retryable
            raise CustomApplicationError("Access denied due to authentication failure") from original_exc

    # Execute the function and catch the exception
    with pytest.raises(CustomApplicationError) as exc_info:
        await function_with_chained_exception()

    caught_exception = exc_info.value

    # Assert that the exception chain is preserved
    # BUG: With the current implementation, __cause__ will be None
    # FIX: Once fixed, __cause__ should point to the Unauthenticated exception
    assert caught_exception.__cause__ is not None, (
        "Exception chain was lost! The __cause__ should be preserved when "
        "re-raising non-retryable exceptions through the retry mechanism."
    )

    assert isinstance(caught_exception.__cause__, exceptions.Unauthenticated), (
        f"Expected __cause__ to be Unauthenticated, got {type(caught_exception.__cause__)}"
    )

    assert "Invalid authentication credentials" in str(caught_exception.__cause__), (
        f"Expected original exception message in: {str(caught_exception.__cause__)}"
    )


@pytest.mark.asyncio
async def test_exception_chain_preserved_without_retry_decorator():
    """
    Control test: verify that exception chaining works correctly WITHOUT
    the retry decorator.

    This test should PASS both before and after the fix, demonstrating
    that the issue is specific to the retry mechanism.
    """
    async def function_without_retry():
        """Function without retry decorator - exception chain should work normally."""
        try:
            raise exceptions.Unauthenticated("401 Invalid authentication credentials")
        except exceptions.Unauthenticated as original_exc:
            raise CustomApplicationError("Access denied due to authentication failure") from original_exc

    with pytest.raises(CustomApplicationError) as exc_info:
        await function_without_retry()

    caught_exception = exc_info.value

    # This should always pass - exception chaining works normally without retry
    assert caught_exception.__cause__ is not None
    assert isinstance(caught_exception.__cause__, exceptions.Unauthenticated)
    assert "Invalid authentication credentials" in str(caught_exception.__cause__)


@pytest.mark.asyncio
async def test_nested_exception_chain_preserved():
    """
    Test that deeply nested exception chains are preserved.

    This tests a more complex scenario where there are multiple levels
    of exception chaining: A -> B -> C
    """
    @retry_async.AsyncRetry(
        predicate=retry_async.if_exception_type(exceptions.InternalServerError),
        initial=0.1,
        multiplier=1,
        maximum=0.2
    )
    async def function_with_nested_chain():
        """Function with multiple levels of exception chaining."""
        try:
            try:
                # Level 1: Original error
                raise ValueError("Invalid configuration value")
            except ValueError as level1_exc:
                # Level 2: Wrap in auth error
                raise exceptions.Unauthenticated("Auth failed") from level1_exc
        except exceptions.Unauthenticated as level2_exc:
            # Level 3: Wrap in custom error (non-retryable)
            raise CustomApplicationError("Application error") from level2_exc

    with pytest.raises(CustomApplicationError) as exc_info:
        await function_with_nested_chain()

    caught_exception = exc_info.value

    # Assert the immediate cause is preserved
    assert caught_exception.__cause__ is not None, (
        "First level of exception chain was lost"
    )
    assert isinstance(caught_exception.__cause__, exceptions.Unauthenticated)

    # Assert the nested cause is also preserved
    assert caught_exception.__cause__.__cause__ is not None, (
        "Nested exception chain was lost"
    )
    assert isinstance(caught_exception.__cause__.__cause__, ValueError)
    assert str(caught_exception.__cause__.__cause__) == "Invalid configuration value"
