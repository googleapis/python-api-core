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

"""AsyncIO iterators for paging through paged API methods.

These iterators simplify the process of paging through API responses
where the request takes a page token and the response is a list of results with
a token for the next page. See `list pagination`_ in the Google API Style Guide
for more details.

.. _list pagination:
    https://cloud.google.com/apis/design/design_patterns#list_pagination

API clients that have methods that follow the list pagination pattern can
return an :class:`.AsyncIterator`:

    >>> results_iterator = await client.list_resources()

Or you can walk your way through items and call off the search early if
you find what you're looking for (resulting in possibly fewer requests)::

    >>> async for resource in results_iterator:
    ...     print(resource.name)
    ...     if not resource.is_valid:
    ...         break

At any point, you may check the number of items consumed by referencing the
``num_results`` property of the iterator::

    >>> async for my_item in results_iterator:
    ...     if results_iterator.num_results >= 10:
    ...         break

When iterating, not every new item will send a request to the server.
To iterate based on each page of items (where a page corresponds to
a request)::

    >>> async for page in results_iterator.pages:
    ...     print('=' * 20)
    ...     print('    Page number: {:d}'.format(iterator.page_number))
    ...     print('  Items in page: {:d}'.format(page.num_items))
    ...     print('     First item: {!r}'.format(next(page)))
    ...     print('Items remaining: {:d}'.format(page.remaining))
    ...     print('Next page token: {}'.format(iterator.next_page_token))
    ====================
        Page number: 1
      Items in page: 1
         First item: <MyItemClass at 0x7f1d3cccf690>
    Items remaining: 0
    Next page token: eav1OzQB0OM8rLdGXOEsyQWSG
    ====================
        Page number: 2
      Items in page: 19
         First item: <MyItemClass at 0x7f1d3cccffd0>
    Items remaining: 18
    Next page token: None
"""

import abc

from google.api_core.page_iterator import Page, _do_nothing_page_start


def _item_to_value_identity(iterator, item):
    """An item to value transformer that returns the item un-changed."""
    # pylint: disable=unused-argument
    # We are conforming to the interface defined by Iterator.
    return item


class AsyncIterator(abc.ABC):
    """A generic class for iterating through API list responses.

    Args:
        client(google.cloud.client.Client): The API client.
        item_to_value (Callable[google.api_core.page_iterator_async.AsyncIterator, Any]):
            Callable to convert an item from the type in the raw API response
            into the native object. Will be called with the iterator and a
            single item.
        page_token (str): A token identifying a page in a result set to start
            fetching results from.
        max_results (int): The maximum number of results to fetch.
    """

    def __init__(
        self,
        client,
        item_to_value=_item_to_value_identity,
        page_token=None,
        max_results=None,
    ):
        self._started = False
        self.__active_aiterator = None

        self.client = client
        """Optional[Any]: The client that created this iterator."""
        self.item_to_value = item_to_value
        """Callable[Iterator, Any]: Callable to convert an item from the type
            in the raw API response into the native object. Will be called with
            the iterator and a
            single item.
        """
        self.max_results = max_results
        """int: The maximum number of results to fetch."""

        # The attributes below will change over the life of the iterator.
        self.page_number = 0
        """int: The current page of results."""
        self.next_page_token = page_token
        """str: The token for the next page of results. If this is set before
            the iterator starts, it effectively offsets the iterator to a
            specific starting point."""
        self.num_results = 0
        """int: The total number of results fetched so far."""

    @property
    def pages(self):
        """Iterator of pages in the response.

        returns:
            types.GeneratorType[google.api_core.page_iterator.Page]: A
                generator of page instances.

        raises:
            ValueError: If the iterator has already been started.
        """
        if self._started:
            raise ValueError("Iterator has already started", self)
        self._started = True
        return self._page_aiter(increment=True)

    async def _items_aiter(self):
        """Iterator for each item returned."""
        async for page in self._page_aiter(increment=False):
            for item in page:
                self.num_results += 1
                yield item

    def __aiter__(self):
        """Iterator for each item returned.

        Returns:
            types.GeneratorType[Any]: A generator of items from the API.

        Raises:
            ValueError: If the iterator has already been started.
        """
        if self._started:
            raise ValueError("Iterator has already started", self)
        self._started = True
        return self._items_aiter()

    async def __anext__(self):
        if self.__active_aiterator is None:
            self.__active_aiterator = self.__aiter__()
        return await self.__active_aiterator.__anext__()

    async def _page_aiter(self, increment):
        """Generator of pages of API responses.

        Args:
            increment (bool): Flag indicating if the total number of results
                should be incremented on each page. This is useful since a page
                iterator will want to increment by results per page while an
                items iterator will want to increment per item.

        Yields:
            Page: each page of items from the API.
        """
        page = await self._next_page()
        while page is not None:
            self.page_number += 1
            if increment:
                self.num_results += page.num_items
            yield page
            page = await self._next_page()

    @abc.abstractmethod
    async def _next_page(self):
        """Get the next page in the iterator.

        This does nothing and is intended to be over-ridden by subclasses
        to return the next :class:`Page`.

        Raises:
            NotImplementedError: Always, this method is abstract.
        """
        raise NotImplementedError


