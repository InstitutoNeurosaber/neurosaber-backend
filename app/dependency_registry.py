from fastapi_injector import request_scope
from injector import Injector


class DependencyRegistry:
    def __init__(self):
        self._registry = []
        self._injector = None

    def register(self, interface, to=None, scope=request_scope):
        self._registry.append({"interface": interface, "to": to, "scope": scope})

    def bind_all(self, injector: Injector):
        self._injector = injector  # Store reference for use in events
        for bidings in self._registry:
            injector.binder.bind(**bidings)


registry = DependencyRegistry()
