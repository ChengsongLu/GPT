from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar


T = TypeVar("T")


def branch_name_sort_key(name: str | None) -> tuple[int, str]:
    normalized = (name or "").strip()
    return (0 if normalized.lower() == "main" else 1, normalized.lower())


def sort_branch_names(names: Iterable[str]) -> list[str]:
    return sorted(names, key=branch_name_sort_key)


def sort_branches(items: Iterable[T], *, name_attr: str = "name", default_attr: str = "is_default") -> list[T]:
    def _key(item: T) -> tuple[int, int, str]:
        name = str(getattr(item, name_attr, "") or "").strip()
        is_default = bool(getattr(item, default_attr, False))
        return (
            0 if name.lower() == "main" else 1,
            0 if is_default else 1,
            name.lower(),
        )

    return sorted(items, key=_key)