class AsyncHTTPIterator(AsyncIterator):
    """A generic class for iterating through HTTP/JSON API list responses for asynchronous I/O.

    To make an iterator work, you'll need to provide a way to convert a JSON
    item returned from the API into the object of your choice (via
    ``item_to_value``). You also may need to specify a custom ``items_key`` so
    that a given response (containing a page of results) can be parsed into an
    iterable page of the actual objects you want.

    Args:
        client (google.cloud.client.Client): The API client.
        api_request (Callable): The function to use to make API requests.
            Generally, this will be a coroutine of
            :meth:`google.cloud._http.JSONConnection.api_request`.
        path (str): The method path to query for the list of items.
        item_to_value (Callable[google.api_core.page_iterator.Iterator, Any]):
            Callable to convert an item from the type in the JSON response into
            a native object. Will be called with the iterator and a single
            item.
        items_key (str): The key in the API response where the list of items
            can be found.
        page_token (str): A token identifying a page in a result set to start
            fetching results from.
        page_size (int): The maximum number of results to fetch per page
        max_results (int): The maximum number of results to fetch
        extra_params (dict): Extra query string parameters for the
            API call.
        page_start (Callable[
            google.api_core.page_iterator.Iterator,
            google.api_core.page_iterator.Page, dict]): Callable to provide
            any special behavior after a new page has been created. Assumed
            signature takes the :class:`.Iterator` that started the page,
            the :class:`.Page` that was started and the dictionary containing
            the page response.
        next_token (str): The name of the field used in the response for page
            tokens.

    .. autoattribute:: pages
    """

    _DEFAULT_ITEMS_KEY = "items"
    _PAGE_TOKEN = "pageToken"
    _MAX_RESULTS = "maxResults"
    _NEXT_TOKEN = "nextPageToken"
    _RESERVED_PARAMS = frozenset([_PAGE_TOKEN])
    _HTTP_METHOD = "GET"

    def __init__(
        self,
        client,
        api_request,
        path,
        item_to_value,
        items_key=_DEFAULT_ITEMS_KEY,
        page_token=None,
        page_size=None,
        max_results=None,
        extra_params=None,
        page_start=_do_nothing_page_start,
        next_token=_NEXT_TOKEN,
    ):
        super().__init__(
            client, item_to_value, page_token=page_token, max_results=max_results
        )
        self.api_request = api_request
        self.path = path
        self._items_key = items_key
        self.extra_params = extra_params
        self._page_size = page_size
        self._page_start = page_start
        self._next_token = next_token
        # Verify inputs / provide defaults.
        if self.extra_params is None:
            self.extra_params = {}
        self._verify_params()

    def _verify_params(self):
        """Verifies the parameters don't use any reserved parameter.

        Raises:
            ValueError: If a reserved parameter is used.
        """
        reserved_in_use = self._RESERVED_PARAMS.intersection(self.extra_params)
        if reserved_in_use:
            raise ValueError("Using a reserved parameter", reserved_in_use)

    async def _next_page(self):
        """Get the next page in the iterator.

        Returns:
            Optional[Page]: The next page in the iterator or :data:`None` if
                there are no pages left.
        """
        if self._has_next_page():
            response = await self._get_next_page_response()
            items = response.get(self._items_key, ())
            page = Page(self, items, self.item_to_value, raw_page=response)
            self._page_start(self, page, response)
            self.next_page_token = response.get(self._next_token)
            return page
        else:
            return None

    def _has_next_page(self):
        """Determines whether or not there are more pages with results.

        Returns:
            bool: Whether the iterator has more pages.
        """
        if self.page_number == 0:
            return True

        if self.max_results is not None:
            if self.num_results >= self.max_results:
                return False

        return self.next_page_token is not None

    def _get_query_params(self):
        """Getter for query parameters for the next request.

        Returns:
            dict: A dictionary of query parameters.
        """
        result = {}
        if self.next_page_token is not None:
            result[self._PAGE_TOKEN] = self.next_page_token

        page_size = None
        if self.max_results is not None:
            page_size = self.max_results - self.num_results
            if self._page_size is not None:
                page_size = min(page_size, self._page_size)
        elif self._page_size is not None:
            page_size = self._page_size

        if page_size is not None:
            result[self._MAX_RESULTS] = page_size

        result.update(self.extra_params)
        return result

    async def _get_next_page_response(self):
        """Requests the next page from the path provided.

        Returns:
            dict: The parsed JSON response of the next page's contents.

        Raises:
            ValueError: If the HTTP method is not ``GET`` or ``POST``.
        """
        params = self._get_query_params()
        if self._HTTP_METHOD == "GET":
            return await self.api_request(
                method=self._HTTP_METHOD, path=self.path, query_params=params
            )
        elif self._HTTP_METHOD == "POST":
            return await self.api_request(
                method=self._HTTP_METHOD, path=self.path, data=params
            )
        else:
            raise ValueError("Unexpected HTTP method", self._HTTP_METHOD)


