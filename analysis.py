from pathlib import Path
import csv
import math
import random
import sqlite3

# Create folders for generated data and results.
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
RESULTS_DIR = PROJECT_DIR / "results"

DATA_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# Fix the seed so the simulated data can be reproduced.
rng = random.Random(62026)
N_FAMILIES = 5000

people = []
income_records = []

for family_id in range(1, N_FAMILIES + 1):
    parent_id = 2 * family_id - 1
    child_id = 2 * family_id

    people.extend([
        (parent_id, family_id, "parent"),
        (child_id, family_id, "child"),
    ])

    # Generate persistent differences in long-run log income.
    parent_component = rng.gauss(0, 0.5)
    child_component = (
        0.4 * parent_component + rng.gauss(0, 0.4)
    )

    # Observe parents at ages 38 through 42.
    for age in range(38, 43):
        year = 1960 + age
        shock = rng.gauss(0, 0.35)
        income = math.exp(10.8 + parent_component + shock)

        income_records.append(
            (parent_id, year, age, income)
        )

    # Observe children at ages 25 through 45.
    for age in range(25, 46):
        year = 1985 + age
        loading = min(1.0, 0.55 + 0.03 * (age - 25))
        shock = rng.gauss(0, 0.35)

        log_income = (
            10.8
            + 0.025 * (age - 40)
            + loading * child_component
            + shock
        )

        income_records.append(
            (child_id, year, age, math.exp(log_income))
        )

# Save the synthetic person records.
with (DATA_DIR / "people.csv").open(
    "w", newline="", encoding="utf-8"
) as file:
    writer = csv.writer(file)
    writer.writerow(["person_id", "family_id", "role"])
    writer.writerows(people)

# Save the synthetic annual income records.
with (DATA_DIR / "income.csv").open(
    "w", newline="", encoding="utf-8"
) as file:
    writer = csv.writer(file)
    writer.writerow([
        "person_id", "year", "age", "real_income"
    ])
    writer.writerows(income_records)

print("Data source: synthetic simulation")
print(f"Families: {N_FAMILIES:,}")
print(f"People: {len(people):,}")
print(f"Annual income records: {len(income_records):,}")
print("Saved: data/people.csv")
print("Saved: data/income.csv")
# Load the saved CSV files into a temporary SQLite database.
conn = sqlite3.connect(":memory:")
conn.execute("PRAGMA foreign_keys = ON;")

conn.executescript("""
    CREATE TABLE people (
        person_id INTEGER PRIMARY KEY,
        family_id INTEGER NOT NULL,
        role TEXT NOT NULL
    );

    CREATE TABLE income (
        person_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        age INTEGER NOT NULL,
        real_income REAL NOT NULL,
        PRIMARY KEY (person_id, year),
        FOREIGN KEY (person_id) REFERENCES people(person_id)
    );
""")

with (DATA_DIR / "people.csv").open(
    newline="", encoding="utf-8"
) as file:
    reader = csv.DictReader(file)
    person_rows = [
        (
            int(row["person_id"]),
            int(row["family_id"]),
            row["role"],
        )
        for row in reader
    ]

conn.executemany(
    "INSERT INTO people VALUES (?, ?, ?);",
    person_rows
)

with (DATA_DIR / "income.csv").open(
    newline="", encoding="utf-8"
) as file:
    reader = csv.DictReader(file)
    annual_rows = [
        (
            int(row["person_id"]),
            int(row["year"]),
            int(row["age"]),
            float(row["real_income"]),
        )
        for row in reader
    ]

conn.executemany(
    "INSERT INTO income VALUES (?, ?, ?, ?);",
    annual_rows
)

conn.commit()

# Verify the number of records loaded into each table.
people_count = conn.execute(
    "SELECT COUNT(*) FROM people;"
).fetchone()[0]

income_count = conn.execute(
    "SELECT COUNT(*) FROM income;"
).fetchone()[0]

