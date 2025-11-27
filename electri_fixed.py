# electre_tri_nutriscore.py - Version simplifiée
import pandas as pd
import numpy as np
import ast
import json
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================
INPUT_XLSX = "collecte_de_donnee_projet/utils/combined_spreads_data.xlsx"
OUTPUT_XLSX = "electre_tri_resultats.xlsx"

# Critères ELECTRE TRI - Poids équilibrés pour meilleure discrimination
CRITERIA = {
    "energy-kcal_100g": {"direction": "cost", "weight": 0.12},      # Énergie - importance modérée
    "sugars_100g": {"direction": "cost", "weight": 0.12},      # Sucres - réduit pour éviter sur-pénalisation  
    "fat_100g": {"direction": "cost", "weight": 0.12}, # Graisses saturées - réduit
    "sodium_100g": {"direction": "cost", "weight": 0.08},      # Sodium - moins important pour pâtes à tartiner
    "fruits_vegetables_nuts_100g": {"direction": "benefit", "weight": 0.18}, # Noix/fruits - très important !
    "fiber_100g": {"direction": "benefit", "weight": 0.15},    # Fibres - valorisées
    "proteins_100g": {"direction": "benefit", "weight": 0.13}, # Protéines - augmentées
    "additives_n": {"direction": "cost", "weight": 0.10}       # Additifs - conservé
}
# Total: cost = 0.54, benefit = 0.46 (plus équilibré)

# Classes ELECTRE TRI (5 classes de A' à E')
CLASSES = ["A'", "B'", "C'", "D'", "E'"]  # A' = excellent, E' = à éviter

# Seuils majoritaires selon les exigences du projet
LAMBDA_VALUES = [0.6, 0.7]  # λ=0.6 pour optimiste, λ=0.7 pour pessimiste

# =============================================================================
# PROFILS LIMITES (b1 à b6) - CALIBRÉS SUR DONNÉES NETTOYÉES
# =============================================================================
# Rappel de la logique selon le projet (Page 10) :
# b6 = Borne Supérieure (Perfection inatteignable, pour fermer le modèle)
# b5 = Frontière A'/B' (Excellence nutritionnelle)
# b4 = Frontière B'/C' (Bon produit)
# b3 = Frontière C'/D' (Produit moyen/standard)
# b2 = Frontière D'/E' (Produit à limiter fortement)
# b1 = Borne Inférieure (Pire que le pire produit, pour fermer le modèle)

DEFAULT_PROFILES = [
    # --- b1 : Borne Inférieure (Pire Cauchemar - INATTEIGNABLE) ---
    # Valeurs pires que tes max observés (Sodium > 40, Sucre > 90)
    {"energy-kcal_100g": 1000, "sugars_100g": 101, "fat_100g": 101, "sodium_100g": 100,
     "fruits_vegetables_nuts_100g": -1, "fiber_100g": -1, "proteins_100g": -1, "additives_n": 50},

    # --- b2 : Frontière E' / D' (Le seuil "Rouge") ---
    # Tes graphiques montrent que bcp de produits sont entre 500-600 kcal.
    # On sévit ici : si > 600 kcal ou > 35g sucre, c'est E.
    {"energy-kcal_100g": 600, "sugars_100g": 35, "fat_100g": 20, "sodium_100g": 1.5,
     "fruits_vegetables_nuts_100g": 0, "fiber_100g": 1.0, "proteins_100g": 2.0, "additives_n": 6},

    # --- b3 : Frontière D' / C' (Le seuil "Jaune") ---
    # Moyenne gamme. Correspond au "ventre mou" de tes courbes.
    {"energy-kcal_100g": 480, "sugars_100g": 20, "fat_100g": 10, "sodium_100g": 0.5,
     "fruits_vegetables_nuts_100g": 10, "fiber_100g": 2.5, "proteins_100g": 4.0, "additives_n": 4},

    # --- b4 : Frontière C' / B' (Le seuil "Vert Clair") ---
    # On commence à être exigeant. Moins de 10g de sucre (rare dans tes données -> valorisant).
    {"energy-kcal_100g": 350, "sugars_100g": 10, "fat_100g": 5, "sodium_100g": 0.2,
     "fruits_vegetables_nuts_100g": 40, "fiber_100g": 4.0, "proteins_100g": 6.0, "additives_n": 2},

    # --- b5 : Frontière B' / A' (L'Excellence "Vert Foncé") ---
    # Très peu calorique, très naturel.
    # Note: Sodium à 0.05 car ta courbe montre que bcp de produits sont à 0.
    {"energy-kcal_100g": 200, "sugars_100g": 5, "fat_100g": 2, "sodium_100g": 0.05,
     "fruits_vegetables_nuts_100g": 80, "fiber_100g": 7.0, "proteins_100g": 9.0, "additives_n": 0},

    # --- b6 : Borne Supérieure (Perfection Absolue - INATTEIGNABLE) ---
    # Inatteignable par définition.
    {"energy-kcal_100g": -1, "sugars_100g": -1, "fat_100g": -1, "sodium_100g": -1,
     "fruits_vegetables_nuts_100g": 101, "fiber_100g": 101, "proteins_100g": 101, "additives_n": -1}
]

# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================
def get_column_values(df, column_name):
    """Récupère les valeurs d'une colonne et les convertit en nombres."""
    if column_name in df.columns:
        # Convertir en nombres, mettre 0 si impossible
        values = pd.to_numeric(df[column_name], errors='coerce').fillna(0)
        return values
    else:
        # Si la colonne n'existe pas, créer une série de zéros
        return pd.Series([0] * len(df))

def extract_criteria_values(df):
    """Extrait les valeurs nutritionnelles pour chaque critère ELECTRE TRI."""
    print("🔍 Extraction des critères nutritionnels...")
    
    # CORRECTION: Vos colonnes ont déjà les bons noms !
    # Mapping direct : critère ELECTRE → nom de colonne dans votre fichier
    colonnes = {
        "energy-kcal_100g": "energy-kcal_100g",              # ✅ Existe déjà
        "sugars_100g": "sugars_100g",                        # ✅ Existe déjà
        "fat_100g": "fat_100g",                              # ✅ Existe déjà
        "sodium_100g": "sodium_100g",                        # ✅ Existe déjà
        "fruits_vegetables_nuts_100g": "fruits_vegetables_nuts_100g",  # ✅ Existe déjà
        "fiber_100g": "fiber_100g",                          # ✅ Existe déjà
        "proteins_100g": "proteins_100g",                    # ✅ Existe déjà
        "additives_n": "additives_n"                         # ✅ Existe déjà
    }
    
    # Créer un nouveau DataFrame avec les critères
    criteres_data = {}
    
    print("📋 Vérification des colonnes dans le fichier:")
    print(f"   Colonnes disponibles: {list(df.columns)}")
    
    for critere, nom_colonne in colonnes.items():
        # Récupérer les valeurs de chaque critère
        valeurs = get_column_values(df, nom_colonne)
        criteres_data[critere] = valeurs
        
        # Afficher le résultat avec statistiques
        if nom_colonne in df.columns:
            nb_non_nulles = (valeurs != 0).sum()
            nb_nulles = (valeurs == 0).sum()
            print(f"  ✅ {critere} trouvé dans '{nom_colonne}': {nb_non_nulles} valeurs, {nb_nulles} zéros")
        else:
            print(f"  ❌ {critere} non trouvé, création avec valeurs par défaut (0)")
    
    return pd.DataFrame(criteres_data)

def safe_eval(x):
    """Convertit une chaîne en dictionnaire de manière sûre."""
    if isinstance(x, dict):
        return x
    if pd.isna(x):
        return {}
    try:
        return ast.literal_eval(str(x))
    except:
        try:
            return json.loads(str(x))
        except:
            return {}

# =============================================================================
# ALGORITHME ELECTRE TRI - COEUR DE LA MÉTHODE
# =============================================================================

