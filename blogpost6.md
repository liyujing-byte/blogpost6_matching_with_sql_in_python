---
title: "My Sixth Blog Post"
subtitle: "Matching Generations: How Income Timing Changes the Estimated IGE"
date: "2026-10-21"
categories: [data science, SQL, intergenerational mobility]
---

How strongly is children's income associated with their parents'
income, and does the answer depend on when income is measured?
I use SQL within Python to match parents and children in a synthetic
longitudinal dataset. The results illustrate how early-career income
and temporary earnings fluctuations can make intergenerational
persistence appear weaker.

## Data and approach

I generate 5,000 synthetic families, each containing one designated
parent and one child. The `people` table records permanent person IDs,
origin-family IDs, and roles. The `income` table contains annual
individual earnings, calendar years, and ages. Parents are observed
at ages 38–42, while children are observed at ages 25–45. Income is
expressed in constant hypothetical dollars.

The data are simulated rather than drawn from actual families.
The random seed is 62026, and the population elasticity between
latent long-run incomes is set to 0.40. Annual earnings include
temporary shocks. Children's early earnings reflect long-run
differences less strongly than their midcareer earnings.
These assumptions create an illustration, not an estimate of
mobility in any country.

Python's built-in `sqlite3` module loads the CSV files into an
in-memory database. The complete script generates the data,
executes the SQL queries, and saves the estimates and figure.

## Matching parents and children with SQL

I first match the two generations using their origin-family IDs:

```sql
SELECT
    p.family_id,
    p.person_id AS parent_id,
    c.person_id AS child_id
FROM people AS p
JOIN people AS c
    ON p.family_id = c.family_id
WHERE p.role = 'parent'
  AND c.role = 'child';
```

`SELECT` chooses the output columns. `JOIN` connects records with
matching family IDs. The aliases `p` and `c` allow the same table
to represent both generations, while `WHERE` selects their roles.
The resulting table contains 5,000 pairs, with no duplicate
child matches.

This match is valid because each simulated family has explicitly
assigned relationships. In real longitudinal data, sharing a
household ID alone would not establish parenthood. Researchers
need verified relationship codes or parent pointers, along with
stable identifiers that remain useful after children move out.

## From annual records to income measures

For a five-year measure, I group annual records by person:

```sql
SELECT
    person_id,
    AVG(real_income) AS mean_income
FROM income
WHERE age BETWEEN 38 AND 42
  AND real_income > 0
GROUP BY person_id
HAVING COUNT(*) = 5;
```

`WHERE` filters individual observations before aggregation.
`GROUP BY` collects each person's records, and `AVG` calculates
their arithmetic mean income. `HAVING` retains only people with
five valid years. For single-year measures, I select one age and
require one observation.

The full query uses common table expressions to summarize parental
and child income separately, then joins these summaries to the
matched pairs using person IDs. Aggregating first avoids multiplying
parent-year and child-year records in a many-to-many join.
Every specification contains the same 5,000 families.

## Income timing changes the estimated association

I estimate an OLS regression of log child income on log parental
income, including an intercept. The slope is the intergenerational
income elasticity, or IGE. For multi-year measures, income is
averaged in levels before taking logarithms.

| Income measurement | Parent ages | Child ages | IGE | Robust SE |
|---|---|---|---:|---:|
| Early career, single year | 40 | 25 | 0.162 | 0.010 |
| Early career, five-year average | 38–42 | 25–29 | 0.241 | 0.008 |
| Midcareer, single year | 40 | 40 | 0.304 | 0.012 |
| Midcareer, five-year average | 38–42 | 38–42 | 0.390 | 0.011 |

![Estimated IGEs for the same 5,000 synthetic parent–child pairs.
Error bars show approximate 95 percent confidence intervals using
HC1 robust standard errors.](results/ige_comparison.png)

Holding parental single-year income fixed, measuring children at
age 25 produces an IGE of 0.162, compared with 0.304 at age 40.
This illustrates life-cycle bias: early earnings provide a less
representative measure of long-run economic position under the
simulation's assumptions.

The midcareer five-year estimate is 0.390, close to the imposed
long-run parameter of 0.40. An IGE of 0.390 means that 10 percent
higher parental income is associated with approximately 3.9 percent
higher child income. This is a descriptive association, not a
causal effect.

## What averaging can and cannot solve

Averaging smooths temporary earnings fluctuations. Temporary noise
in parental income can attenuate the regression slope, so using
several years can improve the measurement of persistent income.

However, the early-career average still yields only 0.241.
Repeated observations at young ages can retain systematic
life-cycle distortion. That comparison also changes children's
measurement ages from 25 to 25–29, so the increase cannot be
attributed to averaging alone.

All simulated incomes are positive and complete. Real applications
must address inflation, missing observations, nonpositive earnings,
and relationship verification. Confidence intervals describe
sampling uncertainty within the simulation; they do not validate
its assumptions.

The main takeaway is that matching generations requires attention
to both identifiers and income measurement. Several years of
income near representative career ages can better capture
long-run economic status, while averaging alone cannot guarantee
that life-cycle bias disappears.

[Code, data, and replication instructions](https://github.com/liyujing-byte/blogpost6_matching_with_sql_in_python)