assert people_count == 10000
assert income_count == 130000

print("\nSQLite database loaded successfully.")
print(f"People in database: {people_count:,}")
print(f"Income records in database: {income_count:,}")

# Create a table containing one row per parent-child pair.
conn.execute("""
    CREATE TABLE parent_child_pairs AS
    SELECT
        p.family_id,
        p.person_id AS parent_id,
        c.person_id AS child_id
    FROM people AS p
    JOIN people AS c
        ON p.family_id = c.family_id
    WHERE p.role = 'parent'
      AND c.role = 'child';
""")

# Check that each child has exactly one matched parent.
duplicate_children = conn.execute("""
    SELECT child_id, COUNT(*) AS match_count
    FROM parent_child_pairs
    GROUP BY child_id
    HAVING COUNT(*) > 1;
""").fetchall()

pair_count = conn.execute("""
    SELECT COUNT(*)
    FROM parent_child_pairs;
""").fetchone()[0]

assert not duplicate_children, "Some children have multiple matches."
assert pair_count == N_FAMILIES, "Unexpected number of matched pairs."

# Display a small sample of the matched pairs.
sample_pairs = conn.execute("""
    SELECT family_id, parent_id, child_id
    FROM parent_child_pairs
    ORDER BY family_id
    LIMIT 5;
""").fetchall()

print(f"\nMatched parent-child pairs: {pair_count:,}")
print(f"Children with duplicate matches: {len(duplicate_children)}")
print("family_id | parent_id | child_id")

for family_id, parent_id, child_id in sample_pairs:
    print(f"{family_id} | {parent_id} | {child_id}")

# Define one reusable query for different income windows.
income_query = """
    WITH parent_income AS (
        SELECT
            person_id,
            AVG(real_income) AS parent_mean
        FROM income
        WHERE age BETWEEN :parent_start AND :parent_end
          AND real_income > 0
        GROUP BY person_id
        HAVING COUNT(*) = :parent_years
    ),
    child_income AS (
        SELECT
            person_id,
            AVG(real_income) AS child_mean
        FROM income
        WHERE age BETWEEN :child_start AND :child_end
          AND real_income > 0
        GROUP BY person_id
        HAVING COUNT(*) = :child_years
    )
    SELECT
        pairs.family_id,
        pairs.parent_id,
        pairs.child_id,
        p.parent_mean,
        c.child_mean
    FROM parent_child_pairs AS pairs
    JOIN parent_income AS p
        ON pairs.parent_id = p.person_id
    JOIN child_income AS c
        ON pairs.child_id = c.person_id
    ORDER BY pairs.family_id;
"""

# Specify the parent and child age windows.
specifications = [
    ("early_single", 40, 40, 25, 25),
    ("early_average", 38, 42, 25, 29),
    ("midcareer_single", 40, 40, 40, 40),
    ("midcareer_average", 38, 42, 38, 42),
]

matched_samples = {}

for name, parent_start, parent_end, child_start, child_end in specifications:
    parameters = {
        "parent_start": parent_start,
        "parent_end": parent_end,
        "parent_years": parent_end - parent_start + 1,
        "child_start": child_start,
        "child_end": child_end,
        "child_years": child_end - child_start + 1,
    }

    rows = conn.execute(income_query, parameters).fetchall()

    assert len(rows) == N_FAMILIES
    assert len({row[2] for row in rows}) == N_FAMILIES

    matched_samples[name] = rows

    output_path = RESULTS_DIR / f"matched_{name}.csv"

    with output_path.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.writer(file)
        writer.writerow([
            "family_id",
            "parent_id",
            "child_id",
            "parent_income",
            "child_income",
        ])
        writer.writerows(rows)

    print(f"{name}: {len(rows):,} matched pairs")

# Verify that every specification contains the same children.
reference_ids = {
    row[2] for row in matched_samples["early_single"]
}

for rows in matched_samples.values():
    assert {row[2] for row in rows} == reference_ids

