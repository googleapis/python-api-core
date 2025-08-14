# Copyright 2020, Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Asynchronous bi-directional streaming RPC helpers."""

import asyncio
import logging

from google.api_core import exceptions

_LOGGER = logging.getLogger(__name__)


class _AsyncRequestQueueGenerator:
    """An async helper for sending requests to a gRPC stream from a Queue.

    This generator takes requests off a given queue and yields them to gRPC.

    This helper is useful when you have an indeterminate, indefinite, or
    otherwise open-ended set of requests to send through a request-streaming
    (or bidirectional) RPC.

    The reason this is necessary is because gRPC takes an async iterator as the
    request for request-streaming RPCs. gRPC consumes this iterator to allow
    it to block while generating requests for the stream. However, if the
    generator blocks indefinitely gRPC will not be able to clean up the task
    as it'll be blocked on `anext(iterator)` and not be able to check the
    channel status to stop iterating. This helper mitigates that by waiting
    on the queue with a timeout and checking the RPC state before yielding.

    Finally, it allows for retrying without swapping queues because if it does
    pull an item off the queue when the RPC is inactive, it'll immediately put
    it back and then exit. This is necessary because yielding the item in this
    case will cause gRPC to discard it. In practice, this means that the order
of messages is not guaranteed. If such a thing is necessary it would be
    easy to use a priority queue.

    Example::

        requests = _AsyncRequestQueueGenerator(q)
        call = await stub.StreamingRequest(requests)
        requests.call = call

        async for response in call:
            print(response)
            await q.put(...)

    Args:
        queue (asyncio.Queue): The request queue.
        period (float): The number of seconds to wait for items from the queue
            before checking if the RPC is cancelled. In practice, this
            determines the maximum amount of time the request consumption
            task will live after the RPC is cancelled.
        initial_request (Union[protobuf.Message,
                Callable[[], protobuf.Message]]): The initial request to
            yield. This is done independently of the request queue to allow for
            easily restarting streams that require some initial configuration
            request.
    """

    def __init__(self, queue: asyncio.Queue, period: float = 1, initial_request=None):
        self._queue = queue
        self._period = period
        self._initial_request = initial_request
        self.call = None

    def _is_active(self):
        # Note: there is a possibility that this starts *before* the call
        # property is set. So we have to check if self.call is set before
        # seeing if it's active. We need to return True if self.call is None.
        # See https://github.com/googleapis/python-api-core/issues/560.
        return self.call is None or not self.call.done()

    async def __aiter__(self):
        if self._initial_request is not None:
            if callable(self._initial_request):
                yield self._initial_request()
            else:
                yield self._initial_request

        while True:
            try:
                item = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                if not self._is_active():
                    _LOGGER.debug(
                        "Empty queue and inactive call, exiting request generator."
                    )
                    return
                else:
                    # call is still active, keep waiting for queue items.
                    await asyncio.sleep(self._period)
                    continue

            # The consumer explicitly sent "None", indicating that the request
            # should end.
            if item is None:
                _LOGGER.debug("Cleanly exiting request generator.")
                return

            if not self._is_active():
                # We have an item, but the call is closed. We should put the
                # item back on the queue so that the next call can consume it.
                await self._queue.put(item)
                _LOGGER.debug(
                    "Inactive call, replacing item on queue and exiting "
                    "request generator."
                )
                return

            yield item



