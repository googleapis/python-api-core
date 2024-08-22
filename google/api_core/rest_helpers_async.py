# Copyright 2024 Google LLC
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

"""AsyncIO helpers for :mod:`rest` supporting 3.7+.
"""


import functools

import google.auth
from google.api_core import exceptions



class _RestCall():
    """Wrapped Rest Call to map exceptions."""

    def __init__(self):
        self._call = None

    def with_call(self, call):
        """Supplies the call object separately to keep __init__ clean."""
        self._call = call
        return self
    
    async def __call__(self):
        try:
            return await self._call
        except google.auth.exceptions.TransportError as rpc_exc:
            raise exceptions.GoogleAPICallError(str(rpc_exc), errors=(rpc_exc,), response=rpc_exc)


def wrap_errors(callable_):
    """Map errors for REST async callables."""

    @functools.wraps(callable_)
    async def error_remapped_callable(*args, **kwargs):
        call = callable_(*args, **kwargs)
        call = _RestCall().with_call(call)
        response = await call()
        return response

    return error_remapped_callable
