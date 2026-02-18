# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bracket caching utilities for save/load operations."""

import json
import os
import logging
from datetime import datetime


def save_bracket_to_cache(category, bracket, cache_dir):
    """Save bracket to JSON cache file.
    
    Args:
        category: Tournament category name
        bracket: List of (name1, name2, club1, club2) match tuples
        cache_dir: Directory to save cache files in
    
    Returns:
        Path to saved cache file
    
    Raises:
        OSError: If cache directory cannot be created or file cannot be written
    """
    logger = logging.getLogger(__name__)
    
    # Ensure cache directory exists
    os.makedirs(cache_dir, exist_ok=True)
    
    # Create cache data structure
    cache_data = {
        'timestamp': datetime.now().isoformat(),
        'category': category,
        'bracket': bracket
    }
    
    # Write to timestamped JSON file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    cache_file = os.path.join(cache_dir, f"bracket_{category}_{timestamp}.json")
    
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Bracket cached: {cache_file}")
        return cache_file
    except OSError as e:
        logger.error(f"Failed to save bracket cache: {e}")
        raise


def load_bracket_from_cache(cache_file):
    """Load bracket from JSON cache file.
    
    Args:
        cache_file: Path to cache JSON file
    
    Returns:
        List of (name1, name2, club1, club2) match tuples
    
    Raises:
        FileNotFoundError: If cache file does not exist
        json.JSONDecodeError: If cache file is invalid JSON
    """
    logger = logging.getLogger(__name__)
    
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        logger.info(f"Bracket loaded from cache: {cache_file}")
        return cache_data.get('bracket', [])
    except FileNotFoundError:
        logger.warning(f"Cache file not found: {cache_file}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid cache file format: {e}")
        raise


def clear_bracket_cache(cache_dir):
    """Delete all bracket cache files in directory.
    
    Args:
        cache_dir: Directory containing cache files
    
    Returns:
        Number of files deleted
    """
    logger = logging.getLogger(__name__)
    count = 0
    
    if not os.path.exists(cache_dir):
        logger.debug(f"Cache directory does not exist: {cache_dir}")
        return count
    
    try:
        for filename in os.listdir(cache_dir):
            if filename.startswith('bracket_') and filename.endswith('.json'):
                filepath = os.path.join(cache_dir, filename)
                os.remove(filepath)
                logger.debug(f"Deleted cache file: {filepath}")
                count += 1
    except OSError as e:
        logger.error(f"Error clearing cache directory: {e}")
    
    return count