def calculate_concordance(product_values, profile_values):
    """
    Calcule si un produit est meilleur qu'un profil de référence.
    
    Retourne un score entre 0 et 1 :
    - Plus proche de 1 = le produit dépasse le profil sur la plupart des critères
    - Plus proche de 0 = le produit ne dépasse pas le profil
    """
    total_score = 0.0
    
    # Vérifier chaque critère un par un
    for critere_nom, critere_config in CRITERIA.items():
        poids = critere_config["weight"]  # Importance du critère
        type_critere = critere_config["direction"]  # "benefit" ou "cost"
        
        # Valeurs du produit et du profil pour ce critère
        valeur_produit = product_values.get(critere_nom, 0)
        valeur_profil = profile_values.get(critere_nom, 0)
        
        # Vérifier si le produit est meilleur que le profil
        if type_critere == "benefit":  
            # Pour les bons critères (fibres, protéines...) : plus = mieux
            produit_meilleur = valeur_produit >= valeur_profil
        else:  
            # Pour les mauvais critères (sucres, graisses...) : moins = mieux
            produit_meilleur = valeur_produit <= valeur_profil
            
        # Si le produit est meilleur, ajouter le poids au score total
        if produit_meilleur:
            total_score += poids
    
    return total_score

def classify_pessimistic(product_values, profiles, seuil_majorite):
    """
    Classification pessimiste : commence par les profils les plus hauts.
    CORRIGÉ: Attribution correcte des classes selon les bornes b1-b6
    """
    # Commencer par le profil le plus élevé (b5) et descendre vers (b2)
    # b6 et b1 sont des bornes inatteignables, on ne les teste pas
    for numero_profil in range(5, 1, -1):  # 5, 4, 3, 2 (b5, b4, b3, b2)
        profil = profiles[numero_profil - 1]  # Liste commence à 0
        
        # Calculer si le produit dépasse ce profil
        score = calculate_concordance(product_values, profil)
        
        if score >= seuil_majorite:
            # Le produit dépasse le profil, on l'affecte à la classe SUPÉRIEURE
            if numero_profil == 5: return "A'"    # Dépasse b5 → Excellence
            elif numero_profil == 4: return "B'"  # Dépasse b4 → Très bon
            elif numero_profil == 3: return "C'"  # Dépasse b3 → Bon  
            elif numero_profil == 2: return "D'"  # Dépasse b2 → Moyen
    
    # Si le produit ne dépasse aucun profil (même pas b2), c'est le plus mauvais
    return "E'"

def classify_optimistic(product_values, profiles, seuil_majorite):
    """
    Classification optimiste conforme au Slide 13 (utilise la Préférence Stricte P).
    """
    # On monte de b2 vers b5 (π2 vers π5 dans les slides)
    # Rappel: profiles[0] est b1, profiles[1] est b2...
    for numero_profil in range(2, 6): 
        profil = profiles[numero_profil - 1] 
        
        # 1. Est-ce que le Profil Surclasse le Produit ? (b S a)
        score_profil_sur_produit = calculate_concordance(profil, product_values)
        b_S_a = score_profil_sur_produit >= seuil_majorite
        
        # 2. Est-ce que le Produit Surclasse le Profil ? (a S b)
        score_produit_sur_profil = calculate_concordance(product_values, profil)
        a_S_b = score_produit_sur_profil >= seuil_majorite
        
        # 3. Préférence Stricte (b P a) <=> (b S a) ET NON (a S b)
        b_P_a = b_S_a and not a_S_b
        
        if b_P_a:
            # Le profil est STRICTEMENT meilleur que le produit.
            # Le produit ne peut pas appartenir à cette catégorie supérieure, il tombe dans celle d'en dessous.
            if numero_profil == 2: return "E'"    # Stoppé par b2
            elif numero_profil == 3: return "D'"  # Stoppé par b3
            elif numero_profil == 4: return "C'"
            elif numero_profil == 5: return "B'"
            
    # Si aucun profil n'est strictement meilleur, c'est le top
    return "A'"

