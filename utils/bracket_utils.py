# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

import math
import os
import sys

# Add parent directory to path for libraries access
_parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from utils.logging import get_logger  # noqa: E402
from edv_backend.backend.data.repositories.config_repository import (  # noqa: E402
    ConfigRepository,
)

# module logger
logger = get_logger('bracket_utils')

# Global config instance (can be replaced or reloaded as needed)
_current_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_current_dir, '..', 'config', 'bracket_config.xlsx')
bracket_config = None

def set_bracket_config(path):
    global bracket_config
    bracket_config = ConfigRepository(path)

def ensure_config_loaded():
    global bracket_config
    if bracket_config is None:
        bracket_config = ConfigRepository(CONFIG_PATH)

def get_weight_class(weight, gender, age_group=None):
    ensure_config_loaded()
    return bracket_config.get_weight_class(weight, gender, age_group)

def get_pool_size(age_group):
    """
    Get the pool size configuration for U9 and U11 age groups.
    
    Args:
        age_group: The age group (e.g., 'U9', 'U11')
    
    Returns:
        The pool size as integer, or None if not configured
    """
    ensure_config_loaded()
    return bracket_config.get_pool_size(age_group)

def get_age_group(age, event_year=None):
    """
    Returns the age group (e.g., U13, U15, etc.) for a given age and event year.
    If age is missing or invalid, returns None.
    If event_year is None, uses the value from config.
    """
    ensure_config_loaded()
    if age is None:
        logger.warning('Missing age for participant when determining age group')
        return None
    # handle NaN floats
    try:
        if isinstance(age, float) and math.isnan(age):
            logger.warning('Age is NaN for participant when determining age group')
            return None
    except Exception:
        pass
    if event_year is None:
        event_year = bracket_config.get_event_year()
    if event_year is None:
        raise ValueError("Event year not set in config or argument.")
    try:
        age_num = int(age)
    except Exception:
        logger.warning(f'Invalid age value: {age!r}')
        return None
    birth_year = event_year - age_num
    group = bracket_config.get_age_group(birth_year)
    if group is None:
        # Fallback: treat adults (age >= 18) as '18+' if config lacks older birth years
        if age_num >= 18:
            logger.info(f"Age group not found for birth_year={birth_year}; falling back to '18+' for age={age_num}")
            return '18+'
    return group


def _create_first_round(participants):
    """Create the first round by pairing participants to nearest power of 2."""
    pool = participants[:]
    first_round = []
    
    # Calculate next power of 2
    num_matches = math.ceil(len(pool) / 2)  # Number of matches needed
    
    # Create matches
    for i in range(num_matches):
        if i * 2 + 1 < len(pool):
            first_round.append((pool[i*2]['Name'], pool[i*2 + 1]['Name']))
        elif i * 2 < len(pool):
            first_round.append((pool[i*2]['Name'], 'BYE'))
        else:
            first_round.append(('BYE', 'BYE'))
    
    return first_round


def make_bracket(participants):
    """Generate a balanced tournament bracket using the 3-layer system.
    
    This implementation:
    - Groups fighters by club
    - Distributes them round-robin to separate clubs
    - Generates a recursive snake seed order
    - Maps fighters into seed slots for balanced matchups
    
    Returns: List of (fighter_name, opponent_name) tuples for round 1
    """
    if not participants:
        return []
    
    # Use the balanced 3-layer bracket system
    return _compute_snake_bracket(participants)


def export_all_brackets(participants, event_year=None):
    """
    Groups participants by (gender, age group, weight class),
    and returns a dict: {bracket_key: {'fighters': [...], 'bracket': [...], 'pool_size': ...}}
    
    For U9 and U11 groups, includes pool_size from configuration.
    """
    from collections import defaultdict
    ensure_config_loaded()
    if event_year is None:
        event_year = bracket_config.get_event_year()
    brackets = defaultdict(lambda: {'fighters': [], 'bracket': [], 'pool_size': None})
    unassigned_count = 0
    # Group participants
    for p in participants:
        raw_gender = p.get('Gender', p.get('gender', 'Unknown'))
        age = p.get('Age', p.get('age'))
        weight = p.get('Weight', p.get('weight'))
        name = p.get('Name', p.get('name'))

        # Normalize gender for weight lookup
        gender_norm = str(raw_gender).strip()
        if not gender_norm:
            gender_norm = 'Unknown'

        # Determine age group and weight class
        age_group = get_age_group(age, event_year)
        try:
            weight_class = get_weight_class(weight, gender_norm, age_group)
        except Exception as e:
            logger.warning(f"Weight class lookup failed for {name!r}: {e}")
            weight_class = None

        # If either dimension is missing, log a warning and put into an Unassigned bracket
        # Note: U9 and U11 participants have age_group but weight_class='no-class' which is valid
        if age_group is None or (weight_class is None) or (str(weight_class).lower() == 'unknown'):
            unassigned_count += 1
            logger.warning(f"Participant {name!r} could not be assigned to a bracket (age_group={age_group}, weight_class={weight_class}).")
            bracket_key = f"Unassigned | {gender_norm} | {age_group or 'UnknownAge'} | {weight_class or 'UnknownWeight'}"
            brackets[bracket_key]['fighters'].append(p)
            continue

        # Normal bracket key
        bracket_key = f"{gender_norm} | {age_group} | {weight_class}"
        brackets[bracket_key]['fighters'].append(p)
    
    # Generate brackets and set pool sizes
    for key in brackets:
        fighters = brackets[key]['fighters']
        
        # Extract age_group from bracket key to get pool size if needed
        parts = key.split(' | ')
        if len(parts) >= 2:
            age_group = parts[1]
            pool_size = get_pool_size(age_group)
            if pool_size is not None:
                brackets[key]['pool_size'] = pool_size
                logger.info(f"Bracket {key}: configured pool size = {pool_size}")
        
        # Generate bracket - use snake seeding for balanced brackets
        try:
            brackets[key]['bracket'] = _compute_snake_bracket(fighters)
        except Exception as e:
            logger.warning(f"Bracket generation failed for {key!r}: {e}")
            # Fallback: simple sequential pairing without randomization
            ordered = _interleave_by_club(fighters)
            pairs = []
            pool = ordered[:]
            while len(pool) > 1:
                a = pool.pop(0)
                b = pool.pop(0)
                pairs.append((a.get('Name'), b.get('Name')))
            if pool:
                pairs.append((pool[0].get('Name'), 'BYE'))
            brackets[key]['bracket'] = pairs
    
    
    if unassigned_count:
        logger.warning(f"Total unassigned participants: {unassigned_count}")
    return dict(brackets)


