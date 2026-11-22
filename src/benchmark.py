import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from statistics import median
from time import perf_counter

import boto3
import duckdb
import pandas as pd

BUCKET = "user-k-benaicha-ece"
PREFIX = "bigdata_project/processed/"
REPETITIONS = 7

print("Date UTC :", datetime.now(timezone.utc).isoformat())

namespace = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
if namespace.exists():
    print("Namespace :", namespace.read_text().strip())

endpoint = (
    os.getenv("AWS_ENDPOINT_URL_S3")
    or os.getenv("AWS_ENDPOINT_URL")
    or os.getenv("AWS_S3_ENDPOINT")
    or os.getenv("S3_ENDPOINT")
)

if not endpoint:
    raise RuntimeError("Adresse S3 absente de l'environnement.")

if not endpoint.startswith(("https://", "http://")):
    endpoint = "https://" + endpoint

s3 = boto3.client("s3", endpoint_url=endpoint)

# Télécharger avant la mesure pour exclure les variations du réseau.
files = {}

for format_name in ["csv", "parquet"]:
    response = s3.get_object(
        Bucket=BUCKET,
        Key=PREFIX + "orders_clean." + format_name,
    )
    with response["Body"] as stream:
        files[format_name] = stream.read()

con = duckdb.connect()
con.execute("SET threads = 1")

query = """
    SELECT category, COUNT(*) AS lignes, SUM(quantity) AS quantite
    FROM benchmark_orders
    GROUP BY category
    ORDER BY category
"""


def measure(format_name):
    start = perf_counter()

    buffer = BytesIO(files[format_name])

    if format_name == "csv":
        data = pd.read_csv(buffer, parse_dates=["order_date"])
    else:
        data = pd.read_parquet(buffer)

    con.register("benchmark_orders", data)
    result = con.execute(query).fetchall()

    elapsed_ms = (perf_counter() - start) * 1000
    con.unregister("benchmark_orders")

    return elapsed_ms, result


# Un passage d'échauffement par format, exclu des mesures.
_, reference = measure("csv")
_, parquet_result = measure("parquet")

if reference != parquet_result:
    raise RuntimeError("Les deux formats ne donnent pas les mêmes résultats.")

runs = []

# Alterner l'ordre pour limiter l'effet de l'ordre d'exécution.
for repetition in range(1, REPETITIONS + 1):
    formats = ["csv", "parquet"] if repetition % 2 else ["parquet", "csv"]

    for format_name in formats:
        elapsed_ms, result = measure(format_name)

        if result != reference:
            raise RuntimeError("Résultat incohérent pendant les mesures.")

        runs.append({
            "repetition": repetition,
            "format": format_name,
            "temps_ms": elapsed_ms,
        })

runs_df = pd.DataFrame(runs)

summary = pd.DataFrame([
    {
        "format": format_name,
        "taille_octets": len(files[format_name]),
        "repetitions": REPETITIONS,
        "temps_median_ms": median(
            row["temps_ms"]
            for row in runs
            if row["format"] == format_name
        ),
    }
    for format_name in ["csv", "parquet"]
])

for name, result in [
    ("benchmark_runs.csv", runs_df),
    ("benchmark_results.csv", summary),
]:
    s3.put_object(
        Bucket=BUCKET,
        Key=PREFIX + name,
        Body=result.to_csv(index=False).encode("utf-8"),
    )

print("\nCOMPARAISON CSV / PARQUET")
print(summary.to_string(index=False))
print("\nRésultats des agrégations identiques.")
print("Mesure : lecture en mémoire + agrégation SQL.")
print("Téléchargement S3 exclu. Un thread DuckDB.")
print("Sept mesures par format après échauffement.")
print("Mesures détaillées et synthèse enregistrées sur S3.")

con.close()