def compare_with_nutriscore(df_results):
    """
    Compare les classifications ELECTRE TRI avec le Nutri-Score original.
    
    Args:
        df_results: DataFrame avec les résultats ELECTRE TRI
    
    Returns:
        dict: statistiques de comparaison et matrices de confusion
    """
    # Mapping Nutri-Score vers nos classes ELECTRE TRI
    nutriscore_mapping = {'A': "A'", 'B': "B'", 'C': "C'", 'D': "D'", 'E': "E'"}
    
    stats = {}
    
    for lambda_val in LAMBDA_VALUES:
        df_lambda = df_results[df_results['lambda'] == lambda_val]
        
        # Mapper le Nutri-Score original
        df_lambda = df_lambda.copy()
        df_lambda['nutriscore_mapped'] = df_lambda['nutriscore_original'].map(nutriscore_mapping)
        
        # Filtrer les produits avec un Nutri-Score valide
        df_valid = df_lambda.dropna(subset=['nutriscore_mapped'])
        
        if len(df_valid) > 0:
            # Comparaisons simples
            accord_pessimiste = (df_valid['classe_pessimiste'] == df_valid['nutriscore_mapped']).sum()
            accord_optimiste = (df_valid['classe_optimiste'] == df_valid['nutriscore_mapped']).sum()
            
            total = len(df_valid)
            
            # === MATRICES DE CONFUSION ===
            # Matrice pour pessimiste
            confusion_pessimiste = pd.crosstab(
                df_valid['nutriscore_mapped'], 
                df_valid['classe_pessimiste'], 
                rownames=['Nutri-Score'], 
                colnames=['ELECTRE TRI Pessimiste'],
                margins=True
            )
            
            # Matrice pour optimiste
            confusion_optimiste = pd.crosstab(
                df_valid['nutriscore_mapped'], 
                df_valid['classe_optimiste'], 
                rownames=['Nutri-Score'], 
                colnames=['ELECTRE TRI Optimiste'],
                margins=True
            )
            
            stats[f'lambda_{lambda_val}'] = {
                'total_produits': total,
                'accord_pessimiste': accord_pessimiste,
                'accord_optimiste': accord_optimiste,
                'taux_accord_pessimiste': round(accord_pessimiste / total * 100, 1),
                'taux_accord_optimiste': round(accord_optimiste / total * 100, 1),
                'desaccord_pessimiste': total - accord_pessimiste,
                'desaccord_optimiste': total - accord_optimiste,
                'matrice_confusion_pessimiste': confusion_pessimiste,
                'matrice_confusion_optimiste': confusion_optimiste
            }
    
    return stats

