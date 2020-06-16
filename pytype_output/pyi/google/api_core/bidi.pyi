# (generated with --quick)

from typing import Any, Generator, Iterator, List, Optional

_BIDIRECTIONAL_CONSUMER_NAME: str
_LOGGER: logging.Logger
collections: module
datetime: module
exceptions: module
logging: module
queue: module
threading: module
time: module

class BackgroundConsumer:
    __doc__: str
    _bidi_rpc: Any
    _operational_lock: threading.Lock
    _paused: bool
    _thread: Optional[threading.Thread]
    _wake: threading.Condition
    is_active: Any
    is_paused: Any
    def __init__(self, bidi_rpc, on_response) -> None: ...
    def _on_call_done(self, future) -> None: ...
    def _on_response(self, _1) -> Any: ...
    def _thread_main(self, ready) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...

class BidiRpc:
    __doc__: str
    _callbacks: list
    _initial_request: Any
    _is_active: bool
    _request_generator: Optional[_RequestQueueGenerator]
    _request_queue: queue.Queue[nothing]
    _rpc_metadata: Any
    call: Any
    is_active: Any
    pending_requests: Any
    def __init__(self, start_rpc, initial_request = ..., metadata = ...) -> None: ...
    def _on_call_done(self, future) -> None: ...
    def _start_rpc(self, _1: Iterator) -> Any: ...
    def add_done_callback(self, callback) -> None: ...
    def close(self) -> None: ...
    def open(self) -> None: ...
    def recv(self) -> Any: ...
    def send(self, request) -> None: ...

class ResumableBidiRpc(BidiRpc):
    __doc__: str
    _callbacks: List[nothing]
    _finalize_lock: threading.Lock
    _finalized: bool
    _initial_request: Any
    _is_active: bool
    _operational_lock: threading._RLock
    _reopen_throttle: Optional[_Throttle]
    _request_generator: Optional[_RequestQueueGenerator]
    _request_queue: queue.Queue[nothing]
    _rpc_metadata: Any
    call: Any
    is_active: bool
    def __init__(self, start_rpc, should_recover, should_terminate = ..., initial_request = ..., metadata = ..., throttle_reopen = ...) -> None: ...
    def _finalize(self, result) -> None: ...
    def _on_call_done(self, future) -> None: ...
    def _recoverable(self, method, *args, **kwargs) -> Any: ...
    def _recv(self) -> Any: ...
    def _reopen(self) -> None: ...
    def _send(self, request) -> None: ...
    def _should_recover(self, _1) -> Any: ...
    def _should_terminate(self, _1) -> Any: ...
    def _start_rpc(self, _1: Iterator) -> Any: ...
    def close(self) -> None: ...
    def recv(self) -> Any: ...
    def send(self, request) -> Any: ...

class _RequestQueueGenerator:
    __doc__: str
    _initial_request: Any
    _period: Any
    _queue: Any
    call: Any
    def __init__(self, queue, period = ..., initial_request = ...) -> None: ...
    def __iter__(self) -> Generator[Any, Any, None]: ...
    def _is_active(self) -> bool: ...

class _Throttle:
    __doc__: str
    _access_limit: Any
    _entry_lock: threading.Lock
    _past_entries: collections.deque
    _time_window: Any
    def __enter__(self) -> Any: ...
    def __exit__(self, *_) -> None: ...
    def __init__(self, access_limit, time_window) -> None: ...
    def __repr__(self) -> str: ...

def _never_terminate(future_or_error) -> bool: ...
