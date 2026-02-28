import duckdb

con = duckdb.connect("taxi_pipeline.duckdb")

result = con.execute("""
    SELECT 
        SUM(tip_amt) AS total_tips
    FROM nyc_taxi.yellow_tripdata
""").fetchall()

print(result)