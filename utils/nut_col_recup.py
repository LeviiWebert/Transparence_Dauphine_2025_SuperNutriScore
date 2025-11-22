import pandas as pd
import ast

# === Étape 1 : Charger le fichier existant ===
fichier = "combined_spreads_data1.xlsx"
print(f"🔍 Recherche du fichier : {fichier}")

# Vérifier si le fichier existe
import os
if not os.path.exists(fichier):
    print(f"❌ Fichier non trouvé : {fichier}")
    print("📁 Fichiers disponibles dans le dossier :")
    dossier = "/Users/lev.w/Desktop/M2 MIAGE/Transparence des algo/Projet/"
    if os.path.exists(dossier):
        fichiers_excel = [f for f in os.listdir(dossier) if f.endswith('.xlsx')]
        for f in fichiers_excel:
            print(f"   - {f}")
    raise FileNotFoundError(f"Le fichier {fichier} n'existe pas.")
else:
    print(f"✅ Fichier trouvé !")

df = pd.read_excel(fichier)

# === Étape 2 : Vérifier la colonne nutriments ===
if "nutriments" not in df.columns:
    raise ValueError("❌ La colonne 'nutriments' est introuvable dans le fichier.")

# === Étape 3 : CLÉS COHÉRENTES AVEC ELECTRI_FIXED.PY ===
# Les noms de colonnes créées doivent correspondre exactement aux critères ELECTRE TRI
nutriments_cles = {
    # Clés dans 'nutriments' → Noms de colonnes finaux (identiques aux critères ELECTRE)
    "energy-kcal_100g": "energy-kcal_100g",           # Énergie en kcal
    "sugars_100g": "sugars_100g",                     # Sucres
    "saturated-fat_100g": "fat_100g",                 # Graisses saturées → fat_100g  
    "sodium_100g": "sodium_100g",                     # Sodium
    "fruits-vegetables-nuts-estimate-from-ingredients_100g": "fruits_vegetables_nuts_100g",  # Fruits/légumes/noix
    "fiber_100g": "fiber_100g",                       # Fibres
    "proteins_100g": "proteins_100g",                 # Protéines
    "additives_n": "additives_n"                      # Nombre d'additifs
}

# NOUVEAU : Mapping pour les unités
nutriments_unites = {
    "energy-kcal_100g": "energy-kcal_unit",           # Unité pour l'énergie
    "sugars_100g": "sugars_unit",                     # Unité pour les sucres
    "saturated-fat_100g": "saturated-fat_unit",       # Unité pour les graisses saturées
    "sodium_100g": "sodium_unit",                     # Unité pour le sodium
    "fruits-vegetables-nuts-estimate-from-ingredients_100g": "%",  # Pas d'unité spécifique
    "fiber_100g": "fiber_unit",                       # Unité pour les fibres
    "proteins_100g": "proteins_unit",                 # Unité pour les protéines
    "additives_n": None                               # Pas d'unité (nombre)
}

# === Étape 4 : Fonction sûre d'extraction ===
def extraire_valeur(nutriments, cle):
    """Extrait une valeur nutritionnelle depuis la colonne 'nutriments'."""
    if isinstance(nutriments, dict):
        return nutriments.get(cle, 0)  # 0 par défaut au lieu de None
    if isinstance(nutriments, str):
        try:
            d = ast.literal_eval(nutriments)
            if isinstance(d, dict):
                return d.get(cle, 0)
        except Exception:
            return 0  # 0 par défaut en cas d'erreur
    return 0

# === Étape 5 : Extraire et ajouter les colonnes ELECTRE TRI ===
print(f"📊 Colonnes existantes dans le fichier : {len(df.columns)}")
print(f"🔍 Extraction des critères ELECTRE TRI...")

colonnes_ajoutees = []
for cle_nutriments, nom_colonne_finale in nutriments_cles.items():
    if nom_colonne_finale not in df.columns:  # Éviter de dupliquer
        # Extraire les valeurs depuis 'nutriments'
        df[nom_colonne_finale] = df["nutriments"].apply(lambda x: extraire_valeur(x, cle_nutriments))
        colonnes_ajoutees.append(nom_colonne_finale)
        print(f"   ✅ {nom_colonne_finale} (depuis {cle_nutriments})")
        
        # Afficher quelques valeurs pour vérification
        valeurs_non_nulles = df[df[nom_colonne_finale] != 0][nom_colonne_finale].head(3)
        if len(valeurs_non_nulles) > 0:
            print(f"      📋 Exemples: {list(valeurs_non_nulles)}")
        else:
            print(f"      ⚠️  Aucune valeur trouvée pour cette clé")
    else:
        print(f"   ⚠️  {nom_colonne_finale} existe déjà, pas de modification")

# === Étape 6 : Vérification de cohérence ELECTRE TRI ===
print(f"\n🔧 Vérification de cohérence avec ELECTRE TRI...")

# Critères attendus par ELECTRE TRI (depuis electri_fixed.py)
criteres_electre = [
    "energy-kcal_100g", "sugars_100g", "fat_100g", "sodium_100g",
    "fruits_vegetables_nuts_100g", "fiber_100g", "proteins_100g", "additives_n"
]

colonnes_manquantes = []
for critere in criteres_electre:
    if critere in df.columns:
        nb_valeurs = (df[critere] != 0).sum()
        print(f"   ✅ {critere}: {nb_valeurs} valeurs non-nulles")
    else:
        colonnes_manquantes.append(critere)
        print(f"   ❌ {critere}: MANQUANT")

if colonnes_manquantes:
    print(f"\n⚠️  Colonnes manquantes pour ELECTRE TRI: {', '.join(colonnes_manquantes)}")
    # Créer ces colonnes avec des valeurs par défaut
    for col in colonnes_manquantes:
        df[col] = 0
        print(f"   🔧 {col} créée avec valeurs par défaut (0)")
        colonnes_ajoutees.append(col)

# === Étape 7 : Sauvegarde du fichier final ===
output = "collecte_de_donnee_projet/combined_spreads_data2.xlsx"
df.to_excel(output, index=False)

print(f"\n✅ Extraction terminée ! Fichier enregistré sous : {output}")
print(f"📊 Colonnes totales dans le fichier final : {len(df.columns)}")
print(f"🆕 Nouvelles colonnes ajoutées ({len(colonnes_ajoutees)}) : {', '.join(colonnes_ajoutees)}")
print(f"📋 Toutes les colonnes originales ont été conservées !")

# === Étape 8 : Test de cohérence finale ===
print(f"\n🎯 Test de cohérence avec ELECTRE TRI:")
tous_criteres_presents = all(critere in df.columns for critere in criteres_electre)
if tous_criteres_presents:
    print(f"   ✅ SUCCÈS: Tous les critères ELECTRE TRI sont présents !")
    print(f"   📊 Le fichier est prêt pour l'analyse ELECTRE TRI")
else:
    criteres_manquants = [c for c in criteres_electre if c not in df.columns]
    print(f"   ❌ ÉCHEC: Critères manquants: {criteres_manquants}")

# === Étape 9 : Aperçu des données nutritionnelles ===
print(f"\n📋 Aperçu des critères ELECTRE TRI (5 premières lignes non-nulles):")
for critere in criteres_electre:
    if critere in df.columns:
        valeurs = df[df[critere] != 0][critere].head(5)
        if len(valeurs) > 0:
            print(f"   {critere}: {list(valeurs)}")
        else:
            print(f"   {critere}: [Aucune valeur trouvée]")