-- SPDX-FileCopyrightText: 2026 TOP Team Combat Control
-- SPDX-License-Identifier: GPL-3.0-or-later

CREATE TABLE members (
    id SERIAL PRIMARY KEY,
    last_name VARCHAR(50) NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    birth_date DATE NOT NULL,
    club VARCHAR(100) NOT NULL,
    gender CHAR(1) CHECK (gender IN ('m','w')),
    weight NUMERIC(5,2),        -- kg, up to 999.99
    valid BOOLEAN DEFAULT FALSE, -- is membership valid
    paid BOOLEAN DEFAULT FALSE   -- has membership fee been paid
);
