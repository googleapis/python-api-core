# Copyright 2021 Google LLC
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

import json
import random
from typing import List
from unittest.mock import patch

import proto
import pytest
import requests

from google.api_core import rest_streaming


class Composer(proto.Message):
    given_name = proto.Field(proto.STRING, number=1)
    family_name = proto.Field(proto.STRING, number=2)


class Song(proto.Message):
    composer = proto.Field(Composer, number=1)
    title = proto.Field(proto.STRING, number=2)
    lyrics = proto.Field(proto.STRING, number=3)
    year = proto.Field(proto.INT32, number=4)


class EchoResponse(proto.Message):
    content = proto.Field(proto.STRING, number=1)


class ResponseMock(requests.Response):
    class _ResponseItr:
        def __init__(
            self,
            _response_bytes: bytes,
            decode_unicode: bool,
            random_split=False,
            seed=0,
        ):
            self._responses_bytes = _response_bytes
            self._i = 0
            self._decode_unicode = decode_unicode
            self._random_split = random_split
            random.seed(seed)

        def __next__(self):
            if self._i == len(self._responses_bytes):
                raise StopIteration
            if self._random_split:
                n = random.randint(1, len(self._responses_bytes[self._i :]))
            else:
                n = 1
            x = self._responses_bytes[self._i : self._i + n]
            self._i += n
            if self._decode_unicode:
                x = x.decode("utf-8")
            return x

        def __iter__(self):
            return self

    def __init__(
        self,
        *args,
        responses: List[proto.Message],
        random_split=False,
        response_cls,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._responses = responses
        self._random_split = random_split
        self._response_message_cls = response_cls

    def _parse_responses(self, responses: List[proto.Message]) -> bytes:
        ret_val = "["
        # json.dumps returns a string surrounded with quotes that need to be stripped
        # in order to be an actual JSON.
        json_responses = [
            json.dumps(self._response_message_cls.to_json(r))[1:-1] for r in responses
        ]
        for x in json_responses:
            ret_val += x
            ret_val += ","
        ret_val = ret_val[:-1]  # Remove trailing comma.
        ret_val += "]"
        return bytes(ret_val, "utf-8")

    def close(self):
        raise NotImplementedError()

    def iter_content(self, *args, decode_unicode=True, **kwargs):
        return self._ResponseItr(
            self._parse_responses(self._responses),
            decode_unicode,
            random_split=self._random_split,
        )


def test_next_simple():
    responses = [EchoResponse(content="hello world"), EchoResponse(content="yes")]
    resp = ResponseMock(
        responses=responses, random_split=False, response_cls=EchoResponse
    )
    itr = rest_streaming.ResponseIterator(resp, EchoResponse)
    assert list(itr) == responses


def test_next_nested():
    responses = [
        Song(title="some song", composer=Composer(given_name="some name")),
        Song(title="another song"),
    ]
    resp = ResponseMock(responses=responses, random_split=True, response_cls=Song)
    itr = rest_streaming.ResponseIterator(resp, Song)
    assert list(itr) == responses


def test_next_stress():
    n = 50
    responses = [
        Song(title="title_%d" % i, composer=Composer(given_name="name_%d" % i))
        for i in range(n)
    ]
    resp = ResponseMock(responses=responses, random_split=True, response_cls=Song)
    itr = rest_streaming.ResponseIterator(resp, Song)
    assert list(itr) == responses


def test_next_escaped_characters_in_string():
    responses = [
        Song(title="title\nfoo\tbar", composer=Composer(given_name="name\n\n\n"))
    ]
    resp = ResponseMock(responses=responses, random_split=True, response_cls=Song)
    itr = rest_streaming.ResponseIterator(resp, Song)
    assert list(itr) == responses


def test_next_not_array():
    with patch.object(
        ResponseMock, "iter_content", return_value=iter('{"hello": 0}')
    ) as mock_method:

        resp = ResponseMock(responses=[], response_cls=EchoResponse)
        itr = rest_streaming.ResponseIterator(resp, EchoResponse)
        with pytest.raises(ValueError):
            next(itr)
        mock_method.assert_called_once()
