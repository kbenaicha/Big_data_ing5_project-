import os
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path

import boto3
import pandas as pd

BUCKET = "user-k-benaicha-ece"
PREFIX = "bigdata_project/processed/"
CENT = Decimal("0.01")

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


def read_csv(name):
    response = s3.get_object(Bucket=BUCKET, Key=PREFIX + name)
    with response["Body"] as stream:
        return pd.read_csv(
            BytesIO(stream.read()),
            dtype=str,
            keep_default_na=False,
        )


orders = read_csv("orders_clean.csv")
sql_results = read_csv("sales_by_category.csv")

if sql_results["category"].duplicated().any():
    raise ValueError("Catégories dupliquées dans le résultat SQL.")

if set(orders["category"]) != set(sql_results["category"]):
    raise ValueError("Les catégories des deux fichiers ne correspondent pas.")

sql_results = sql_results.set_index("category")
checks = []

for category, group in orders.groupby("category"):
    statuses = group["status"]

    delivered = int(statuses.eq("delivered").sum())
    returned = int(statuses.eq("returned").sum())
    cancelled = int(statuses.eq("cancelled").sum())

    # Recalcul indépendant des montants en arithmétique décimale.
    revenue = Decimal("0.00")

    for row in group.itertuples(index=False):
        if row.status == "delivered":
            amount = (
                Decimal(row.quantity)
                * Decimal(row.unit_price)
                * (Decimal("1") - Decimal(row.discount_rate))
            )
            revenue += amount.quantize(CENT, rounding=ROUND_HALF_UP)

    denominator = delivered + returned
    return_rate = (
        (Decimal(returned) * 100 / Decimal(denominator)).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        if denominator
        else None
    )

    expected = {
        "total_lignes": Decimal(len(group)),
        "lignes_livrees": Decimal(delivered),
        "lignes_retournees": Decimal(returned),
        "lignes_annulees": Decimal(cancelled),
        "ca_net": revenue,
        "taux_retour_pct": return_rate,
    }

    for metric, python_value in expected.items():
        text = sql_results.loc[category, metric]
        sql_value = Decimal(text) if text else None

        checks.append({
            "category": category,
            "indicateur": metric,
            "valeur_python": python_value,
            "valeur_sql": sql_value,
            "conforme": python_value == sql_value,
        })

    print(
        f"{category} : CA recalculé = {revenue} ; "
        f"taux de retour = {return_rate} %"
    )

report = pd.DataFrame(checks)

s3.put_object(
    Bucket=BUCKET,
    Key=PREFIX + "validation_report.csv",
    Body=report.to_csv(index=False).encode("utf-8"),
)

failures = report.loc[~report["conforme"]]

print(f"\nContrôles réalisés : {len(report)}")
print(f"Contrôles conformes : {int(report['conforme'].sum())}")
print(f"Écarts détectés : {len(failures)}")
print(f"Rapport : s3://{BUCKET}/{PREFIX}validation_report.csv")

if not failures.empty:
    print(failures.to_string(index=False))
    raise RuntimeError("Des écarts existent entre Python et SQL.")

print("Vérification indépendante réussie.")