def generate_visualizations(df_results, comparison_stats, output_dir="graphiques"):
    """
    Génère les graphiques et visualisations pour l'analyse ELECTRE TRI.
    
    Args:
        df_results: DataFrame avec les résultats ELECTRE TRI
        comparison_stats: statistiques de comparaison avec Nutri-Score
        output_dir: dossier de sortie pour les graphiques
    """
    # Créer le dossier de sortie
    Path(output_dir).mkdir(exist_ok=True)
    
    # Configuration matplotlib
    plt.style.use('default')
    plt.rcParams['figure.figsize'] = (12, 8)
    plt.rcParams['font.size'] = 10
    
    # === 1. RÉPARTITION DES CLASSIFICATIONS ===
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('Répartition des Classifications ELECTRE TRI', fontsize=16, fontweight='bold')
    
    for idx, lambda_val in enumerate(LAMBDA_VALUES):
        df_lambda = df_results[df_results['lambda'] == lambda_val]
        
        # Pessimiste
        pess_counts = df_lambda['classe_pessimiste'].value_counts()
        axes[idx, 0].pie(pess_counts.values, labels=pess_counts.index, autopct='%1.1f%%', 
                        colors=['#2E8B57', '#32CD32', '#FFD700', '#FF8C00', '#DC143C'])
        axes[idx, 0].set_title(f'Pessimiste λ={lambda_val}')
        
        # Optimiste
        opt_counts = df_lambda['classe_optimiste'].value_counts()
        axes[idx, 1].pie(opt_counts.values, labels=opt_counts.index, autopct='%1.1f%%',
                        colors=['#2E8B57', '#32CD32', '#FFD700', '#FF8C00', '#DC143C'])
        axes[idx, 1].set_title(f'Optimiste λ={lambda_val}')
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/repartition_classifications.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # === 2. COMPARAISON PESSIMISTE VS OPTIMISTE ===
    fig, ax = plt.subplots(1, 1, figsize=(12, 8))
    
    lambda_labels = [f'λ={lam}' for lam in LAMBDA_VALUES]
    x = np.arange(len(lambda_labels))
    
    pess_counts = []
    opt_counts = []
    
    for lambda_val in LAMBDA_VALUES:
        df_lambda = df_results[df_results['lambda'] == lambda_val]
        pess_counts.append(df_lambda['classe_pessimiste'].value_counts().to_dict())
        opt_counts.append(df_lambda['classe_optimiste'].value_counts().to_dict())
    
    # Créer un graphique en barres groupées
    width = 0.35
    classes = CLASSES
    colors = ['#2E8B57', '#32CD32', '#FFD700', '#FF8C00', '#DC143C']
    
    bottom_pess = np.zeros(len(lambda_labels))
    bottom_opt = np.zeros(len(lambda_labels))
    
    for i, class_name in enumerate(classes):
        pess_vals = [pess_counts[j].get(class_name, 0) for j in range(len(lambda_labels))]
        opt_vals = [opt_counts[j].get(class_name, 0) for j in range(len(lambda_labels))]
        
        ax.bar(x - width/2, pess_vals, width, bottom=bottom_pess, 
               label=f'{class_name} (Pess)', color=colors[i], alpha=0.8)
        ax.bar(x + width/2, opt_vals, width, bottom=bottom_opt,
               label=f'{class_name} (Opt)', color=colors[i], alpha=0.5)
        
        bottom_pess += pess_vals
        bottom_opt += opt_vals
    
    ax.set_xlabel('Seuil Lambda')
    ax.set_ylabel('Nombre de produits')
    ax.set_title('Comparaison Pessimiste vs Optimiste par Seuil Lambda')
    ax.set_xticks(x)
    ax.set_xticklabels(lambda_labels)
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/comparaison_pessimiste_optimiste.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # === 3. MATRICES DE CONFUSION GRAPHIQUES ===
    if comparison_stats:
        for lambda_key, stats in comparison_stats.items():
            lambda_val = lambda_key.split('_')[1]
            
            # Matrice de confusion Pessimiste
            fig, ax = plt.subplots(1, 1, figsize=(10, 8))
            confusion_pess = stats['matrice_confusion_pessimiste'].iloc[:-1, :-1]  # Exclure les totaux
            
            sns.heatmap(confusion_pess, annot=True, fmt='d', cmap='Blues', 
                       ax=ax, cbar_kws={'label': 'Nombre de produits'})
            ax.set_title(f'Matrice de Confusion - Pessimiste (λ={lambda_val})')
            ax.set_xlabel('ELECTRE TRI Prédiction')
            ax.set_ylabel('Nutri-Score Réel')
            
            plt.tight_layout()
            plt.savefig(f'{output_dir}/confusion_pessimiste_lambda_{lambda_val.replace(".", "_")}.png', 
                       dpi=300, bbox_inches='tight')
            plt.close()
            
            # Matrice de confusion Optimiste
            fig, ax = plt.subplots(1, 1, figsize=(10, 8))
            confusion_opt = stats['matrice_confusion_optimiste'].iloc[:-1, :-1]  # Exclure les totaux
            
            sns.heatmap(confusion_opt, annot=True, fmt='d', cmap='Oranges',
                       ax=ax, cbar_kws={'label': 'Nombre de produits'})
            ax.set_title(f'Matrice de Confusion - Optimiste (λ={lambda_val})')
            ax.set_xlabel('ELECTRE TRI Prédiction')
            ax.set_ylabel('Nutri-Score Réel')
            
            plt.tight_layout()
            plt.savefig(f'{output_dir}/confusion_optimiste_lambda_{lambda_val.replace(".", "_")}.png',
                       dpi=300, bbox_inches='tight')
            plt.close()
    
    # === 4. TAUX D'ACCORD AVEC NUTRI-SCORE ===
    if comparison_stats:
        fig, ax = plt.subplots(1, 1, figsize=(10, 6))
        
        lambdas = []
        taux_pess = []
        taux_opt = []
        
        for lambda_key, stats in comparison_stats.items():
            lambda_val = lambda_key.split('_')[1]
            lambdas.append(f'λ={lambda_val}')
            taux_pess.append(stats['taux_accord_pessimiste'])
            taux_opt.append(stats['taux_accord_optimiste'])
        
        x = np.arange(len(lambdas))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, taux_pess, width, label='Pessimiste', 
                      color='#4169E1', alpha=0.8)
        bars2 = ax.bar(x + width/2, taux_opt, width, label='Optimiste',
                      color='#FF6347', alpha=0.8)
        
        # Ajouter les valeurs sur les barres
        for bar in bars1:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                   f'{height:.1f}%', ha='center', va='bottom')
        
        for bar in bars2:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                   f'{height:.1f}%', ha='center', va='bottom')
        
        ax.set_xlabel('Seuil Lambda')
        ax.set_ylabel('Taux d\'accord (%)')
        ax.set_title('Taux d\'accord avec le Nutri-Score par Méthode et Seuil')
        ax.set_xticks(x)
        ax.set_xticklabels(lambdas)
        ax.legend()
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(f'{output_dir}/taux_accord_nutriscore.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    # === 5. DISTRIBUTION DES CRITÈRES ===
    fig, axes = plt.subplots(2, 4, figsize=(20, 10))
    fig.suptitle('Distribution des Valeurs des Critères', fontsize=16, fontweight='bold')
    
    axes = axes.flatten()
    for idx, (criterion, config) in enumerate(CRITERIA.items()):
        df_unique = df_results[df_results['lambda'] == LAMBDA_VALUES[0]]  # Prendre une seule fois
        values = df_unique[criterion]
        
        axes[idx].hist(values, bins=30, alpha=0.7, color='skyblue', edgecolor='black')
        axes[idx].set_title(f'{criterion}\n({config["direction"]} criterion)')
        axes[idx].set_xlabel('Valeur')
        axes[idx].set_ylabel('Fréquence')
        axes[idx].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/distribution_criteres.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"📊 Graphiques sauvegardés dans le dossier '{output_dir}/'")
    return output_dir

