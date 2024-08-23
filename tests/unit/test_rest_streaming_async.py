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

import datetime
import logging
import random
import time
from typing import List, AsyncIterator
import mock

import proto
import pytest

from google.api_core import rest_streaming_async_new
from google.api import http_pb2
from google.api import httpbody_pb2
from google.auth.aio.transport import Response

from ..conftest import Composer, Song, EchoResponse, parse_responses

# TODO (ohmayr): check if we need to log.
__protobuf__ = proto.module(package=__name__)
SEED = int(time.time())
logging.info(f"Starting async rest streaming tests with random seed: {SEED}")
random.seed(SEED)


async def mock_async_gen(data, chunk_size=1):
    for i in range(0, len(data)):
        chunk = data[i : i + chunk_size]
        yield chunk.encode("utf-8")


class ResponseMock(Response):
    class _ResponseItr(AsyncIterator[bytes]):
        def __init__(self, _response_bytes: bytes, random_split=False):
            self._responses_bytes = _response_bytes
            self._i = 0
            self._random_split = random_split

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._i == len(self._responses_bytes):
                raise StopAsyncIteration
            if self._random_split:
                n = random.randint(1, len(self._responses_bytes[self._i :]))
            else:
                n = 1
            x = self._responses_bytes[self._i : self._i + n]
            self._i += n
            return x

    def __init__(
        self,
        responses: List[proto.Message],
        response_cls,
        random_split=False,
    ):
        self._responses = responses
        self._random_split = random_split
        self._response_message_cls = response_cls

    @property
    async def close(self):
        raise NotImplementedError()

    async def content(self, chunk_size=None):
        itr = self._ResponseItr(
            self._parse_responses(), random_split=self._random_split
        )
        async for chunk in itr:
            yield chunk

    async def read(self):
        raise NotImplementedError()

    @property
    async def headers(self):
        raise NotImplementedError()

    @property
    async def status_code(self):
        raise NotImplementedError()

    def _parse_responses(self):
        return parse_responses(self._response_message_cls, self._responses)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "random_split,resp_message_is_proto_plus",
    [(False, True), (False, False)],
)
async def test_next_simple(random_split, resp_message_is_proto_plus):
    if resp_message_is_proto_plus:
        response_type = EchoResponse
        responses = [EchoResponse(content="hello world"), EchoResponse(content="yes")]
    else:
        response_type = httpbody_pb2.HttpBody
        responses = [
            httpbody_pb2.HttpBody(content_type="hello world"),
            httpbody_pb2.HttpBody(content_type="yes"),
        ]

    resp = ResponseMock(
        responses=responses, random_split=random_split, response_cls=response_type
    )
    itr = rest_streaming_async_new.AsyncResponseIterator(resp, response_type)
    i = 0
    async for response in itr:
        assert response == responses[i]
        i += 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "random_split,resp_message_is_proto_plus",
    [
        (True, True),
        (False, True),
        (True, False),
        (False, False),
    ],
)
async def test_next_nested(random_split, resp_message_is_proto_plus):
    if resp_message_is_proto_plus:
        response_type = Song
        responses = [
            Song(title="some song", composer=Composer(given_name="some name")),
            Song(title="another song", date_added=datetime.datetime(2021, 12, 17)),
        ]
    else:
        # Although `http_pb2.HttpRule`` is used in the response, any response message
        # can be used which meets this criteria for the test of having a nested field.
        response_type = http_pb2.HttpRule
        responses = [
            http_pb2.HttpRule(
                selector="some selector",
                custom=http_pb2.CustomHttpPattern(kind="some kind"),
            ),
            http_pb2.HttpRule(
                selector="another selector",
                custom=http_pb2.CustomHttpPattern(path="some path"),
            ),
        ]
    resp = ResponseMock(
        responses=responses, random_split=random_split, response_cls=response_type
    )
    itr = rest_streaming_async_new.AsyncResponseIterator(resp, response_type)
    i = 0
    async for response in itr:
        assert response == responses[i]
        i += 1
    assert i == len(responses)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "random_split,resp_message_is_proto_plus",
    [
        (True, True),
        (False, True),
        (True, False),
        (False, False),
    ],
)
async def test_next_stress(random_split, resp_message_is_proto_plus):
    n = 50
    if resp_message_is_proto_plus:
        response_type = Song
        responses = [
            Song(title="title_%d" % i, composer=Composer(given_name="name_%d" % i))
            for i in range(n)
        ]
    else:
        response_type = http_pb2.HttpRule
        responses = [
            http_pb2.HttpRule(
                selector="selector_%d" % i,
                custom=http_pb2.CustomHttpPattern(path="path_%d" % i),
            )
            for i in range(n)
        ]
    resp = ResponseMock(
        responses=responses, random_split=random_split, response_cls=response_type
    )
    itr = rest_streaming_async_new.AsyncResponseIterator(resp, response_type)
    i = 0
    async for response in itr:
        assert response == responses[i]
        i += 1
    assert i == n


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "random_split,resp_message_is_proto_plus",
    [
        (True, True),
        (False, True),
        (True, False),
        (False, False),
    ],
)
async def test_next_escaped_characters_in_string(
    random_split, resp_message_is_proto_plus
):
    if resp_message_is_proto_plus:
        response_type = Song
        composer_with_relateds = Composer()
        relateds = ["Artist A", "Artist B"]
        composer_with_relateds.relateds = relateds

        responses = [
            Song(
                title='ti"tle\nfoo\tbar{}', composer=Composer(given_name="name\n\n\n")
            ),
            Song(
                title='{"this is weird": "totally"}',
                composer=Composer(given_name="\\{}\\"),
            ),
            Song(title='\\{"key": ["value",]}\\', composer=composer_with_relateds),
        ]
    else:
        response_type = http_pb2.Http
        responses = [
            http_pb2.Http(
                rules=[
                    http_pb2.HttpRule(
                        selector='ti"tle\nfoo\tbar{}',
                        custom=http_pb2.CustomHttpPattern(kind="name\n\n\n"),
                    )
                ]
            ),
            http_pb2.Http(
                rules=[
                    http_pb2.HttpRule(
                        selector='{"this is weird": "totally"}',
                        custom=http_pb2.CustomHttpPattern(kind="\\{}\\"),
                    )
                ]
            ),
            http_pb2.Http(
                rules=[
                    http_pb2.HttpRule(
                        selector='\\{"key": ["value",]}\\',
                        custom=http_pb2.CustomHttpPattern(kind="\\{}\\"),
                    )
                ]
            ),
        ]
    resp = ResponseMock(
        responses=responses, random_split=random_split, response_cls=response_type
    )
    itr = rest_streaming_async_new.AsyncResponseIterator(resp, response_type)

    i = 0
    async for response in itr:
        assert response == responses[i]
        i += 1
    assert i == len(responses)


