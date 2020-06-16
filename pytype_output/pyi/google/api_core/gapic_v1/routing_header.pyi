# (generated with --quick)

from typing import Any, Callable, Mapping, Sequence, Tuple, TypeVar, Union

ROUTING_METADATA_KEY: str
sys: module

AnyStr = TypeVar('AnyStr', str, bytes)

def to_grpc_metadata(params) -> Tuple[str, str]: ...
def to_routing_header(params) -> str: ...
def urlencode(query: Union[Mapping, Sequence[Tuple[Any, Any]]], doseq: bool = ..., safe: AnyStr = ..., encoding: str = ..., errors: str = ..., quote_via: Callable[[str, AnyStr, str, str], str] = ...) -> str: ...
