
## sql/01_raw_questions.sql

```sql
CREATE OR REPLACE TABLE
`famous-gearing-490518-b7.stackoverflow_pipeline.raw_questions`
AS
SELECT
  id,
  creation_date,
  score,
  view_count,
  answer_count,
  tags
FROM `bigquery-public-data.stackoverflow.posts_questions`
WHERE creation_date >= '2015-01-01'
  AND creation_date < '2025-01-01';
