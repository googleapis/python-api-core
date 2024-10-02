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

"""Helpers for providing client information.

Client information is used to send information about the calling client,
such as the library and Python version, to API services.
"""

import platform
from typing import Union

from google.api_core import version as api_core_version

_PY_VERSION = platform.python_version()
_API_CORE_VERSION = api_core_version.__version__

_GRPC_VERSION: Union[str, None]

try:
    import grpc

    _GRPC_VERSION = grpc.__version__
except ImportError:  # pragma: NO COVER
    _GRPC_VERSION = None


class ClientInfo(object):
    """Client information used to generate a user-agent for API calls.

    This user-agent information is sent along with API calls to allow the
    receiving service to do analytics on which versions of Python and Google
    libraries are being used.

    Args:
        python_version (str): The Python interpreter version, for example,
            ``'3.9.6'``.
        grpc_version (Optional[str]): The gRPC library version.
        api_core_version (str): The google-api-core library version.
        gapic_version (Optional[str]): The version of gapic-generated client
            library, if the library was generated by gapic.
        client_library_version (Optional[str]): The version of the client
            library, generally used if the client library was not generated
            by gapic or if additional functionality was built on top of
            a gapic client library.
        user_agent (Optional[str]): Prefix to the user agent header. This is
            used to supply information such as application name or partner tool.
            Recommended format: ``application-or-tool-ID/major.minor.version``.
        rest_version (Optional[str]): The google-auth or requests library version.
    """

    def __init__(
        self,
        python_version=_PY_VERSION,
        grpc_version=_GRPC_VERSION,
        api_core_version=_API_CORE_VERSION,
        gapic_version=None,
        client_library_version=None,
        user_agent=None,
        rest_version=None,
    ):
        self.python_version = python_version
        self.grpc_version = grpc_version
        self.api_core_version = api_core_version
        self.gapic_version = gapic_version
        self.client_library_version = client_library_version
        self.user_agent = user_agent
        self.rest_version = rest_version

    def to_user_agent(self):
        """Returns the user-agent string for this client info."""

        # Note: the order here is important as the internal metrics system
        # expects these items to be in specific locations.
        ua = ""

        if self.user_agent is not None:
            ua += "{user_agent} "

        ua += "gl-python/{python_version} "

        if self.grpc_version is not None:
            ua += "grpc/{grpc_version} "

        if self.rest_version is not None:
            ua += "rest/{rest_version} "

        ua += "gax/{api_core_version} "

        if self.gapic_version is not None:
            ua += "gapic/{gapic_version} "

        if self.client_library_version is not None:
            ua += "gccl/{client_library_version} "

        return ua.format(**self.__dict__).strip()
