# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Search utilities for filtering items by search terms.

Provides filtering logic with support for:
- Multiple search terms (space-separated)
- AND logic (all terms must match)
- Case-insensitive matching
- Logging support
"""

from utils.logging import get_logger

logger = get_logger('search_utils')


def filter_items(items, search_term, key_func=None):
    """
    Filter items by search term with support for multiple terms.
    
    Args:
        items: List of strings or objects to filter
        search_term: Search string (space-separated terms for AND logic)
        key_func: Optional function to extract searchable text from item
                 (default: str if items are strings, item['key'] if dicts)
    
    Returns:
        Tuple of (filtered_items, matched_count, search_terms)
    """
    # Handle empty or placeholder search
    search_term = search_term.lower().strip() if search_term else ""
    
    if not search_term:
        return items, len(items), []
    
    # Parse search terms (split by whitespace)
    search_terms = [t for t in search_term.split() if t]
    
    if not search_terms:
        return items, len(items), []
    
    # Filter items
    matched = []
    
    for item in items:
        # Extract searchable text
        if key_func:
            text = key_func(item).lower()
        elif isinstance(item, str):
            text = item.lower()
        elif isinstance(item, dict):
            text = item.get('key', str(item)).lower()
        else:
            text = str(item).lower()
        
        # Check if ALL search terms match (AND logic)
        if all(term in text for term in search_terms):
            matched.append(item)
    
    return matched, len(matched), search_terms


def format_search_debug(matched_count, search_terms, total_items=None):
    """
    Format debug log message for search results.
    
    Args:
        matched_count: Number of items matched
        search_terms: List of search terms that were applied
        total_items: Optional total items scanned
    
    Returns:
        Formatted log string
    """
    if not search_terms:
        return "Search cleared"
    
    msg = f"Search terms: {search_terms}, found {matched_count} items"
    if total_items is not None:
        msg += f" (of {total_items})"
    return msg
