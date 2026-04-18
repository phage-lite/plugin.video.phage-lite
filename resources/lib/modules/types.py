from typing import TypeAlias, TypeVar

__all__ = ["UrlParams", "T"]

UrlParams: TypeAlias = dict[str, str] | list[tuple[str, str]]
T = TypeVar('T')
