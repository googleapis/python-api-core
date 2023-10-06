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

"""Helpers for constructing routing headers.

These headers are used by Google infrastructure to determine how to route
requests, especially for services that are regional.

Generally, these headers are specified as gRPC metadata.
"""

import functools
from enum import Enum
from urllib.parse import urlencode

ROUTING_METADATA_KEY = "x-goog-request-params"
# use caching to avoid repeated computation
ROUTING_PARAM_CACHE_SIZE = 32


def to_routing_header(params, qualified_enums=True):
    """Returns a routing header string for the given request parameters.

    Args:
        params (Mapping[str, str | bytes | Enum]): A dictionary containing the request
            parameters used for routing.
        qualified_enums (bool): Whether to represent enum values
            as their type-qualified symbol names instead of as their
            unqualified symbol names.

    Returns:
        str: The routing header string.
    """
    tuples = params.items() if isinstance(params, dict) else params
    if not qualified_enums:
        tuples = [(x[0], x[1].name) if isinstance(x[1], Enum) else x for x in tuples]
    return _urlencode_params(*tuples)


def to_grpc_metadata(params, qualified_enums=True):
    """Returns the gRPC metadata containing the routing headers for the given
    request parameters.

    Args:
        params (Mapping[str, str | bytes | Enum]): A dictionary containing the request
            parameters used for routing.
        qualified_enums (bool): Whether to represent enum values
            as their type-qualified symbol names instead of as their
            unqualified symbol names.

    Returns:
        Tuple(str, str): The gRPC metadata containing the routing header key
            and value.
    """
    return (ROUTING_METADATA_KEY, to_routing_header(params, qualified_enums))


@functools.lru_cache(ROUTING_PARAM_CACHE_SIZE)
def _urlencode_params(*params):
    """Cacheable wrapper over urlencode

    Args:
        *params ([Tuple[str, str | bytes | Enum]): the reqyest parameters
            used for routing.

    Returns:
        str: The routing header string.
    """
    return urlencode(
        params,
        # Per Google API policy (go/api-url-encoding), / is not encoded.
        safe="/",
    )
