from __future__ import annotations

import functools


def requires(*args, **kwargs):
    """A decorator to link tests to requirement IDs. No-op at runtime."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*func_args, **func_kwargs):
            return func(*func_args, **func_kwargs)

        return wrapper

    return decorator
