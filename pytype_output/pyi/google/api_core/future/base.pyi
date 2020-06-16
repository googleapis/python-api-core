# (generated with --quick)

from typing import Any

abc: module
six: module

class Future(metaclass=abc.ABCMeta):
    __doc__: str
    @abstractmethod
    def add_done_callback(self, fn) -> Any: ...
    @abstractmethod
    def cancel(self) -> Any: ...
    @abstractmethod
    def cancelled(self) -> Any: ...
    @abstractmethod
    def done(self) -> Any: ...
    @abstractmethod
    def exception(self, timeout = ...) -> Any: ...
    @abstractmethod
    def result(self, timeout = ...) -> Any: ...
    @abstractmethod
    def running(self) -> Any: ...
    @abstractmethod
    def set_exception(self, exception) -> Any: ...
    @abstractmethod
    def set_result(self, result) -> Any: ...
