---
title: SQL Practice and Revision
description: Collection of SQL scripts covering CRUD basics, joins, window functions, views, and constraints for database concept practice.
technologies: SQL, MySQL, PostgreSQL
keywords:
- sql
- window functions
- ctes
- joins
- aggregate functions
- query optimization
- database concepts
- views
- constraints
- crud operations
- data
- overview
- analytical
- creating
- initial
archetypes:
- Data Analyst
repo_url: https://github.com/SagarMarthandan
---

# SQL Practice and Revision

This repository contains a collection of SQL scripts used for practicing and revising various database concepts, from basic CRUD operations to advanced window functions and views.

## Files Overview

### 1. Fundamentals & CRUD Basics

- **[1-5. practice.sql](1-5. practice.sql)**: Basic table creation (`CREATE`), data insertion (`INSERT`), and schema inspection (`DESC`).
- **[5. CRUD_Basics.sql](5. CRUD_Basics.sql)**: Core CRUD operations (`SELECT`, `UPDATE`, `DELETE`) using a `cats` dataset.
- **[6. CRUD_challenge.sql](6. CRUD_challenge.sql)**: Practice exercises for reinforcing CRUD concepts.
- **[10. data_types.sql](10. data_types.sql)**: Exploring various MySQL data types including `DECIMAL`, `DATE`, `TIME`, `DATETIME`, and `TIMESTAMP`.

### 2. String & Aggregate Functions

- **[7. string_functions.sql](7. string_functions.sql)**: Comprehensive guide to string manipulation (`CONCAT`, `SUBSTRING`, `REPLACE`, `CHAR_LENGTH`, etc.).
- **[9. aggregate_functions.sql](9. aggregate_functions.sql)**: Working with group functions like `COUNT`, `MIN`, `MAX`, `SUM`, and `AVG` along with `GROUP BY`.

### 3. Selection & Filtering

- **[8. Refining_selections.sql](8. Refining_selections.sql)**: Refining data retrieval using `DISTINCT`, `ORDER BY`, `LIMIT`, and `LIKE` pattern matching.
- **[11. logival_operators.sql](11. logival_operators.sql)**: Practice with logical operators (`AND`, `OR`, `NOT`, `BETWEEN`, `IN`) and `CASE` statements.

### 4. Database Schema & Constraints

- **[book_data.sql](book_data.sql)**: Setup script for the `books` table used in various exercises.
- **[12. constraints_ALTER_table.sql](12. constraints_ALTER_table.sql)**: Working with constraints (`UNIQUE`, `CHECK`) and modifying existing tables using `ALTER TABLE`.

### 5. Joins & Relationships (One-to-Many & Many-to-Many)

- **[13. one_to_many_joins.sql](13. one_to_many_joins.sql)**: Understanding primary and foreign keys, along with `INNER`, `LEFT`, and `RIGHT JOIN`s.
- **[14. many_to_many_joins.sql](14. many_to_many_joins.sql)**: Implementing complex relationships using join tables (e.g., reviewers and series).

### 6. Advanced SQL Concepts

- **[15. views_models_more.sql](15. views_models_more.sql)**: Creating `VIEWS`, using `HAVING` clauses, and the `WITH ROLLUP` modifier.
- **[16. Window_functions.sql](16. Window_functions.sql)**: Advanced analytical queries using `OVER()`, `PARTITION BY`, `RANK()`, `LEAD()`, and `LAG()`.

## How to Use

1.  **Setup**: Run initial data scripts like `book_data.sql` to populate the environment.
2.  **Learn**: Follow the numbered scripts sequentially to move from basics to advanced topics.
3.  **Practice**: Modify the queries in the scripts to test your understanding of different functions and operations.

---

_Happy Querying!_




------------------------------------------------------------------------------