# -*- coding: utf-8 -*-
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
#
from collections import OrderedDict

from .base import OperationsTransport
from .rest import OperationsRestTransport

try:
    from .rest_asyncio import OperationsRestAsyncTransport

    HAS_ASYNC_TRANSPORT = True
except ImportError:
    # This import requires the `async_rest` extra
    # Don't raise an exception if `OperationsRestAsyncTransport` cannot be imported
    # as other transports are still available
    HAS_ASYNC_TRANSPORT = False

# Compile a registry of transports.
_transport_registry = OrderedDict()
_transport_registry["rest"] = OperationsRestTransport

if HAS_ASYNC_TRANSPORT:
    _transport_registry["rest_asyncio"] = OperationsRestAsyncTransport

__all__ = (
    "OperationsTransport",
    "OperationsRestTransport",
    "OperationsRestAsyncTransport",
)
