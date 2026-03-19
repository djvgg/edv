# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

import math
import os
import sys

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger  # noqa: E402
from utils.helpers import normalize_gender  # noqa: E402
from backend.data.repositories.config_repository import (  # noqa: E402
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
    group = bracket_config.get_age_group(int(float(birth_year)))
    if group is None:
        if age_num >= 18:
            group = '18+'
        elif age_num >= 15:
            group = 'U18'
        elif age_num >= 13:
            group = 'U15'
        elif age_num >= 11:
            group = 'U13'
        elif age_num >= 9:
            group = 'U11'
        else:
            group = 'U9'
        logger.info(f"Age group not found in config for birth_year={birth_year}; mathematically fallback to '{group}'")
    return group


def validate_age_from_birthyear(birthyear, min_age=6, max_age=120, event_year=None):
    """
    Validates a participant's age based on birthyear and returns detailed validation info.
    
    SINGLE SOURCE OF TRUTH for age validation across the app.
    
    Args:
        birthyear: Birth year as integer (e.g., 2018)
        min_age: Minimum valid age (default 6)
        max_age: Maximum valid age (default 120)
        event_year: Event year for age calculation (uses config default if None)
    
    Returns:
        Tuple: (age_group, calculated_age, is_valid, rejection_reason)
        Examples:
            (2018, None, ...) → ('U13', 8, True, None)
            (2001, None, ...) → ('18+', 25, True, None)
            (2026, None, ...) → ('18+', 0, True, None)  # Fallback for future births
            (1900, None, ...) → (None, 126, False, 'too old (126 years)')
            (None, None, ...) → (None, None, False, 'no age/birthyear')
    """
    ensure_config_loaded()
    
    # Step 1: Validate birthyear exists
    if birthyear is None or birthyear == '':
        return None, None, False, "no age/birthyear"
    
    # Step 2: Parse birthyear
    try:
        birthyear_int = int(birthyear)
    except (ValueError, TypeError):
        return None, None, False, f"invalid birthyear: {birthyear}"
    
    # Step 3: Get event year for calculation
    if event_year is None:
        event_year = bracket_config.get_event_year()
    if event_year is None:
        return None, None, False, "event year not configured"
    
    # Step 4: Calculate age
    calculated_age = event_year - birthyear_int
    
    # Step 5: Check hard bounds (6-120 years old)
    if calculated_age < min_age:
        return None, calculated_age, False, f"too young ({calculated_age} years, minimum {min_age})"
    if calculated_age > max_age:
        return None, calculated_age, False, f"too old ({calculated_age} years, maximum {max_age})"
    
    # Step 6: Get age group (with fallback)
    age_group = get_age_group(calculated_age, event_year)
    
    # Step 7: Return success (age_group may still be None in edge cases, but valid within bounds)
    return age_group, calculated_age, True, None


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
    
    U9/U11: Created without gender separation, sorted by weight
    U13+: Created by (gender, age_group, weight_class)
    
    Actual rendering (pools vs KO) is determined by GenerationMethodScreen assignments.
    """
    from collections import defaultdict
    ensure_config_loaded()
    if event_year is None:
        event_year = bracket_config.get_event_year()
    
    brackets = defaultdict(lambda: {'fighters': [], 'bracket': [], 'pool_size': None})
    
    # Group participants
    for p in participants:
        raw_gender = p.get('Gender', p.get('gender', 'Unknown'))
        
        # Explicit priority to 'Birthyear' since it's the intended field, fallback to 'Age'
        birth_year = p.get('Birthyear', p.get('BirthYear', p.get('birthyear')))
        if birth_year in (None, ''):
            birth_year = p.get('Age', p.get('age'))
            
        weight = p.get('Weight', p.get('weight', 0))
        name = p.get('Name', p.get('name', ''))
        doublestart = str(p.get('Doublestart', p.get('doublestart', 'nein'))).strip().lower()

        # Normalize gender to 'm'/'w' to match config group names
        gender_norm = normalize_gender(raw_gender) if raw_gender else 'Unknown'

        # Determine age group
        age_group = None
        if birth_year is not None:
            try:
                age_group = bracket_config.get_age_group(int(float(birth_year)))
            except Exception as e:
                logger.warning(f"Could not determine age group for birth_year {birth_year}: {e}")

        if age_group is None:
            if birth_year is not None:
                try:
                    current_year_num = event_year if event_year else bracket_config.get_event_year()
                    calc_age = int(current_year_num) - int(float(birth_year))
                    if calc_age >= 18:
                        age_group = '18+'
                    elif calc_age >= 15:
                        age_group = 'U18'
                    elif calc_age >= 13:
                        age_group = 'U15'
                    elif calc_age >= 11:
                        age_group = 'U13'
                    elif calc_age >= 9:
                        age_group = 'U11'
                    else:
                        age_group = 'U9'
                    # Adults (18+) are intentionally absent from the youth eligibility config — expected
                    log_fn = logger.debug if age_group == '18+' else logger.warning
                    log_fn(f"Birth year {birth_year!r} not in age eligibility config, fallback to '{age_group}'")
                except Exception:
                    logger.warning(f"Missing/unknown birth year {birth_year!r} for {name!r}, defaulting to '18+'")
                    age_group = '18+'
            else:
                logger.warning(f"Missing age for {name!r}, defaulting to '18+'")
                age_group = '18+'

        # Build list of age groups this participant goes into
        age_groups_to_enter = [age_group]

        if doublestart in ('höher', 'hoeher', 'higher') and birth_year is not None:
            all_eligible = bracket_config.get_all_eligible_age_groups(birth_year)
            if len(all_eligible) > 1:
                # Primary group is the first eligible; "höher" = next one up
                primary_idx = all_eligible.index(age_group) if age_group in all_eligible else 0
                if primary_idx + 1 < len(all_eligible):
                    higher_group = all_eligible[primary_idx + 1]
                    age_groups_to_enter.append(higher_group)
                    logger.info(f"Doublestart höher: {name!r} → {age_group} + {higher_group}")
                else:
                    logger.warning(f"Doublestart höher: {name!r} already in highest eligible group ({age_group}), no higher group available")
        
        elif doublestart in ('doppel', 'double', 'duplex', 'ja') and birth_year is not None:
            all_eligible = bracket_config.get_all_eligible_age_groups(birth_year)
            if len(all_eligible) > 1:
                # "doppel"/"ja" = add to ALL eligible age groups
                age_groups_to_enter = all_eligible
                logger.info(f"Doublestart doppel/ja: {name!r} → entered in {len(all_eligible)} age groups: {age_groups_to_enter}")
            else:
                logger.debug(f"Doublestart doppel/ja: {name!r} has only one eligible age group, no duplication needed")

        # Create participant copy with birth_year
        p_copy = dict(p)
        p_copy['Age'] = birth_year
        
        # Mark as doublestart copy if participant is in multiple age groups (legitimate duplicate)
        if len(age_groups_to_enter) > 1:
            p_copy['is_doublestart_copy'] = True

        # Add fighter to each age group bracket
        for ag in age_groups_to_enter:
            if ag in ('U9', 'U11'):
                bracket_key = f"{ag}"
            else:
                try:
                    weight_class = bracket_config.get_weight_class(weight, gender_norm, ag)
                except Exception as e:
                    logger.warning(f"Weight class lookup failed for {name!r} (age_group={ag}): {e}")
                    weight_class = 'unknown'

                if weight_class is None or str(weight_class).lower() == 'unknown':
                    logger.warning(f"Missing weight class for {name!r} (age_group={ag})")
                    weight_class = 'unknown'

                bracket_key = f"{gender_norm} | {ag} | {weight_class}"

            brackets[bracket_key]['fighters'].append(dict(p_copy))
    
    # Post-process: sort U9/U11 by weight, set pool_size
    for key in list(brackets.keys()):
        fighters = brackets[key]['fighters']
        
        # For U9/U11: sort by weight and set pool_size
        if key in ('U9', 'U11'):
            # Sort by weight for balanced pools
            fighters_sorted = sorted(fighters, key=lambda x: x.get('Weight', 0))
            brackets[key]['fighters'] = fighters_sorted
            
            # Get pool size from config
            pool_size = get_pool_size(key)
            if pool_size is not None:
                brackets[key]['pool_size'] = pool_size
                logger.info(f"Bracket {key}: configured pool size = {pool_size}")
        else:
            # For U13+: generate KO bracket structure
            try:
                bracket = _compute_snake_bracket(fighters)
            except Exception as e:
                logger.warning(f"Bracket generation failed for {key!r}: {e}")
                # Fallback: simple sequential pairing
                ordered = _interleave_by_club(fighters)
                pairs = []
                pool = ordered[:]
                while len(pool) > 1:
                    a = pool.pop(0)
                    b = pool.pop(0)
                    pairs.append((a.get('Name'), b.get('Name')))
                if pool:
                    pairs.append((pool[0].get('Name'), 'BYE'))
                bracket = pairs
            
            brackets[key]['bracket'] = bracket
    
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
    """Create a Freilos placeholder fighter."""
    return {'Name': 'Freilos', 'Verein': '', 'id': -1}


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
            name1 = p1.get('Name') if p1 else 'Freilos'
            name2 = p2.get('Name') if p2 else 'Freilos'
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


def merge_u9_u11_pools(brackets):
    """Reverse of split_u9_u11_into_pools.

    Merges "U9 | Pool N" / "U11 | Pool N" keys back into single "U9" / "U11"
    buckets so GroupPreviewScreen always shows one combined group.
    Fighters are re-sorted by weight and pool_size is restored from config.
    """
    ensure_config_loaded()
    merged = {}
    collected = {}  # {'U9': [...fighters], 'U11': [...fighters]}

    for key, data in brackets.items():
        age_group = None
        if key.startswith('U9 | Pool'):
            age_group = 'U9'
        elif key.startswith('U11 | Pool'):
            age_group = 'U11'

        if age_group:
            if age_group not in collected:
                collected[age_group] = []
            collected[age_group].extend(data.get('fighters', []))
        else:
            merged[key] = data

    for age_group, fighters in collected.items():
        fighters_sorted = sorted(fighters, key=lambda x: x.get('Weight', 0))
        pool_size = get_pool_size(age_group)
        merged[age_group] = {
            'fighters': fighters_sorted,
            'bracket': [],
            'pool_size': pool_size,
        }
        logger.info(f"[POOL MERGE] {len(fighters_sorted)} fighters merged back into {age_group!r}")

    return merged


def split_u9_u11_into_pools(brackets):
    """Replace the single U9/U11 bracket entry with individual pool brackets.

    Precondition: fighters list is already sorted by weight
    (export_all_brackets guarantees this).

    Example (pool_size=4, 16 fighters in "U11"):
        "U11 | Pool 1" → 4 lightest fighters
        "U11 | Pool 2" → next 4
        ...

    Brackets without pool_size configured (or 0 fighters) are kept unchanged.
    """
    new_brackets = {}
    for key, data in brackets.items():
        if key not in ('U9', 'U11'):
            new_brackets[key] = data
            continue

        fighters = data.get('fighters', [])
        pool_size = data.get('pool_size')

        if not pool_size or not fighters:
            new_brackets[key] = data
            continue

        # Always re-sort by weight (defensive: handles in-place weight edits)
        fighters = sorted(fighters, key=lambda x: x.get('Weight', 0))

        # Even distribution: ceil(n / pool_size) pools, remainder spread across first pools
        n = len(fighters)
        n_pools = math.ceil(n / pool_size)
        base = n // n_pools
        extra = n % n_pools  # first `extra` pools get base+1 fighters

        pool_sizes = [base + 1 if i < extra else base for i in range(n_pools)]

        start = 0
        for pool_num, size in enumerate(pool_sizes, 1):
            chunk = fighters[start: start + size]
            start += size
            pool_key = f"{key} | Pool {pool_num}"
            new_brackets[pool_key] = {
                'fighters': chunk,
                'bracket': [],
                'pool_size': None,
            }
            logger.info(f"[POOL SPLIT] {key} → {pool_key}: {len(chunk)} fighters")

    return new_brackets


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
