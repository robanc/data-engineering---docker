{{ config(materialized='table') }}

select
    month,
    tag,
    question_count
from {{ ref('fct_questions_by_tag_month') }}
where tag in ('python', 'java', 'javascript', 'sql', 'pandas')
order by month
