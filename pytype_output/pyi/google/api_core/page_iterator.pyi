# (generated with --quick)

from typing import Any, Dict, FrozenSet, Generator, TypeVar

abc: module
six: module

_T1 = TypeVar('_T1')
_TPage = TypeVar('_TPage', bound=Page)

class GRPCIterator(Iterator):
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
    def _next_page(self) -> Page: ...

class HTTPIterator(Iterator):
    _DEFAULT_ITEMS_KEY: str
    _HTTP_METHOD: str
    _MAX_RESULTS: str
    _NEXT_TOKEN: str
    _PAGE_TOKEN: str
    _RESERVED_PARAMS: FrozenSet[str]
    __doc__: str
    _items_key: Any
    _next_token: Any
    _started: bool
    client: Any
    extra_params: Any
    item_to_value: Any
    max_results: Any
    next_page_token: Any
    num_results: int
    page_number: int
    path: Any
    def __init__(self, client, api_request, path, item_to_value, items_key = ..., page_token = ..., max_results = ..., extra_params = ..., page_start = ..., next_token = ...) -> None: ...
    def _get_next_page_response(self) -> Any: ...
    def _get_query_params(self) -> Dict[str, Any]: ...
    def _has_next_page(self) -> bool: ...
    def _next_page(self) -> Page: ...
    def _page_start(self, _1: HTTPIterator, _2: Page, _3) -> Any: ...
    def _verify_params(self) -> None: ...
    def api_request(self) -> Any: ...

class Iterator(metaclass=abc.ABCMeta):
    __doc__: str
    _started: bool
    client: Any
    item_to_value: Any
    max_results: Any
    next_page_token: Any
    num_results: Any
    page_number: int
    pages: Any
    def __init__(self, client, item_to_value = ..., page_token = ..., max_results = ...) -> None: ...
    def __iter__(self) -> Generator[Any, Any, None]: ...
    def _items_iter(self) -> Generator[Any, Any, None]: ...
    @abstractmethod
    def _next_page(self) -> Any: ...
    def _page_iter(self, increment) -> Generator[Any, Any, None]: ...

class Page:
    __doc__: str
    _item_iter: Any
    _item_to_value: Any
    _num_items: int
    _parent: Any
    _raw_page: Any
    _remaining: int
    num_items: Any
    raw_page: Any
    remaining: Any
    def __init__(self, parent, items, item_to_value, raw_page = ...) -> None: ...
    def __iter__(self: _TPage) -> _TPage: ...
    def __next__(self) -> Any: ...
    def next(self) -> Any: ...

class _GAXIterator(Iterator):
    __doc__: str
    _gax_page_iter: Any
    _started: bool
    client: Any
    item_to_value: Any
    max_results: Any
    next_page_token: Any
    num_results: int
    page_number: int
    def __init__(self, client, page_iter, item_to_value, max_results = ...) -> None: ...
    def _next_page(self) -> Page: ...

def _do_nothing_page_start(iterator, page, response) -> None: ...
def _item_to_value_identity(iterator, item: _T1) -> _T1: ...