@pytest.mark.asyncio
@pytest.mark.parametrize("response_type", [EchoResponse, httpbody_pb2.HttpBody])
async def test_next_not_array(response_type):

    data = '{"hello": 0}'
    with mock.patch.object(
        ResponseMock, "content", return_value=mock_async_gen(data)
    ) as mock_method:
        resp = ResponseMock(responses=[], response_cls=response_type)
        itr = rest_streaming_async_new.AsyncResponseIterator(resp, response_type)
        with pytest.raises(ValueError):
            await itr.__anext__()
        mock_method.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("response_type", [EchoResponse, httpbody_pb2.HttpBody])
async def test_cancel(response_type):
    with mock.patch.object(
        ResponseMock, "close", new_callable=mock.AsyncMock
    ) as mock_method:
        resp = ResponseMock(responses=[], response_cls=response_type)
        itr = rest_streaming_async_new.AsyncResponseIterator(resp, response_type)
        await itr.cancel()
        mock_method.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_type,return_value",
    [
        (EchoResponse, bytes('[{"content": "hello"}, {', "utf-8")),
        (httpbody_pb2.HttpBody, bytes('[{"content_type": "hello"}, {', "utf-8")),
    ],
)
async def test_check_buffer(response_type, return_value):
    with mock.patch.object(
        ResponseMock,
        "_parse_responses",
        return_value=return_value,
    ):
        resp = ResponseMock(responses=[], response_cls=response_type)
        itr = rest_streaming_async_new.AsyncResponseIterator(resp, response_type)
        with pytest.raises(ValueError):
            await itr.__anext__()
            await itr.__anext__()


@pytest.mark.asyncio
@pytest.mark.parametrize("response_type", [EchoResponse, httpbody_pb2.HttpBody])
async def test_next_html(response_type):

    data = "<!DOCTYPE html><html></html>"
    with mock.patch.object(
        ResponseMock, "content", return_value=mock_async_gen(data)
    ) as mock_method:
        resp = ResponseMock(responses=[], response_cls=response_type)

        itr = rest_streaming_async_new.AsyncResponseIterator(resp, response_type)
        with pytest.raises(ValueError):
            await itr.__anext__()
        mock_method.assert_called_once()


@pytest.mark.asyncio
async def test_invalid_response_class():
    class SomeClass:
        pass

    resp = ResponseMock(responses=[], response_cls=SomeClass)
    response_iterator = rest_streaming_async_new.AsyncResponseIterator(resp, SomeClass)

    with pytest.raises(
        ValueError,
        match="Response message class must be a subclass of proto.Message or google.protobuf.message.Message",
    ):
        response_iterator._grab()
