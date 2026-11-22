from io import BytesIO

import pandas as pd

from read_s3 import BUCKET, df, s3

PREFIX = "bigdata_project/processed/"
raw = df.copy()

# 1 Identifier les doublons.
duplicates = raw.duplicated(subset=["order_line_id"], keep="first")
rejected_duplicates = raw.loc[duplicates].copy()
rejected_duplicates["rejection_reason"] = "doublon"

data = raw.loc[~duplicates].copy()

# 2 Convertir les valeurs pour contrôler leur validité.
dates = pd.to_datetime(
    data["order_date"], format="%Y-%m-%d", errors="coerce"
)
quantity = pd.to_numeric(data["quantity"], errors="coerce")
price = pd.to_numeric(data["unit_price"], errors="coerce")
discount = pd.to_numeric(data["discount_rate"], errors="coerce")

# Une date invalide devient NaT et peut ainsi être identifiée.
checks = {
    "date_invalide": dates.isna(),
    "quantite_invalide": (
        quantity.isna() | (quantity <= 0) | (quantity % 1 != 0)
    ),
    "prix_invalide": price.isna() | (price < 0),
    "remise_invalide": ~discount.between(0, 1),
    "statut_invalide": ~data["status"].isin(
        ["delivered", "returned", "cancelled"]
    ),
}

# Conserver tous les motifs lorsqu'une ligne cumule des erreurs.
reasons = pd.Series("", index=data.index, dtype="string")

for reason, mask in checks.items():
    reasons.loc[mask] = reasons.loc[mask] + reason + ";"

invalid = reasons.ne("")

# Conserver les valeurs originales dans les rejets.
rejected_invalid = data.loc[invalid].copy()
rejected_invalid["rejection_reason"] = reasons.loc[invalid].str.rstrip(";")

rejected = pd.concat(
    [rejected_duplicates, rejected_invalid], ignore_index=True
)

# 3 Construire le fichier nettoyé avec les types adaptés.
clean = data.loc[~invalid].copy()
clean["order_date"] = dates.loc[clean.index]
clean["quantity"] = quantity.loc[clean.index].astype("int64")
clean["unit_price"] = price.loc[clean.index]
clean["discount_rate"] = discount.loc[clean.index]

missing_category = (
    clean["category"].fillna("").astype(str).str.strip().eq("")
)
clean.loc[missing_category, "category"] = "Inconnue"

# 4 Produire le bilan qualité.
metrics = {
    "lignes_brutes": len(raw),
    "doublons_supprimes": int(duplicates.sum()),
    **{
        reason: int(mask.sum())
        for reason, mask in checks.items()
    },
    "categories_completees": int(missing_category.sum()),
    "total_lignes_rejetees": len(rejected),
    "lignes_nettoyees": len(clean),
}

quality = pd.DataFrame(
    metrics.items(), columns=["controle", "nombre"]
)

# Vérifier que chaque ligne brute est conservée ou rejetée.
assert len(raw) == len(clean) + len(rejected)
assert clean["order_line_id"].is_unique

# 5 Préparer les exports avant de les envoyer sur S3.
parquet = BytesIO()
clean.to_parquet(parquet, index=False, engine="pyarrow")

outputs = {
    "orders_clean.parquet": parquet.getvalue(),
    "orders_clean.csv": clean.to_csv(index=False).encode("utf-8"),
    "orders_rejected.csv": rejected.to_csv(index=False).encode("utf-8"),
    "quality_report.csv": quality.to_csv(index=False).encode("utf-8"),
}

for name, content in outputs.items():
    s3.put_object(Bucket=BUCKET, Key=PREFIX + name, Body=content)

print("\nBILAN DU NETTOYAGE")
print(quality.to_string(index=False))

print("\nExemples de lignes rejetées :")
print(
    rejected_invalid.groupby("rejection_reason").head(1)[
        ["order_line_id", "order_date", "quantity",
         "discount_rate", "rejection_reason"]
    ].to_string(index=False)
)

print(f"\nExports : s3://{BUCKET}/{PREFIX}")
print("Nettoyage et exports S3 réussis.")