def get_bracket_rounds(participants):
    import copy
    import random
    random.shuffle(participants)
    pool = copy.deepcopy(participants)
    rounds = []
    current_round = [(p['Name'],) for p in pool]

    round_num = 1
    while len(current_round) > 1:
        next_round = []
        matches = []
        i = 0
        battle_num = 1
        while i < len(current_round):
            if i + 1 < len(current_round):
                p1 = current_round[i][0]
                p2 = current_round[i+1][0]
                matches.append((p1, p2))
                next_round.append((f"Winner from round {round_num} battle {battle_num}",))
                i += 2
                battle_num += 1
            else:
                # Odd participant, auto-advance
                p1 = current_round[i][0]
                next_round.append((p1,))
                i += 1
        rounds.append(matches)
        current_round = next_round
        round_num += 1
    return rounds
# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

# Moved from utils/bracket_utils.py

import random
import math
import sys
import os

# Add parent directory to path for libraries access
_parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from libraries.logging import get_logger
from ..data.repositories.config_repository import ConfigRepository

# module logger
logger = get_logger('bracket_utils')

# Global config instance (can be replaced or reloaded as needed)
import os
_current_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_current_dir, '..', '..', 'config', 'bracket_config.xlsx')
bracket_config = None

def set_bracket_config(path):
    global bracket_config
    bracket_config = ConfigRepository(path)

def ensure_config_loaded():
    global bracket_config
    if bracket_config is None:
        bracket_config = ConfigRepository(CONFIG_PATH)

def get_weight_class(weight, gender):
    ensure_config_loaded()
    return bracket_config.get_weight_class(weight, gender)

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
    """Create the first round by pairing participants."""
    pool = participants[:]
    first_round = []
    while len(pool) > 1:
        first_round.append((pool[0]['Name'], pool[1]['Name']))
        pool = pool[2:]
    if pool:
        first_round.append((pool[0]['Name'], 'BYE'))
    return first_round

def _winner_label(round_num, match_num):
    """Generate winner label for a match."""
    return f"Winner of Round {round_num+1} Battle {match_num+1}"

def _process_match_pair(p1, p2, round_num, i):
    """Process a pair of matches and return the next round entry."""
    if p1[1] == 'BYE':
        return (p1[0], _winner_label(round_num, i+2))
    elif p2[1] == 'BYE':
        return (p2[0], _winner_label(round_num, i+1))
    else:
        return (_winner_label(round_num, i+1), _winner_label(round_num, i+2))

def _process_odd_match(p1, round_num, i):
    """Process an odd match left over."""
    if p1[1] == 'BYE':
        return (p1[0], 'BYE')
    else:
        return (_winner_label(round_num, i+1), 'BYE')

def make_bracket(participants):
    random.shuffle(participants)
    first_round = _create_first_round(participants)
    rounds = [first_round]
    round_num = 1
    
    # Build subsequent rounds, moving BYEs forward until they face a real opponent
    while len(rounds[-1]) > 1:
        prev_round = rounds[-1]
        next_round = []
        for i in range(0, len(prev_round), 2):
            if i+1 < len(prev_round):
                p1, p2 = prev_round[i], prev_round[i+1]
                next_round.append(_process_match_pair(p1, p2, round_num, i))
            else:
                p1 = prev_round[i]
                next_round.append(_process_odd_match(p1, round_num, i))
        rounds.append(next_round)
        round_num += 1

    # Return only the first round for drawing, but also return all rounds for advanced use
    # For compatibility, return the first round as the bracket
    return rounds[0]


# Step 2: Add export_all_brackets function
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
    sorted_clubs = sorted(club_groups.keys(), 
                         key=lambda c: len(club_groups[c]), 
                         reverse=True)
    
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


def _snake_seed_list(size: int) -> list:
    """DEPRECATED: Use _generate_seed_order() instead."""
    seeds = [1, 2]
    while len(seeds) < size:
        mirror_sum = len(seeds) * 2 + 1
        expanded = []
        for s in seeds:
            expanded.extend([s, mirror_sum - s])
        seeds = expanded
    return seeds


def _seed_positions(slots: int) -> list:
    """DEPRECATED: Use _compute_balanced_bracket() instead."""
    seed_layout = _snake_seed_list(slots)
    positions = [0] * slots
    for slot_index, seed in enumerate(seed_layout):
        positions[seed - 1] = slot_index
    return positions


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


def _compute_snake_bracket(participants):
    """Return balanced bracket using 3-layer system.
    
    This is now a wrapper around _compute_balanced_bracket() which implements:
    - Layer 1: List Optimizer (club distribution, BYE padding)
    - Layer 2: Seed Generator (recursive snake seeding)
    - Layer 3: Slot Assignment (map optimized list to seed order)
    
    Guarantees:
    ✓ Power-of-two bracket structure
    ✓ Balanced tree (no fighter can skip multiple rounds)
    ✓ No BYE vs BYE matches in round 1
    ✓ Club separation heuristic
    ✓ Deterministic output
    """
    return _compute_balanced_bracket(participants)


def export_all_brackets(participants, event_year=None):
    """
    Groups participants by (gender, age group, weight class),
    and returns a dict: {bracket_key: {'fighters': [...], 'bracket': [...]}}
    """
    from collections import defaultdict
    ensure_config_loaded()
    if event_year is None:
        event_year = bracket_config.get_event_year()
    brackets = defaultdict(lambda: {'fighters': [], 'bracket': []})
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
            weight_class = get_weight_class(weight, gender_norm)
        except Exception as e:
            logger.warning(f"Weight class lookup failed for {name!r}: {e}")
            weight_class = None

        # If either dimension is missing, log a warning and put into an Unassigned bracket
        if age_group is None or (weight_class is None) or (str(weight_class).lower() == 'unknown'):
            unassigned_count += 1
            logger.warning(f"Participant {name!r} could not be assigned to a bracket (age_group={age_group}, weight_class={weight_class}).")
            bracket_key = f"Unassigned | {gender_norm} | {age_group or 'UnknownAge'} | {weight_class or 'UnknownWeight'}"
            brackets[bracket_key]['fighters'].append(p)
            continue

        # Normal bracket key
        bracket_key = f"{gender_norm} | {age_group} | {weight_class}"
        brackets[bracket_key]['fighters'].append(p)
    # Default behavior: use snake seeding to reduce same-club matches and BYE collisions.
    # Special-case: if number of fighters equals the slot count (power of two),
    # then use simple interleaving by club and sequential pairing (almost-random,
    # but preserves club separation) to avoid unnecessary seeding complexity.
    for key in brackets:
        fighters = brackets[key]['fighters']
        n = len(fighters)
        # Always use snake seeding for balanced brackets (pads to next power-of-2 with BYEs)
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
