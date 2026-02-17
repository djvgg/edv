# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Database configuration for PostgreSQL connection.
TODO: Move credentials to environment variables for production.
"""

DB_CONFIG = {
    'host': '172.17.192.42',
    'port': 5432,
    'database': 'mydatabase',
    'user': 'myuser',
    'password': 'mypassword'
}
