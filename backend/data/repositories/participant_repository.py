# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Repository for fetching participant data from PostgreSQL database.
"""

import psycopg2
from datetime import date
from typing import List, Dict
from ..db_config import DB_CONFIG


def calculate_age(birth_date: date) -> int:
    """Calculate age from birth date."""
    today = date.today()
    age = today.year - birth_date.year
    if today.month < birth_date.month or (today.month == birth_date.month and today.day < birth_date.day):
        age -= 1
    return age


def fetch_participants_from_db() -> List[Dict]:
    """
    Fetch all valid and paid participants from the database.

    Returns:
        List of participant dictionaries with keys: Name, Gender, Age, Weight, Verein
    """
    participants = []

    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Query to fetch all members (ignoring valid/paid for now)
        query = """
            SELECT
                first_name,
                last_name,
                birth_date,
                club,
                gender,
                weight
            FROM public.members
            ORDER BY last_name, first_name
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        for row in rows:
            first_name, last_name, birth_date, club, gender, weight = row

            # Build participant dict matching the format expected by bracket generator
            participant = {
                'Name': f"{first_name} {last_name}".strip(),
                'Gender': gender.upper().strip() if gender else '',  # 'M' or 'W'
                'Age': calculate_age(birth_date) if birth_date else None,
                'Weight': float(weight) if weight else None,
                'Verein': club if club else ''
            }
            participants.append(participant)

        cursor.close()
        conn.close()

        print(f"[INFO] Loaded {len(participants)} participants from database")
        return participants

    except Exception as e:
        print(f"[ERROR] Database error: {e}")
        raise


def test_connection() -> bool:
    """Test database connection."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] Connection test failed: {e}")
        return False
