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

import pytest
from unittest import mock

try:
    import grpc  # noqa: F401
except ImportError:  # pragma: NO COVER
    pytest.skip("No GRPC", allow_module_level=True)

from google.api_core import operations_v1
from google.api_core.operations_v1 import transports


def test_ipv6_host_with_port():
    """Test that IPv6 host with port doesn't get modified."""
    with mock.patch('google.auth.default', return_value=(mock.Mock(), "project")):
        transport = transports.OperationsRestTransport(host="[2001:db8::1]:8080")
        assert transport._host == "https://[2001:db8::1]:8080"


def test_ipv6_host_without_port():
    """Test that IPv6 host without port gets default HTTPS port."""
    with mock.patch('google.auth.default', return_value=(mock.Mock(), "project")):
        transport = transports.OperationsRestTransport(host="[2001:db8::1]")
        assert transport._host == "https://[2001:db8::1]:443"


def test_ipv4_host_with_port():
    """Test that IPv4 host with port doesn't get modified."""
    with mock.patch('google.auth.default', return_value=(mock.Mock(), "project")):
        transport = transports.OperationsRestTransport(host="192.168.1.1:8080")
        assert transport._host == "https://192.168.1.1:8080"


def test_ipv4_host_without_port():
    """Test that IPv4 host without port gets default HTTPS port."""
    with mock.patch('google.auth.default', return_value=(mock.Mock(), "project")):
        transport = transports.OperationsRestTransport(host="192.168.1.1")
        assert transport._host == "https://192.168.1.1:443"


def test_hostname_with_port():
    """Test that hostname with port doesn't get modified."""
    with mock.patch('google.auth.default', return_value=(mock.Mock(), "project")):
        transport = transports.OperationsRestTransport(host="example.com:8080")
        assert transport._host == "https://example.com:8080"


def test_hostname_without_port():
    """Test that hostname without port gets default HTTPS port."""
    with mock.patch('google.auth.default', return_value=(mock.Mock(), "project")):
        transport = transports.OperationsRestTransport(host="example.com")
        assert transport._host == "https://example.com:443"


def test_custom_scheme():
    """Test that custom schemes are preserved."""
    with mock.patch('google.auth.default', return_value=(mock.Mock(), "project")):
        transport = transports.OperationsRestTransport(
            host="custom://example.com", 
            url_scheme="custom"
        )
        assert transport._host == "custom://example.com:443"
