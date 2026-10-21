import sqlite3

conn = sqlite3.connect(":memory:")

result = conn.execute("SELECT 1 + 1;").fetchone()

print("SQL result:", result[0])

conn.close()

import sqlite3

conn = sqlite3.connect(":memory:")

# Create the people table.
conn.execute("""
    CREATE TABLE people (
        person_id INTEGER PRIMARY KEY,
        family_id INTEGER,
        role TEXT
    );
""")

# Each row contains a person ID, origin-family ID, and role.
people = [
    (1, 100, "parent"),
    (2, 100, "child"),
    (3, 200, "parent"),
    (4, 200, "child"),
]

# Insert the sample records.
conn.executemany(
    "INSERT INTO people VALUES (?, ?, ?);",
    people
)

# Retrieve all people, ordered by person ID.
rows = conn.execute("""
    SELECT person_id, family_id, role
    FROM people
    ORDER BY person_id;
""").fetchall()

for row in rows:
    print(row)

# Match parents and children using their origin-family IDs.
pairs = conn.execute("""
    SELECT
        p.family_id,
        p.person_id AS parent_id,
        c.person_id AS child_id
    FROM people AS p
    JOIN people AS c
        ON p.family_id = c.family_id
    WHERE p.role = 'parent'
      AND c.role = 'child'
    ORDER BY p.family_id;
""").fetchall()

print("\nParent-child matches:")
print("family_id | parent_id | child_id")

for family_id, parent_id, child_id in pairs:
    print(f"{family_id} | {parent_id} | {child_id}")

# Create a table with one row per person and year.
conn.execute("""
    CREATE TABLE income (
        person_id INTEGER,
        year INTEGER,
        age INTEGER,
        real_income REAL,
        PRIMARY KEY (person_id, year),
        FOREIGN KEY (person_id) REFERENCES people(person_id)
    );
""")

# Income values are synthetic and expressed in constant dollars.
income_records = [
    (1, 2000, 40, 40000),
    (1, 2001, 41, 42000),
    (1, 2002, 42, 38000),
    (2, 2025, 40, 50000),
    (2, 2026, 41, 54000),
    (2, 2027, 42, 46000),
    (3, 2000, 40, 80000),
    (3, 2001, 41, 84000),
    (3, 2002, 42, 76000),
    (4, 2025, 40, 70000),
    (4, 2026, 41, 75000),
    (4, 2027, 42, 65000),
]

conn.executemany(
    "INSERT INTO income VALUES (?, ?, ?, ?);",
    income_records
)

# Display each person's annual income records.
income_rows = conn.execute("""
    SELECT person_id, year, age, real_income
    FROM income
    ORDER BY person_id, year;
""").fetchall()

print("\nAnnual income records:")
print("person_id | year | age | real_income")

for person_id, year, age, real_income in income_rows:
    print(f"{person_id} | {year} | {age} | {real_income:.0f}")

# Calculate three-year average income for each person.
average_rows = conn.execute("""
    SELECT
        person_id,
        COUNT(*) AS years_observed,
        AVG(real_income) AS average_income
    FROM income
    WHERE age BETWEEN 40 AND 42
      AND real_income > 0
    GROUP BY person_id
    HAVING COUNT(*) = 3
    ORDER BY person_id;
""").fetchall()

print("\nThree-year average income:")
print("person_id | years_observed | average_income")

for person_id, years_observed, average_income in average_rows:
    print(f"{person_id} | {years_observed} | {average_income:.2f}")

# Average income first, then match parents and children.
matched_rows = conn.execute("""
    WITH average_income AS (
        SELECT
            person_id,
            AVG(real_income) AS mean_income
        FROM income
        WHERE age BETWEEN 40 AND 42
          AND real_income > 0
        GROUP BY person_id
        HAVING COUNT(*) = 3
    )
    SELECT
        p.family_id,
        p.person_id AS parent_id,
        c.person_id AS child_id,
        pi.mean_income AS parent_income,
        ci.mean_income AS child_income
    FROM people AS p
    JOIN people AS c
        ON p.family_id = c.family_id
    JOIN average_income AS pi
        ON p.person_id = pi.person_id
    JOIN average_income AS ci
        ON c.person_id = ci.person_id
    WHERE p.role = 'parent'
      AND c.role = 'child'
    ORDER BY p.family_id;
""").fetchall()

print("\nMatched average incomes:")
print("family_id | parent_id | child_id | parent_income | child_income")

for family_id, parent_id, child_id, parent_income, child_income in matched_rows:
    print(
        f"{family_id} | {parent_id} | {child_id} | "
        f"{parent_income:.2f} | {child_income:.2f}"
    )

conn.close()