# =============================================================================
# PIPELINE PRINCIPAL ELECTRE TRI
# =============================================================================

def clean_nutriscore_value(row):
    """Nettoie et valide une valeur de Nutri-Score."""
    if 'nutriscore_grade' in row and pd.notna(row['nutriscore_grade']):
        raw_value = str(row['nutriscore_grade']).strip().upper()
        # Ne garder que les vraies lettres Nutri-Score
        if raw_value in ['A', 'B', 'C', 'D', 'E']:
            return raw_value
    return 'N/A'  # Valeurs corrompues → N/A

def classify_products(df, df_criteria, profiles):
    """Classifie tous les produits avec ELECTRE TRI."""
    results = []
    
    print(f"\n🔢 Classification des {len(df)} produits...")
    
    # Selon les exigences du projet : λ=0.6 optimiste, λ=0.7 pessimiste
    for lambda_val in LAMBDA_VALUES:
        print(f"  Traitement avec seuil λ = {lambda_val}")
        
        for idx, row in df.iterrows():
            # Récupérer les valeurs nutritionnelles du produit
            product_values = {}
            for critere in CRITERIA.keys():
                product_values[critere] = df_criteria.loc[idx, critere]
            
            # CORRECTION: Utiliser lambda_val pour voir la différence entre les seuils
            # Pour chaque valeur de lambda, appliquer aux DEUX méthodes
            classe_pessimiste = classify_pessimistic(product_values, profiles, lambda_val)
            classe_optimiste = classify_optimistic(product_values, profiles, lambda_val)
            
            # Nettoyer le Nutri-Score
            nutriscore_value = clean_nutriscore_value(row)
            
            # Sauvegarder le résultat
            results.append({
                'product_name': row.get('product_name', f'Produit_{idx}'),
                'nutriscore_original': nutriscore_value,
                'lambda': lambda_val,  # Garder lambda_val pour la compatibilité des analyses
                'classe_pessimiste': classe_pessimiste,
                'classe_optimiste': classe_optimiste,
                **product_values
            })
    
    return pd.DataFrame(results)

def save_results_to_excel(df_results, profiles, output_file):
    """Sauvegarde les résultats dans un fichier Excel."""
    print(f"\n💾 Sauvegarde des résultats dans {output_file}...")
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Feuille principale
        df_results.to_excel(writer, sheet_name='Classifications_ELECTRE_TRI', index=False)
        
        # Feuilles par lambda
        for lambda_val in LAMBDA_VALUES:
            df_lambda = df_results[df_results['lambda'] == lambda_val]
            sheet_name = f'Lambda_{str(lambda_val).replace(".", "_")}'
            df_lambda.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # Feuille des profils
        df_profiles = pd.DataFrame(profiles)
        df_profiles.index = [f'π{i+1}' for i in range(len(profiles))]
        df_profiles.to_excel(writer, sheet_name='Profils_Limites')
        
        # Configuration des critères
        df_config = pd.DataFrame.from_dict(CRITERIA, orient='index')
        df_config.to_excel(writer, sheet_name='Configuration_Criteres')

