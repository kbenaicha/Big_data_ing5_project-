import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
N_ROWS = 30_000
OUTPUT = Path("data/raw/orders_raw.csv")

rng = random.Random(SEED)
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

categories = ["Sport", "Maison", "Mode", "High-tech", "Beaute"]
regions = ["Ile-de-France", "Bretagne", "Pays de la Loire", "Occitanie"]
fields = [
    "order_line_id", "order_id", "order_date", "product_id",
    "category", "quantity", "unit_price", "discount_rate",
    "status", "region",
]

rows = []

for i in range(N_ROWS):
    product = rng.randint(1, 250)

    rows.append({
        "order_line_id": f"L{i + 1:06d}",
        "order_id": f"CMD{i // 3 + 1:06d}",
        "order_date": (
            date(2025, 1, 1) + timedelta(days=rng.randrange(365))
        ).isoformat(),
        "product_id": f"P{product:03d}",
        "category": categories[(product - 1) // 50],
        "quantity": rng.randint(1, 5),
        "unit_price": f"{rng.randint(500, 20000) / 100:.2f}",
        "discount_rate": rng.choice(["0.00", "0.05", "0.10", "0.20"]),
        "status": rng.choices(
            ["delivered", "returned", "cancelled"],
            weights=[80, 15, 5],
        )[0],
        "region": rng.choice(regions),
    })

# Groupes distincts pour pouvoir contrôler les anomalies précisément.
indices = rng.sample(range(N_ROWS), 800)

for i in indices[:200]:
    rows[i]["category"] = ""

for i in indices[200:400]:
    rows[i]["quantity"] = -1

for i in indices[400:600]:
    rows[i]["order_date"] = "2025-13-40"

for i in indices[600:800]:
    rows[i]["discount_rate"] = "1.50"

# Ajouter 300 doublons de lignes sans anomalie.
anomaly_indices = set(indices)
valid_indices = [i for i in range(N_ROWS) if i not in anomaly_indices]

for i in rng.sample(valid_indices, 300):
    rows.append(rows[i].copy())

rng.shuffle(rows)

with OUTPUT.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

size_bytes = OUTPUT.stat().st_size

print(f"Fichier : {OUTPUT}")
print(f"Graine : {SEED}")
print(f"Nombre de lignes : {len(rows):,}")
print(f"Taille : {size_bytes:,} octets ({size_bytes / 1_000_000:.2f} Mo)")
print("Anomalies :")
print("- 300 doublons supplémentaires")
print("- 200 catégories manquantes")
print("- 200 quantités négatives")
print("- 200 dates invalides")
print("- 200 remises supérieures à 1")

if not 1_000_000 <= size_bytes <= 5_000_000:
    raise ValueError("La taille du fichier brut doit être entre 1 et 5 Mo.")