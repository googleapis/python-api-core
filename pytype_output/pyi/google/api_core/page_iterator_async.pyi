# (generated with --quick)

import google.api_core.page_iterator
from typing import Any, Coroutine, Type, TypeVar

Page: Type[google.api_core.page_iterator.Page]
abc: module

_T1 = TypeVar('_T1')

class AsyncGRPCIterator(AsyncIterator):
    _DEFAULT_REQUEST_TOKEN_FIELD: str
    _DEFAULT_RESPONSE_TOKEN_FIELD: str
    __doc__: str
    _items_field: Any
    _request: Any
    _request_token_field: Any
    _response_token_field: Any
    _started: bool
    client: Any
    item_to_value: Any
    max_results: Any
    next_page_token: Any
    num_results: int
    page_number: int
    def __init__(self, client, method, request, items_field, item_to_value = ..., request_token_field = ..., response_token_field = ..., max_results = ...) -> None: ...
    def _has_next_page(self) -> bool: ...
    def _method(self, _1) -> Any: ...
    def _next_page(self) -> Coroutine[Any, Any, google.api_core.page_iterator.Page]: ...

class AsyncIterator(abc.ABC):
    __doc__: str
    _started: bool
    client: Any
    item_to_value: Any
    max_results: Any
    next_page_token: Any
    num_results: Any
    page_number: int
    pages: Any
    def __aiter__(self) -> asyncgenerator: ...
    def __init__(self, client, item_to_value = ..., page_token = ..., max_results = ...) -> None: ...
    def _items_aiter(self) -> asyncgenerator: ...
    @abstractmethod
    def _next_page(self) -> coroutine: ...
    def _page_aiter(self, increment) -> asyncgenerator: ...

def _item_to_value_identity(iterator, item: _T1) -> _T1: ...
