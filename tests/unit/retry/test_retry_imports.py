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

def test_legacy_imports_retry_unary_sync():
    # TODO: Delete this test when when we revert these imports on the
    #       next major version release
    #       (https://github.com/googleapis/python-api-core/issues/576)

    from google.api_core.retry import logging
    from google.api_core.retry import datetime  # noqa: F401
    from google.api_core.retry import functools  # noqa: F401
    from google.api_core.retry import logging  # noqa: F401
    from google.api_core.retry import random  # noqa: F401
    from google.api_core.retry import sys  # noqa: F401
    from google.api_core.retry import time  # noqa: F401
    from google.api_core.retry import inspect  # noqa: F401
    from google.api_core.retry import warnings  # noqa: F401
    from google.api_core.retry import Any, Callable, TypeVar, TYPE_CHECKING  # noqa: F401

    from google.api_core.retry import datetime_helpers  # noqa: F401
    from google.api_core.retry import exceptions  # noqa: F401
    from google.api_core.retry import auth_exceptions  # noqa: F401

    ### FIXME: How do we test the following, and how do we import it in __init__.py?
    # import google.api_core.retry.requests.exceptions


def test_legacy_imports_retry_unary_async():
    # TODO: Delete this test when when we revert these imports on the
    #       next major version release
    #       (https://github.com/googleapis/python-api-core/issues/576)

    from google.api_core import retry_async  # noqa: F401

    ### FIXME: each of the following cause errors on the "retry_async" part: module not found
    # import google.api_core.retry_async.functools
    # from google.api_core.retry_async import functools
    #
    ## For the above, I tried the following in api_core/__init__.py
    ## and none made the above statements pass:
    #  from google.api_core.retry import retry_unary_async as retry_async
    #  import google.api_core.retry.retry_unary_async as retry_async
