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

"""Helpers for server-side streaming in REST."""

from collections import deque
import string
from typing import Deque, Union

import proto
import requests
import google.protobuf.message
from google.protobuf.json_format import Parse
import aiohttp
from google.api_core._rest_streaming_base import BaseResponseIterator

class ResponseAsyncIterator(BaseResponseIterator):
    """Iterator over REST API Asynchronous responses.

    Args:
        response (requests.Response): An API response object.
        response_message_cls (Union[proto.Message, google.protobuf.message.Message]): A response
        class expected to be returned from an API.

    Raises:
        ValueError: If `response_message_cls` is not a subclass of `proto.Message` or `google.protobuf.message.Message`.
    """

    def __init__(
        self,
        response: aiohttp.ClientResponse,
        response_message_cls: Union[proto.Message, google.protobuf.message.Message],
    ):
        self._response = response
        self._response_itr = self._response.content.iter_chunked(1024)
        super(ResponseAsyncIterator, self).__init__(response_message_cls=response_message_cls)
    
    async def __anext__(self):
        while not self._ready_objs:
            try:
                chunk = await self._response_itr.__anext__()
                chunk = chunk.decode('utf-8')
                self._process_chunk(chunk)
            except StopAsyncIteration as e:
                if self._level > 0:
                    raise ValueError("Unfinished stream: %s" % self._obj)
                raise e
        return self._grab()
    
    def __aiter__(self):
        return self

    
    async def __aexit__(self, exc_type, exc, tb):
        await self._response.release()

    async def cancel(self):
        await self._response.close()