import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import boto3
import pandas as pd

BUCKET = "user-k-benaicha-ece"
KEY = "bigdata_project/Raw/orders_raw.csv"

endpoint = (
    os.getenv("AWS_ENDPOINT_URL_S3")
    or os.getenv("AWS_ENDPOINT_URL")
    or os.getenv("AWS_S3_ENDPOINT")
    or os.getenv("S3_ENDPOINT")
)

if not endpoint:
    raise RuntimeError("Adresse du serveur S3 absente de l'environnement.")

if not endpoint.startswith(("https://", "http://")):
    endpoint = "https://" + endpoint

namespace_file = Path(
    "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
)

print("Date UTC :", datetime.now(timezone.utc).isoformat())
if namespace_file.exists():
    print("Namespace :", namespace_file.read_text().strip())

# Les identifiants sont lus par boto3 depuis la configuration Onyxia.
s3 = boto3.client("s3", endpoint_url=endpoint)
response = s3.get_object(Bucket=BUCKET, Key=KEY)

with response["Body"] as stream:
    content = stream.read()

df = pd.read_csv(BytesIO(content))

print(f"Source : s3://{BUCKET}/{KEY}")
print(f"Taille : {len(content):,} octets")
print(f"Lignes : {len(df):,}")
print(f"Colonnes : {len(df.columns)}")
print("Noms des colonnes :", ", ".join(df.columns))
print("Lecture S3 réussie.")