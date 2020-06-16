# (generated with --quick)

from typing import Any

class ClientOptions:
    __doc__: str
    api_endpoint: Any
    client_cert_source: Any
    client_encrypted_cert_source: Any
    credentials_file: Any
    quota_project_id: Any
    scopes: Any
    def __init__(self, api_endpoint = ..., client_cert_source = ..., client_encrypted_cert_source = ..., quota_project_id = ..., credentials_file = ..., scopes = ...) -> None: ...
    def __repr__(self) -> str: ...

def from_dict(options) -> ClientOptions: ...
