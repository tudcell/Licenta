"""Shared pagination helpers used across services and API layers."""

from __future__ import annotations

from math import ceil
from typing import Any, Sequence


DEFAULT_MAX_PER_PAGE = 100


def normalize_pagination_inputs(page: int, per_page: int, *, max_per_page: int = DEFAULT_MAX_PER_PAGE) -> tuple[int, int]:
    """Clamp pagination inputs to safe values."""
    safe_page = max(1, page)
    safe_per_page = max(1, min(per_page, max_per_page))
    return safe_page, safe_per_page


def build_pagination_metadata(page: int, per_page: int, total: int) -> dict[str, int | bool]:
    """Build pagination metadata for API responses."""
    total_pages = max(1, ceil(total / per_page))
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_next": page * per_page < total,
        "has_prev": page > 1,
    }


def paginate_sequence(
    items: Sequence[Any],
    page: int,
    per_page: int,
    *,
    max_per_page: int = DEFAULT_MAX_PER_PAGE,
) -> tuple[list[Any], dict[str, int | bool]]:
    """Return a page of items along with consistent pagination metadata."""
    safe_page, safe_per_page = normalize_pagination_inputs(page, per_page, max_per_page=max_per_page)
    total_items = len(items)
    start_index = (safe_page - 1) * safe_per_page
    end_index = start_index + safe_per_page
    paginated_items = list(items[start_index:end_index])
    pagination = build_pagination_metadata(safe_page, safe_per_page, total_items)
    return paginated_items, pagination