class AsyncBidiRpc:
    """A helper for consuming a async bi-directional streaming RPC.

    This maps gRPC's built-in interface which uses a request iterator and a
    response iterator into a socket-like :func:`send` and :func:`recv`. This
    is a more useful pattern for long-running or asymmetric streams (streams
    where there is not a direct correlation between the requests and
    responses).

    Example::

        initial_request = example_pb2.StreamingRpcRequest(
            setting='example')
        rpc = AsyncBidiRpc(
            stub.StreamingRpc,
            initial_request=initial_request,
            metadata=[('name', 'value')]
        )

        await rpc.open()

        while rpc.is_active:
            print(await rpc.recv())
            await rpc.send(example_pb2.StreamingRpcRequest(
                data='example'))

    This does *not* retry the stream on errors. See :class:`AsyncResumableBidiRpc`.

    Args:
        start_rpc (grpc.aio.StreamStreamMultiCallable): The gRPC method used to
            start the RPC.
        initial_request (Union[protobuf.Message,
                Callable[[], protobuf.Message]]): The initial request to
            yield. This is useful if an initial request is needed to start the
            stream.
        metadata (Sequence[Tuple(str, str)]): RPC metadata to include in
            the request.
    """

    def __init__(self, start_rpc, initial_request=None, metadata=None):
        self._start_rpc = start_rpc
        self._initial_request = initial_request
        self._rpc_metadata = metadata
        self._request_queue = asyncio.Queue()
        self._request_generator = None
        self._callbacks = []
        self.call = None
        self._loop = asyncio.get_event_loop()

    def add_done_callback(self, callback):
        """Adds a callback that will be called when the RPC terminates.

        This occurs when the RPC errors or is successfully terminated.

        Args:
            callback (Callable[[grpc.Future], None]): The callback to execute.
                It will be provided with the same gRPC future as the underlying
                stream which will also be a :class:`grpc.aio.Call`.
        """
        self._callbacks.append(callback)

    def _on_call_done(self, future):
        # This occurs when the RPC errors or is successfully terminated.
        # Note that grpc's "future" here can also be a grpc.RpcError.
        # See note in https://github.com/grpc/grpc/issues/10885#issuecomment-302651331
        # that `grpc.RpcError` is also `grpc.aio.Call`.
        for callback in self._callbacks:
            callback(future)

    async def open(self):
        """Opens the stream."""
        if self.is_active:
            raise ValueError("Can not open an already open stream.")

        request_generator = _AsyncRequestQueueGenerator(
            self._request_queue, initial_request=self._initial_request
        )
        try:
            call = await self._start_rpc(request_generator, metadata=self._rpc_metadata)
        except exceptions.GoogleAPICallError as exc:
            # The original `grpc.RpcError` (which is usually also a `grpc.Call`) is
            # available from the ``response`` property on the mapped exception.
            self._on_call_done(exc.response)
            raise

        request_generator.call = call

        # TODO: api_core should expose the future interface for wrapped
        # callables as well.
        if hasattr(call, "_wrapped"):  # pragma: NO COVER
            call._wrapped.add_done_callback(self._on_call_done)
        else:
            call.add_done_callback(self._on_call_done)

        self._request_generator = request_generator
        self.call = call

    async def close(self):
        """Closes the stream."""
        if self.call is None:
            return

        await self._request_queue.put(None)
        self.call.cancel()
        self._request_generator = None
        self._initial_request = None
        self._callbacks = []
        # Don't set self.call to None. Keep it around so that send/recv can
        # raise the error.

    async def send(self, request):
        """Queue a message to be sent on the stream.

        If the underlying RPC has been closed, this will raise.

        Args:
            request (protobuf.Message): The request to send.
        """
        if self.call is None:
            raise ValueError("Can not send() on an RPC that has never been open()ed.")

        # Don't use self.is_active(), as ResumableBidiRpc will overload it
        # to mean something semantically different.
        if not self.call.done():
            await self._request_queue.put(request)
        else:
            # calling read should cause the call to raise.
            await self.call.read()

    async def recv(self):
        """Wait for a message to be returned from the stream.

        If the underlying RPC has been closed, this will raise.

        Returns:
            protobuf.Message: The received message.
        """
        if self.call is None:
            raise ValueError("Can not recv() on an RPC that has never been open()ed.")

        return await self.call.read()

    @property
    def is_active(self):
        """bool: True if this stream is currently open and active."""
        return self.call is not None and not self.call.done()

    @property
    def pending_requests(self):
        """int: Returns an estimate of the number of queued requests."""
        return self._request_queue.qsize()
