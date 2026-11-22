from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

import pandas as pd

from read_s3 import BUCKET, df, s3

PREFIX = "bigdata_project/processed/"
CENT = Decimal("0.01")

# read_s3 fournit les données brutes et affiche date et namespace.
raw = df.copy()

response = s3.get_object(
    Bucket=BUCKET,
    Key=PREFIX + "orders_clean.csv",
)
with response["Body"] as stream:
    clean = pd.read_csv(
        BytesIO(stream.read()),
        dtype=str,
        keep_default_na=False,
    )


def indicators(data):
    revenue = Decimal("0.00")

    for row in data.itertuples(index=False):
        if row.status == "delivered":
            amount = (
                Decimal(str(row.quantity))
                * Decimal(str(row.unit_price))
                * (
                    Decimal("1")
                    - Decimal(str(row.discount_rate))
                )
            )
            revenue += amount.quantize(CENT, rounding=ROUND_HALF_UP)

    delivered = int(data["status"].eq("delivered").sum())
    returned = int(data["status"].eq("returned").sum())
    denominator = delivered + returned

    rate = (
        (Decimal(returned) * 100 / Decimal(denominator)).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        if denominator
        else None
    )

    return {
        "nombre_lignes": Decimal(len(data)),
        "ca_net": revenue,
        "taux_retour_pct": rate,
    }


before = indicators(raw)
after = indicators(clean)

comparison = pd.DataFrame([
    {
        "indicateur": name,
        "avant": before[name],
        "apres": after[name],
        "ecart_apres_moins_avant": (
            after[name] - before[name]
            if after[name] is not None and before[name] is not None
            else None
        ),
    }
    for name in before
])

s3.put_object(
    Bucket=BUCKET,
    Key=PREFIX + "cleaning_impact.csv",
    Body=comparison.to_csv(index=False).encode("utf-8"),
)

print("\nEFFET DU NETTOYAGE")
print(comparison.to_string(index=False))
print("\nPour le taux de retour, l'écart est en points de pourcentage.")
print("Avant : calcul naïf incluant doublons et valeurs invalides.")
print("Après : mêmes formules appliquées aux données nettoyées.")
print("Comparaison globale, sans regroupement par date.")
print("Export S3 : " + PREFIX + "cleaning_impact.csv")