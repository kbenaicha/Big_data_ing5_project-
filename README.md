# Big_data_ing5_project-
# Analyse des ventes et des retours d’une boutique en ligne

## Auteurs
- Kawtar Benaicha
- Salma Bouzoubaa

## Prérequis
Compte Onyxia, Python 3.13, Git et accès à un bucket S3.
Les dépendances sont fixées dans `requirements.txt`.
## Dataset
Données synthétiques générées par notre équipe .
Source : [générateur Python](https://github.com/kbenaicha/Big_data_ing5_project-/blob/main/src/generate_data.py).
Taille brute : **2 356 475 octets (2,36 Mo)**, pour **30 300 lignes**.

Une ligne représente une ligne de commande. Colonnes :
`order_line_id`, `order_id`, `order_date`, `product_id`, `category`,
`quantity`, `unit_price`, `discount_rate`, `status`, `region`.
Des anomalies existante  permettent d’évaluer le nettoyage.

## Problématique
Quelles catégories génèrent le plus de chiffre d’affaires net ?
Quelles catégories présentent les taux de retour les plus élevés ?
Comment le nettoyage affecte-t-il les indicateurs globaux ?

## Chemins S3
on a préfére travaille sur un seule espace de travaille pour ne pas redondonée le travail : 
- Bucket : `user-k-benaicha-ece`
- Données brutes : `s3://user-k-benaicha-ece/bigdata_project/Raw/`
- Données traitées et résultats :
  `s3://user-k-benaicha-ece/bigdata_project/processed/`

## Reproduction
1. Cloner le dépôt et installer les dépendances :
   git clone https://github.com/kbenaicha/Big_data_ing5_project-.git
   cd Big_data_ing5_project-
   python -m pip install -r requirements.txt

3. Générer les données :
   python src/generate_data.py

4. Dans « Stockage de données » d’Onyxia, on a 
   `data/raw/orders_raw.csv` sous `bigdata_project/Raw/`.
5. Exécutation  les traitements dans cet ordre :
   python src/read_s3.py
   python src/clean_data.py
   python src/analyze.py
   python src/validate_results.py
   python src/benchmark.py
   python src/compare_cleaning.py

Le nettoyage produit 29 400 lignes conservées et 900 rejets,
doublons compris. Les résultats, rejets, contrôles et mesures sont
enregistrés sous `processed/`. La validation attend 36 contrôles
conformes sans écart. Les preuves numérotées figurent dans `evidence/`.

Pour relancer, réutiliser les données brutes sur S3 et reprendre à
l’étape 5. Les scripts remplacent les fichiers de sortie de même nom.
Après modification du nettoyage, relancer également tous les calculs
et contrôles suivants.