print("All four specifications use the same children.")

# Estimate an OLS regression with an intercept.
def estimate_ige(rows):
    parent_logs = [math.log(row[3]) for row in rows]
    child_logs = [math.log(row[4]) for row in rows]

    n = len(rows)
    parent_mean = sum(parent_logs) / n
    child_mean = sum(child_logs) / n

    sxx = sum(
        (x - parent_mean) ** 2
        for x in parent_logs
    )

    sxy = sum(
        (x - parent_mean) * (y - child_mean)
        for x, y in zip(parent_logs, child_logs)
    )

    beta = sxy / sxx
    alpha = child_mean - beta * parent_mean

    # Calculate the HC1 heteroskedasticity-robust standard error.
    residuals = [
        y - alpha - beta * x
        for x, y in zip(parent_logs, child_logs)
    ]

    meat = sum(
        (x - parent_mean) ** 2 * residual ** 2
        for x, residual in zip(parent_logs, residuals)
    )

    robust_se = math.sqrt(
        (n / (n - 2)) * meat / (sxx ** 2)
    )

    return n, beta, robust_se


# Estimate and save the results for all four specifications.
estimates = []

print("\nIGE estimates:")
print("specification | pairs | IGE | robust SE")

for name, rows in matched_samples.items():
    n, beta, robust_se = estimate_ige(rows)

    estimates.append((
        name,
        n,
        beta,
        robust_se,
        beta - 1.96 * robust_se,
        beta + 1.96 * robust_se,
    ))

    print(f"{name} | {n:,} | {beta:.3f} | {robust_se:.3f}")

with (RESULTS_DIR / "ige_estimates.csv").open(
    "w", newline="", encoding="utf-8"
) as file:
    writer = csv.writer(file)
    writer.writerow([
        "specification",
        "pairs",
        "ige",
        "robust_se",
        "ci_low",
        "ci_high",
    ])
    writer.writerows(estimates)

print("Saved: results/ige_estimates.csv")

import matplotlib.pyplot as plt

# Prepare estimates and 95% confidence intervals.
labels = [
    "Early career\nSingle year",
    "Early career\nFive-year average",
    "Midcareer\nSingle year",
    "Midcareer\nFive-year average",
]

betas = [row[2] for row in estimates]
margins = [1.96 * row[3] for row in estimates]
positions = list(range(len(labels)))

fig, ax = plt.subplots(figsize=(9, 5.5))

ax.errorbar(
    positions,
    betas,
    yerr=margins,
    fmt="o",
    color="#167D9A",
    markersize=8,
    capsize=6,
    linewidth=2,
    label="Estimated IGE with 95% CI",
)

ax.axhline(
    0.40,
    color="#B45309",
    linestyle="--",
    linewidth=1.5,
    label="Population long-run parameter: 0.40",
)

for position, beta, margin in zip(positions, betas, margins):
    ax.text(
        position,
        beta + margin + 0.015,
        f"{beta:.3f}",
        ha="center",
        fontsize=11,
    )

ax.set_xticks(positions)
ax.set_xticklabels(labels)
ax.set_ylabel("Intergenerational income elasticity (IGE)")
ax.set_title("Income Timing and the Estimated IGE")
ax.set_ylim(0, 0.52)
ax.set_xlim(-0.5, 3.5)
ax.grid(axis="y", alpha=0.25)
ax.set_axisbelow(True)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.legend(loc="upper left", frameon=False, fontsize=9)

fig.text(
    0.5,
    0.02,
    "Source: synthetic simulation; 5,000 identical pairs in each specification. "
    "Intervals use HC1 robust standard errors.",
    ha="center",
    fontsize=8,
)

fig.tight_layout(rect=(0, 0.07, 1, 1))

fig.savefig(
    RESULTS_DIR / "ige_comparison.png",
    dpi=300,
    bbox_inches="tight",
)
plt.close(fig)

print("Saved: results/ige_comparison.png")