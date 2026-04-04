"""
Standardized API response helpers.
Provides consistent response format across all endpoints.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from flask import jsonify, request


def api_success(data: Any = None, message: str = None, status_code: int = 200,
                pagination: Dict = None) -> Tuple:
    """
    Creates a standardized success API response.

    Args:
        data: Data to return
        message: Optional success message
        status_code: HTTP code (default 200)
        pagination: Optional pagination info

    Returns:
        Tuple (response, status_code)
    """
    response = {
        'success': True,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    if message:
        response['message'] = message
    if data is not None:
        response['data'] = data
    if pagination:
        response['pagination'] = pagination
    return jsonify(response), status_code


def api_error(message: str, status_code: int = 400, errors: list = None,
              error_code: str = None, data: Any = None) -> Tuple:
    """
    Creates a standardized error API response.

    Args:
        message: Main error message
        status_code: HTTP error code (default 400)
        errors: List of detailed errors (optional)
        error_code: Internal error code (optional)
        data: Additional payload useful for troubleshooting (optional)

    Returns:
        Tuple (response, status_code)
    """
    response = {
        'success': False,
        'error': {
            'message': message,
            'status_code': status_code,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    }
    if errors:
        response['error']['details'] = errors
    if error_code:
        response['error']['code'] = error_code
    if data is not None:
        response['data'] = data
    return jsonify(response), status_code


def paginate(items: list, page: int = 1, per_page: int = 20,
             max_per_page: int = 100) -> Tuple[list, Dict]:
    """
    Generic pagination for lists.

    Args:
        items: List of elements
        page: Current page (1-based)
        per_page: Elements per page
        max_per_page: Maximum limit per page

    Returns:
        Tuple (paginated_items, pagination_info)
    """
    page = max(1, page)
    per_page = max(1, min(per_page, max_per_page))

    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)

    start = (page - 1) * per_page
    end = start + per_page

    paginated_items = items[start:end]

    pagination_info = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'has_next': page < total_pages,
        'has_prev': page > 1,
    }

    return paginated_items, pagination_info


def get_pagination_params() -> Tuple[int, int]:
    """
    Extracts pagination parameters from query string.

    Returns:
        Tuple (page, per_page)
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    return page, per_page

