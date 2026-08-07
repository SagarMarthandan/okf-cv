---
title: Advanced Database Techniques
description: Reference library of SQL patterns covering window functions, CTEs, complex joins, query optimization, and schema design across MySQL and PostgreSQL.
technologies: SQL, MySQL, PostgreSQL
keywords:
  - sql
  - window functions
  - ctes
  - joins
  - query optimization
  - database concepts
  - relational databases
  - data analysis
  - schema design
  - aggregate functions
  - views
  - constraints
archetypes:
  - Data Analyst
transferable_skills:
  - sql
  - window functions
  - data modeling
  - query optimization
  - database design
  - data analysis
repo_url: https://github.com/SagarMarthandan/SQL-Practice
---

# SQL Query Library

A structured reference library of SQL patterns and techniques, organized from foundational queries to advanced analytical functions. Each section demonstrates a specific SQL competency through working examples on real schema designs.

## Competency Areas

### Window Functions & Analytics
`OVER()`, `PARTITION BY`, `RANK()`, `DENSE_RANK()`, `LEAD()`, `LAG()`, and running aggregates for time-series and comparative analysis.

### Complex Joins & Relationships
Inner, left, right, and full outer joins across one-to-many and many-to-many relationships. Foreign key design and join table patterns for normalized schemas.

### CTEs & Query Composition
Common table expressions for multi-step transformations, recursive CTEs for hierarchical data, and subquery patterns for complex filtering.

### Query Optimization
Execution plan analysis, index strategies, `EXPLAIN` output interpretation, and patterns for avoiding full-table scans on large datasets.

### Schema Design & Constraints
Primary and foreign keys, `UNIQUE` and `CHECK` constraints, `ALTER TABLE` modifications, and view creation for reusable query logic.

### Aggregate Functions & Grouping
`COUNT`, `SUM`, `AVG`, `MIN`, `MAX` with `GROUP BY`, `HAVING` clauses, and `WITH ROLLUP` for multi-level aggregation reporting.

## Databases

Patterns are tested across both **MySQL** and **PostgreSQL**, covering syntax differences in data types, string functions, and window function support.
