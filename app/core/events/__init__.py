# This subscription registry is GLOBAL for all the event buses created
_subscription_registry = []


def subscribe(event_name: str):
    def decorator(func):
        _subscription_registry.append((event_name, func))
        return func

    return decorator