# Advanced bracket generation functions

def _next_pow2(n: int) -> int:
    """Compute next power of 2 >= n. Minimum returns 2 (can't have 1-slot bracket)."""
    if n <= 2:
        return 2
    p = 2
    while p < n:
        p <<= 1
    return p


def _generate_seed_order(bracket_size: int) -> list:
    """Generate snake seed order recursively.
    
    Base case: S(2) = [1, 2]
    Recursive: for S(n), take S(n/2) and expand each x to [x, n+1-x]
    
    Example S(16):
    [1, 9, 5, 13, 3, 11, 7, 15, 2, 10, 6, 14, 4, 12, 8, 16]
    """
    if bracket_size == 1:
        return [1]
    if bracket_size == 2:
        return [1, 2]
    
    half = bracket_size // 2
    prev = _generate_seed_order(half)
    result = []
    
    for x in prev:
        result.append(x)
        result.append(bracket_size + 1 - x)
    
    return result


def _group_by_club(participants: list) -> dict:
    """Group fighters by club."""
    club_map = {}
    for p in participants:
        club = p.get('Verein') or p.get('club') or p.get('Club') or '__NO_CLUB__'
        if club not in club_map:
            club_map[club] = []
        club_map[club].append(p)
    return club_map


def _create_bye_fighter() -> dict:
    """Create a BYE placeholder fighter."""
    return {'Name': 'BYE', 'Verein': 'BYE', 'id': -1}


def _distribute_round_robin(club_groups: dict) -> list:
    """Distribute fighters round-robin by club.
    
    Takes fighters from each club in turn to spread them out.
    """
    optimized = []
    clubs = list(club_groups.keys())
    
    # Keep going while any club has fighters
    while any(club_groups[club] for club in clubs):
        for club in clubs:
            if club_groups[club]:
                optimized.append(club_groups[club].pop(0))
    
    return optimized


def _compute_balanced_bracket(participants: list) -> list:
    """Generate balanced tournament bracket using 3-layer system.
    
    Layer 1: Optimize fighter list (group by club, round-robin distribution)
    Layer 2: Generate seed order (recursive snake seeding)
    Layer 3: Assign fighters to seed slots
    
    Returns: List of (fighter_name, opponent_name) tuples for round 1
    """
    n = len(participants)
    if n == 0:
        return []
    
    # STEP 1: Compute target bracket size
    bracket_size = _next_pow2(n)
    bye_count = bracket_size - n
    
    # STEP 2-3: Group by club and sort by size (descending)
    club_map = _group_by_club(participants)
    # Create mutable copies for distribution
    club_groups = {club: fighters[:] for club, fighters in club_map.items()}
    
    # STEP 4: Round-robin distribution
    optimized = _distribute_round_robin(club_groups)
    
    # STEP 5: Append BYEs
    for _ in range(bye_count):
        optimized.append(_create_bye_fighter())
    
    # STEP 6: Generate seed order
    seed_order = _generate_seed_order(bracket_size)
    
    # STEP 7: Assign fighters to seed slots
    bracket_slots = [None] * bracket_size
    for i, seed_num in enumerate(seed_order):
        if i >= len(optimized):
            break
        slot_index = seed_num - 1
        if 0 <= slot_index < bracket_size:
            bracket_slots[slot_index] = optimized[i]
    
    # Convert slot pairs to match tuples
    bracket = []
    for i in range(0, bracket_size, 2):
        if i + 1 < bracket_size:
            p1 = bracket_slots[i]
            p2 = bracket_slots[i + 1]
            name1 = p1.get('Name') if p1 else 'BYE'
            name2 = p2.get('Name') if p2 else 'BYE'
            bracket.append((name1, name2))
    
    return bracket


def _compute_snake_bracket(participants):
    """Return balanced bracket using 3-layer system.
    
    This implements:
    - Layer 1: List Optimizer (club distribution, BYE padding)
    - Layer 2: Seed Generator (recursive snake seeding)
    - Layer 3: Slot Assignment (map optimized list to seed order)
    
    Guarantees:
    - Power-of-two bracket structure
    - Balanced tree (no fighter can skip multiple rounds)
    - No BYE vs BYE matches in round 1
    - Club separation heuristic
    - Deterministic output
    """
    return _compute_balanced_bracket(participants)


def _interleave_by_club(participants):
    """Interleave participants by club to reduce same-club pairings."""
    buckets = {}
    order = []
    for p in participants:
        # club may be under 'Verein' or 'club' key
        club = p.get('Verein') or p.get('club') or p.get('Club') or None
        key = club if club else f"__NO_CLUB_{id(p)}"
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(p)

    interleaved = []
    while True:
        added_any = False
        for key in order:
            if buckets[key]:
                interleaved.append(buckets[key].pop(0))
                added_any = True
        if not added_any:
            break
    return interleaved