class AsyncGRPCIterator(AsyncIterator):
    """A generic class for iterating through gRPC list responses.

    .. note:: The class does not take a ``page_token`` argument because it can
        just be specified in the ``request``.

    Args:
        client (google.cloud.client.Client): The API client. This unused by
            this class, but kept to satisfy the :class:`Iterator` interface.
        method (Callable[protobuf.Message]): A bound gRPC method that should
            take a single message for the request.
        request (protobuf.Message): The request message.
        items_field (str): The field in the response message that has the
            items for the page.
        item_to_value (Callable[GRPCIterator, Any]): Callable to convert an
            item from the type in the JSON response into a native object. Will
            be called with the iterator and a single item.
        request_token_field (str): The field in the request message used to
            specify the page token.
        response_token_field (str): The field in the response message that has
            the token for the next page.
        max_results (int): The maximum number of results to fetch.

    .. autoattribute:: pages
    """

    _DEFAULT_REQUEST_TOKEN_FIELD = "page_token"
    _DEFAULT_RESPONSE_TOKEN_FIELD = "next_page_token"

    def __init__(
        self,
        client,
        method,
        request,
        items_field,
        item_to_value=_item_to_value_identity,
        request_token_field=_DEFAULT_REQUEST_TOKEN_FIELD,
        response_token_field=_DEFAULT_RESPONSE_TOKEN_FIELD,
        max_results=None,
    ):
        super().__init__(client, item_to_value, max_results=max_results)
        self._method = method
        self._request = request
        self._items_field = items_field
        self._request_token_field = request_token_field
        self._response_token_field = response_token_field

    async def _next_page(self):
        """Get the next page in the iterator.

        Returns:
            Page: The next page in the iterator or :data:`None` if
                there are no pages left.
        """
        if not self._has_next_page():
            return None

        if self.next_page_token is not None:
            setattr(self._request, self._request_token_field, self.next_page_token)

        response = await self._method(self._request)

        self.next_page_token = getattr(response, self._response_token_field)
        items = getattr(response, self._items_field)
        page = Page(self, items, self.item_to_value, raw_page=response)

        return page

    def _has_next_page(self):
        """Determines whether or not there are more pages with results.

        Returns:
            bool: Whether the iterator has more pages.
        """
        if self.page_number == 0:
            return True

        # Note: intentionally a falsy check instead of a None check. The RPC
        # can return an empty string indicating no more pages.
        if self.max_results is not None:
            if self.num_results >= self.max_results:
                return False

        return True if self.next_page_token else False
