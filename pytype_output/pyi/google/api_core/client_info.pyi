# (generated with --quick)

from typing import Any, Optional

_API_CORE_VERSION: str
_GRPC_VERSION: Optional[str]
_PY_VERSION: str
pkg_resources: module
platform: module

class ClientInfo:
    __doc__: str
    api_core_version: Any
    client_library_version: Any
    gapic_version: Any
    grpc_version: Any
    python_version: Any
    user_agent: Any
    def __init__(self, python_version = ..., grpc_version = ..., api_core_version = ..., gapic_version = ..., client_library_version = ..., user_agent = ...) -> None: ...
    def to_user_agent(self) -> str: ...
