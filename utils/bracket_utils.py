# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

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
# Utility functions for bracket and pool logic

import random
import math
from libraries.logging import get_logger
from .bracket_config_loader import BracketConfig

# module logger
logger = get_logger('bracket_utils')

# Global config instance (can be replaced or reloaded as needed)
CONFIG_PATH = r'../bracket_config.xlsx'
bracket_config = None

def set_bracket_config(path):
    global bracket_config
    bracket_config = BracketConfig(path)

def ensure_config_loaded():
    global bracket_config
    if bracket_config is None:
        bracket_config = BracketConfig(CONFIG_PATH)

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
    # Generate brackets
    for key in brackets:
        brackets[key]['bracket'] = make_bracket(brackets[key]['fighters'])
    if unassigned_count:
        logger.warning(f"Total unassigned participants: {unassigned_count}")
    return dict(brackets)
