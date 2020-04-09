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

import grpc
import mock
import pytest
from grpc.experimental import aio

from google.api_core import exceptions
from google.api_core import grpc_helpers_async
import google.auth.credentials
from google.longrunning import operations_pb2

from grpc.experimental import aio


class RpcErrorImpl(grpc.RpcError, grpc.Call):
    def __init__(self, code):
        super(RpcErrorImpl, self).__init__()
        self._code = code

    def code(self):
        return self._code

    def details(self):
        return None


@pytest.mark.asyncio
async def test_wrap_unary_errors():
    grpc_error = RpcErrorImpl(grpc.StatusCode.INVALID_ARGUMENT)
    callable_ = mock.AsyncMock(spec=["__call__"], side_effect=grpc_error)

    wrapped_callable = grpc_helpers_async._wrap_unary_errors(callable_)

    with pytest.raises(exceptions.InvalidArgument) as exc_info:
        await wrapped_callable(1, 2, three="four")

    callable_.assert_called_once_with(1, 2, three="four")
    assert exc_info.value.response == grpc_error


@mock.patch("google.api_core.grpc_helpers_async._wrap_unary_errors")
def test_wrap_errors_non_streaming(wrap_unary_errors):
    callable_ = mock.create_autospec(aio.UnaryUnaryMultiCallable)

    result = grpc_helpers_async.wrap_errors(callable_)

    assert result == wrap_unary_errors.return_value
    wrap_unary_errors.assert_called_once_with(callable_)


@mock.patch("google.api_core.grpc_helpers_async._wrap_stream_errors")
def test_wrap_errors_streaming(wrap_stream_errors):
    callable_ = mock.create_autospec(aio.UnaryStreamMultiCallable)

    result = grpc_helpers_async.wrap_errors(callable_)

    assert result == wrap_stream_errors.return_value
    wrap_stream_errors.assert_called_once_with(callable_)


@mock.patch("grpc.composite_channel_credentials")
@mock.patch(
    "google.auth.default",
    return_value=(mock.sentinel.credentials, mock.sentinel.projet),
)
@mock.patch("grpc.experimental.aio.secure_channel")
def test_create_channel_implicit(grpc_secure_channel, default, composite_creds_call):
    target = "example.com:443"
    composite_creds = composite_creds_call.return_value

    channel = grpc_helpers_async.create_channel(target)

    assert channel is grpc_secure_channel.return_value
    default.assert_called_once_with(scopes=None)
    if grpc_helpers_async.HAS_GRPC_GCP:
        grpc_secure_channel.assert_called_once_with(target, composite_creds, None)
    else:
        grpc_secure_channel.assert_called_once_with(target, composite_creds)


@mock.patch("grpc.composite_channel_credentials")
@mock.patch(
    "google.auth.default",
    return_value=(mock.sentinel.credentials, mock.sentinel.projet),
)
@mock.patch("grpc.experimental.aio.secure_channel")
def test_create_channel_implicit_with_ssl_creds(
    grpc_secure_channel, default, composite_creds_call
):
    target = "example.com:443"

    ssl_creds = grpc.ssl_channel_credentials()

    grpc_helpers_async.create_channel(target, ssl_credentials=ssl_creds)

    default.assert_called_once_with(scopes=None)
    composite_creds_call.assert_called_once_with(ssl_creds, mock.ANY)
    composite_creds = composite_creds_call.return_value
    if grpc_helpers_async.HAS_GRPC_GCP:
        grpc_secure_channel.assert_called_once_with(target, composite_creds, None)
    else:
        grpc_secure_channel.assert_called_once_with(target, composite_creds)


@mock.patch("grpc.composite_channel_credentials")
@mock.patch(
    "google.auth.default",
    return_value=(mock.sentinel.credentials, mock.sentinel.projet),
)
@mock.patch("grpc.experimental.aio.secure_channel")
def test_create_channel_implicit_with_scopes(
    grpc_secure_channel, default, composite_creds_call
):
    target = "example.com:443"
    composite_creds = composite_creds_call.return_value

    channel = grpc_helpers_async.create_channel(target, scopes=["one", "two"])

    assert channel is grpc_secure_channel.return_value
    default.assert_called_once_with(scopes=["one", "two"])
    if grpc_helpers_async.HAS_GRPC_GCP:
        grpc_secure_channel.assert_called_once_with(target, composite_creds, None)
    else:
        grpc_secure_channel.assert_called_once_with(target, composite_creds)


@mock.patch("grpc.composite_channel_credentials")
@mock.patch("google.auth.credentials.with_scopes_if_required")
@mock.patch("grpc.experimental.aio.secure_channel")
def test_create_channel_explicit(grpc_secure_channel, auth_creds, composite_creds_call):
    target = "example.com:443"
    composite_creds = composite_creds_call.return_value

    channel = grpc_helpers_async.create_channel(target, credentials=mock.sentinel.credentials)

    auth_creds.assert_called_once_with(mock.sentinel.credentials, None)
    assert channel is grpc_secure_channel.return_value
    if grpc_helpers_async.HAS_GRPC_GCP:
        grpc_secure_channel.assert_called_once_with(target, composite_creds, None)
    else:
        grpc_secure_channel.assert_called_once_with(target, composite_creds)


@mock.patch("grpc.composite_channel_credentials")
@mock.patch("grpc.experimental.aio.secure_channel")
def test_create_channel_explicit_scoped(grpc_secure_channel, composite_creds_call):
    target = "example.com:443"
    scopes = ["1", "2"]
    composite_creds = composite_creds_call.return_value

    credentials = mock.create_autospec(google.auth.credentials.Scoped, instance=True)
    credentials.requires_scopes = True

    channel = grpc_helpers_async.create_channel(
        target, credentials=credentials, scopes=scopes
    )

    credentials.with_scopes.assert_called_once_with(scopes)
    assert channel is grpc_secure_channel.return_value
    if grpc_helpers_async.HAS_GRPC_GCP:
        grpc_secure_channel.assert_called_once_with(target, composite_creds, None)
    else:
        grpc_secure_channel.assert_called_once_with(target, composite_creds)


@pytest.mark.skipif(
    not grpc_helpers_async.HAS_GRPC_GCP, reason="grpc_gcp module not available"
)
@mock.patch("grpc_gcp.secure_channel")
def test_create_channel_with_grpc_gcp(grpc_gcp_secure_channel):
    target = "example.com:443"
    scopes = ["test_scope"]

    credentials = mock.create_autospec(google.auth.credentials.Scoped, instance=True)
    credentials.requires_scopes = True

    grpc_helpers_async.create_channel(target, credentials=credentials, scopes=scopes)
    grpc_gcp_secure_channel.assert_called()
    credentials.with_scopes.assert_called_once_with(scopes)


@pytest.mark.skipif(grpc_helpers_async.HAS_GRPC_GCP, reason="grpc_gcp module not available")
@mock.patch("grpc.experimental.aio.secure_channel")
def test_create_channel_without_grpc_gcp(grpc_secure_channel):
    target = "example.com:443"
    scopes = ["test_scope"]

    credentials = mock.create_autospec(google.auth.credentials.Scoped, instance=True)
    credentials.requires_scopes = True

    grpc_helpers_async.create_channel(target, credentials=credentials, scopes=scopes)
    grpc_secure_channel.assert_called()
    credentials.with_scopes.assert_called_once_with(scopes)
