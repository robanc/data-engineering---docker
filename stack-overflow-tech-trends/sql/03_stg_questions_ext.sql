CREATE OR REPLACE EXTERNAL TABLE
`famous-gearing-490518-b7.stackoverflow_pipeline.stg_questions_ext`
OPTIONS (
  format = 'PARQUET',
  uris = ['gs://stackoverflow-data-lake-famous-gearing/raw/questions/questions_*.parquet']
);
