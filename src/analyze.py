import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import boto3
import duckdb
import pandas as pd

BUCKET = "user-k-benaicha-ece"
PREFIX = "bigdata_project/processed/"
KEY = PREFIX + "orders_clean.parquet"

print("Date UTC :", datetime.now(timezone.utc).isoformat())

namespace = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
if namespace.exists():
    print("Namespace :", namespace.read_text().strip())

# Connexion avec les identifiants du terminal.
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

# Lecture du fichier nettoyé depuis S3.
response = s3.get_object(Bucket=BUCKET, Key=KEY)
with response["Body"] as stream:
    orders = pd.read_parquet(BytesIO(stream.read()))

print(f"Source : s3://{BUCKET}/{KEY}")
print(f"Lignes analysées : {len(orders):,}")

con = duckdb.connect()
con.register("orders", orders)

# Montant après remise, arrondi au centime pour chaque ligne.
con.execute("""
    CREATE VIEW sales AS
    SELECT *,
        CAST(
            ROUND(
                quantity
                * CAST(unit_price AS DECIMAL(12, 2))
                * (
                    CAST(1 AS DECIMAL(4, 2))
                    - CAST(discount_rate AS DECIMAL(4, 2))
                ),
                2
            ) AS DECIMAL(18, 2)
        ) AS line_amount
    FROM orders
""")

# Même définition des indicateurs pour les deux regroupements.
indicators = """
    COUNT(*) AS total_lignes,
    SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END)
        AS lignes_livrees,
    SUM(CASE WHEN status = 'returned' THEN 1 ELSE 0 END)
        AS lignes_retournees,
    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END)
        AS lignes_annulees,
    SUM(CASE WHEN status = 'delivered' THEN line_amount ELSE 0 END)
        AS ca_net,
    ROUND(
        100.0
        * SUM(CASE WHEN status = 'returned' THEN 1 ELSE 0 END)
        / NULLIF(
            SUM(CASE
                WHEN status IN ('delivered', 'returned') THEN 1
                ELSE 0
            END),
            0
        ),
        2
    ) AS taux_retour_pct
"""

by_category = con.execute(f"""
    SELECT category, {indicators}
    FROM sales
    GROUP BY category
    ORDER BY ca_net DESC, category
""").df()

by_month = con.execute(f"""
    SELECT strftime(order_date, '%Y-%m') AS mois, {indicators}
    FROM sales
    GROUP BY mois
    ORDER BY mois
""").df()

# Enregistrement des deux résultats sur S3.
for name, result in [
    ("sales_by_category.csv", by_category),
    ("sales_by_month.csv", by_month),
]:
    s3.put_object(
        Bucket=BUCKET,
        Key=PREFIX + name,
        Body=result.to_csv(index=False, float_format="%.2f").encode("utf-8"),
    )
    print("Export :", PREFIX + name)

print("\nRESULTATS PAR CATEGORIE")
print(by_category.to_string(index=False))

print("\nRESULTATS PAR MOIS")
print(by_month.to_string(index=False))

con.close()
print("\nAnalyse SQL et exports S3 réussis.")