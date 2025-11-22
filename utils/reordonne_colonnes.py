import pandas as pd
import os

def reordonner_colonnes_excel(fichier1, fichier2, fichier_reference="fichier1"):
    """
    Réordonne les colonnes de deux fichiers Excel pour qu'elles soient dans le même ordre.
    
    Args:
        fichier1 (str): Chemin vers le premier fichier Excel
        fichier2 (str): Chemin vers le deuxième fichier Excel
        fichier_reference (str): "fichier1" ou "fichier2" - quel fichier utiliser comme référence pour l'ordre
    """
    
    print("🔄 Début du réordonnement des colonnes...")
    
    # === Étape 1 : Vérifier l'existence des fichiers ===
    _verifier_fichiers(fichier1, fichier2)
    
    # === Étape 2 : Charger les deux fichiers ===
    df1, df2 = _charger_fichiers(fichier1, fichier2)
    
    # === Étape 3 : Afficher les informations sur les fichiers ===
    _afficher_infos_fichiers(fichier1, fichier2, df1, df2)
    
    # === Étape 4 : Vérifier et harmoniser les colonnes ===
    df1, df2 = _harmoniser_colonnes(df1, df2, fichier1, fichier2)
    
    # === Étape 5 : Déterminer l'ordre de référence ===
    ordre_reference = _determiner_ordre_reference(df1, df2, fichier_reference, fichier1, fichier2)
    
    # === Étape 6 : Réordonner et sauvegarder ===
    return _reordonner_et_sauvegarder(df1, df2, ordre_reference, fichier1, fichier2)

def _verifier_fichiers(fichier1, fichier2):
    """Vérifie l'existence des fichiers."""
    if not os.path.exists(fichier1):
        raise FileNotFoundError(f"❌ Le fichier {fichier1} n'existe pas.")
    if not os.path.exists(fichier2):
        raise FileNotFoundError(f"❌ Le fichier {fichier2} n'existe pas.")

def _charger_fichiers(fichier1, fichier2):
    """Charge les deux fichiers Excel."""
    print(f"📖 Chargement de {fichier1}...")
    df1 = pd.read_excel(fichier1)
    print(f"📖 Chargement de {fichier2}...")
    df2 = pd.read_excel(fichier2)
    return df1, df2

def _afficher_infos_fichiers(fichier1, fichier2, df1, df2):
    """Affiche les informations sur les fichiers."""
    print(f"\n📊 Informations sur les fichiers :")
    print(f"   {fichier1}: {len(df1)} lignes, {len(df1.columns)} colonnes")
    print(f"   {fichier2}: {len(df2)} lignes, {len(df2.columns)} colonnes")

def _harmoniser_colonnes(df1, df2, fichier1, fichier2):
    """Harmonise les colonnes entre les deux DataFrames."""
    colonnes1 = set(df1.columns)
    colonnes2 = set(df2.columns)
    
    if colonnes1 == colonnes2:
        return df1, df2
    
    print("\n⚠️  Les fichiers n'ont pas exactement les mêmes colonnes !")
    _afficher_differences_colonnes(colonnes1, colonnes2, fichier1, fichier2)
    
    print("\n🔧 Utilisation des colonnes communes uniquement...")
    colonnes_communes = colonnes1.intersection(colonnes2)
    return df1[list(colonnes_communes)], df2[list(colonnes_communes)]

def _afficher_differences_colonnes(colonnes1, colonnes2, fichier1, fichier2):
    """Affiche les différences entre les colonnes."""
    manquantes_dans_2 = colonnes1 - colonnes2
    manquantes_dans_1 = colonnes2 - colonnes1
    
    if manquantes_dans_2:
        print(f"   Colonnes présentes dans {fichier1} mais absentes dans {fichier2}:")
        for col in manquantes_dans_2:
            print(f"     - {col}")
    
    if manquantes_dans_1:
        print(f"   Colonnes présentes dans {fichier2} mais absentes dans {fichier1}:")
        for col in manquantes_dans_1:
            print(f"     - {col}")

def _determiner_ordre_reference(df1, df2, fichier_reference, fichier1, fichier2):
    """Détermine l'ordre de référence des colonnes."""
    if fichier_reference == "fichier1":
        print(f"\n📋 Utilisation de l'ordre des colonnes de {fichier1} comme référence")
        return list(df1.columns)
    else:
        print(f"\n📋 Utilisation de l'ordre des colonnes de {fichier2} comme référence")
        return list(df2.columns)

def _reordonner_et_sauvegarder(df1, df2, ordre_reference, fichier1, fichier2):
    """Réordonne les colonnes et sauvegarde les fichiers."""
    print("🔄 Réordonnancement des colonnes...")
    df1_reordonne = df1[ordre_reference]
    df2_reordonne = df2[ordre_reference]
    
    print(f"\n✅ Ordre final des colonnes ({len(ordre_reference)} colonnes):")
    for i, col in enumerate(ordre_reference, 1):
        print(f"   {i:2d}. {col}")
    
    # Sauvegarder les fichiers réordonnés
    nom_base1 = os.path.splitext(fichier1)[0]
    nom_base2 = os.path.splitext(fichier2)[0]
    
    fichier1_output = f"{nom_base1}_reordonne.xlsx"
    fichier2_output = f"{nom_base2}_reordonne.xlsx"
    
    print(f"\n💾Sauvegarde des fichiers réordonnés...")
    df1_reordonne.to_excel(fichier1_output, index=False)
    df2_reordonne.to_excel(fichier2_output, index=False)
    
    print(f"Fichiers sauvegardés :")
    print(f"   📄 {fichier1_output}")
    print(f"   📄 {fichier2_output}")
    
    return df1_reordonne, df2_reordonne

# === UTILISATION DU SCRIPT ===
if __name__ == "__main__":
    # 🔧 CONFIGURATION - Modifiez ces noms de fichiers selon vos besoins
    fichier_excel_1 = "BDD_Transparence_detaillés.xlsx"  # Premier fichier Excel
    fichier_excel_2 = "BDD_Transparence_detaillés_2.xlsx"  # Deuxième fichier Excel

    # Quel fichier utiliser comme référence pour l'ordre des colonnes ?
    # "fichier1" ou "fichier2"
    reference = "fichier1"
    
    try:
        # Exécuter le réordonnement
        df1, df2 = reordonner_colonnes_excel(
            fichier_excel_1, 
            fichier_excel_2, 
            fichier_reference=reference
        )
        
        print(f"\n🎉 Réordonnement terminé avec succès !")
        print(f"📊 Les deux fichiers ont maintenant leurs colonnes dans le même ordre.")
        
    except Exception as e:
        print(f"\n❌ Erreur lors du réordonnement : {e}")