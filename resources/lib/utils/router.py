from __future__ import annotations

import inspect
import re
import sys
from collections.abc import Callable
from urllib.parse import parse_qsl, quote, unquote, urlencode

BASE: str = "plugin://plugin.video.bacterio"

_routes: list[tuple[re.Pattern[str], list[str], Callable[..., None]]] = []


def route(pattern: str) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Decorator to register a handler for a URL path pattern.

    Path variables use :name syntax: @route("/movies/genre/:genre_id/")
    Routes are matched in registration order — register specific routes before wildcards.
    """
    regex, param_names = _compile(pattern)

    def decorator(fn: Callable[..., None]) -> Callable[..., None]:
        _routes.append((regex, param_names, fn))
        return fn

    return decorator


def dispatch() -> None:
    """Match the current plugin URL path to a registered handler and call it."""
    path = sys.argv[0].removeprefix(BASE) or "/"
    query: dict[str, str] = dict(parse_qsl(sys.argv[2].lstrip("?")))
    for regex, param_names, handler in _routes:
        m = regex.fullmatch(path)
        if m is None:
            continue
        path_vars = {n: unquote(v) for n, v in zip(param_names, m.groups())}
        handler(**_build_kwargs(handler, path_vars, query))
        return
    from utils.notifications import error
    error(f"Unknown path: {path}")


def url(pattern: str, **kwargs: str | int | float) -> str:
    """Build a plugin:// URL from a path pattern, filling :variables and appending remaining as query params.

    Example:
        url("/movies/genre/:genre_id/", genre_id=28, genre_name="Action", page=2)
        -> "plugin://plugin.video.bacterio/movies/genre/28/?genre_name=Action&page=2"
    """
    remaining = dict(kwargs)
    parts: list[str] = []
    for segment in pattern.split("/"):
        if segment.startswith(":"):
            name = segment[1:]
            parts.append(quote(str(remaining.pop(name)), safe=""))
        else:
            parts.append(segment)
    result = "/".join(parts)
    if remaining:
        result += "?" + urlencode({k: str(v) for k, v in remaining.items()})
    return BASE + result


def _compile(pattern: str) -> tuple[re.Pattern[str], list[str]]:
    names: list[str] = []
    regex_parts: list[str] = []
    for segment in pattern.split("/"):
        if segment.startswith(":"):
            names.append(segment[1:])
            regex_parts.append("([^/]+)")
        else:
            regex_parts.append(re.escape(segment))
    return re.compile("/".join(regex_parts)), names


def _build_kwargs(
    handler: Callable[..., None],
    path_vars: dict[str, str],
    query: dict[str, str],
) -> dict[str, object]:
    sig = inspect.signature(handler)
    annotations: dict[str, object] = getattr(handler, "__annotations__", {})
    result: dict[str, object] = {}
    for name in sig.parameters:
        if name in path_vars:
            result[name] = _coerce(path_vars[name], annotations.get(name))
        elif name in query:
            result[name] = _coerce(query[name], annotations.get(name))
        # else: use the parameter's default value
    return result


def _coerce(value: str, annotation: object) -> object:
    if annotation is int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
    origin = getattr(annotation, "__origin__", None)
    if origin is list:
        args: tuple[object, ...] = getattr(annotation, "__args__", ())
        item_type = args[0] if args else str
        parts = [p.strip() for p in value.split(",") if p.strip()]
        if item_type is int:
            return [int(p) for p in parts if p.isdigit()]
        return parts
    return value
