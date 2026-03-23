EXPORT DATA OPTIONS (
  uri='gs://stackoverflow-data-lake-famous-gearing/raw/questions/questions_*.parquet',
  format='PARQUET',
  overwrite=true
)
AS
SELECT *
FROM `famous-gearing-490518-b7.stackoverflow_pipeline.raw_questions`;