def print_comparison_results(comparison_stats):
    """Affiche les résultats de comparaison avec le Nutri-Score."""
    for lambda_key, stats in comparison_stats.items():
        lambda_val = lambda_key.split('_')[1]
        print(f"\n  📊 Seuil λ = {lambda_val} ({stats['total_produits']} produits avec Nutri-Score):")
        print(f"    🎯 Accord Pessimiste: {stats['accord_pessimiste']}/{stats['total_produits']} ({stats['taux_accord_pessimiste']}%)")
        print(f"    🎯 Accord Optimiste:  {stats['accord_optimiste']}/{stats['total_produits']} ({stats['taux_accord_optimiste']}%)")

def run_electre_tri(input_file=INPUT_XLSX, output_file=OUTPUT_XLSX, profiles=None):
    """Fonction principale : lance l'analyse ELECTRE TRI complète."""
    print("🔄 Début de l'analyse ELECTRE TRI")
    print(f"📂 Fichier d'entrée: {input_file}")
    
    # Étape 1: Charger les données
    df = pd.read_excel(input_file)
    print(f"📊 {len(df)} produits chargés")
    
    # Étape 2: Extraire les critères nutritionnels
    df_criteria = extract_criteria_values(df)
    print(f"✅ Critères extraits: {list(df_criteria.columns)}")
    
    # Étape 3: Définir les profils
    if profiles is None:
        profiles = DEFAULT_PROFILES
        print("⚙️  Utilisation des profils par défaut")
    
    # Étape 4: Classifier tous les produits
    df_results = classify_products(df, df_criteria, profiles)
    
    # Étape 5: Sauvegarder les résultats
    save_results_to_excel(df_results, profiles, output_file)
    print(f"✅ Analyse terminée ! Résultats sauvegardés dans {output_file}")
    
    # Étape 6: Analyser les résultats
    print("\n� Comparaison avec le Nutri-Score original:")
    nutriscore_count = df_results['nutriscore_original'].value_counts()
    total_with_nutriscore = len(df_results[df_results['nutriscore_original'] != 'N/A'])
    print(f"    Total avec Nutri-Score valide: {total_with_nutriscore}")
    
    if total_with_nutriscore > 0:
        comparison_stats = compare_with_nutriscore(df_results)
        print_comparison_results(comparison_stats)
    
    # Étape 7: Afficher la répartition des classes
    print("\n📈 Répartition des classifications ELECTRE TRI:")
    for lambda_val in LAMBDA_VALUES:
        df_lambda = df_results[df_results['lambda'] == lambda_val]
        print(f"  λ = {lambda_val}:")
        print(f"    Pessimiste: {df_lambda['classe_pessimiste'].value_counts().to_dict()}")
        print(f"    Optimiste:  {df_lambda['classe_optimiste'].value_counts().to_dict()}")
    
    # Étape 8: Générer les graphiques
    print("\n📊 Génération des visualisations...")
    try:
        graphics_dir = generate_visualizations(df_results, comparison_stats if total_with_nutriscore > 0 else {})
        print(f"✅ Graphiques créés dans le dossier '{graphics_dir}/'")
    except Exception as e:
        print(f"⚠️  Erreur lors de la génération des graphiques: {e}")
    
    return df_results

if __name__ == "__main__":
    # Lancement avec les paramètres par défaut
    run_electre_tri()
    
    # Exemple d'utilisation avec profils personnalisés:
    # profils_custom = [
    #     {"energy-kcal_100g": 2500, "sugars_100g": 30, "fat_100g": 12, "sodium_100g": 2.0,
    #      "fruits_vegetables_nuts_100g": 0, "fiber_100g": 0, "proteins_100g": 1, "additives_n": 15},  # π1
    #     {"energy-kcal_100g": 2000, "sugars_100g": 20, "fat_100g": 8, "sodium_100g": 1.2,
    #      "fruits_vegetables_nuts_100g": 10, "fiber_100g": 1, "proteins_100g": 3, "additives_n": 8}, # π2
    #     # ... 4 autres profils complets
    # ]
    # run_electre_tri(profiles=profils_custom)