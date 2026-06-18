"""
Generates recommendations and a free-text report from an evaluation result.

generate_report() calls the Groq LLM (llama-3.3-70b-versatile) when GROQ_API_KEY
is set, and falls back to a rule-based report otherwise.
"""
from typing import Any, Dict, List


# ── Rule-based recommendations (always used, LLM only enriches the report text) ──

def generate_recommendations(input_dict: Dict[str, Any], auc: float, risk_level: str) -> List[str]:
    gap = max(0.0, input_dict.get("train_accuracy", 0) - input_dict.get("test_accuracy", 0))
    recs: List[str] = []

    if gap > 0.1:
        recs.append("Réduire le sur-apprentissage : augmenter la régularisation, diminuer les epochs ou utiliser l'early stopping.")
    if input_dict.get("dropout", 0.1) < 0.1:
        recs.append("Augmenter le dropout (0.1 – 0.3) pour limiter la mémorisation des données d'entraînement.")
    if input_dict.get("weight_decay", 1e-4) < 1e-4:
        recs.append("Augmenter le weight decay (≥ 1e-4) pour pénaliser la complexité du modèle.")
    if not input_dict.get("data_augmentation", True):
        recs.append("Activer la data augmentation pour brouiller les signatures d'appartenance.")
    if input_dict.get("nb_train_samples", 10_000) < 5_000:
        recs.append("Élargir le dataset d'entraînement — la taille du dataset est le facteur le plus protecteur contre la MIA.")
    if input_dict.get("dataset_intra_variance", 1.0) < 0.3:
        recs.append("Le dataset présente une faible variance intra-classe : les données sont très similaires, ce qui facilite la mémorisation.")
    if auc >= 0.65:
        recs.append("Risque élevé — envisager une défense forte : Differential Privacy (DP-SGD), knowledge distillation ou MemGuard.")
    elif auc >= 0.55:
        recs.append("Risque modéré — surveiller le gap train/test et renforcer la régularisation.")

    if not recs:
        recs.append("Configuration robuste : maintenir la régularisation en place et surveiller le gap train/test à chaque entraînement.")

    return recs


# ── LLM report (Groq) with rule-based fallback ───────────────────────────────

def generate_report(input_dict: Dict[str, Any], auc: float, risk_level: str) -> str:
    from ..core.config import GROQ_API_KEY
    if GROQ_API_KEY:
        try:
            return _groq_report(input_dict, auc, risk_level)
        except Exception:
            pass
    return _rule_report(input_dict, auc, risk_level)


def _groq_report(input_dict: Dict[str, Any], auc: float, risk_level: str) -> str:
    from groq import Groq
    from ..core.config import GROQ_API_KEY

    gap         = max(0.0, input_dict.get("train_accuracy", 0) - input_dict.get("test_accuracy", 0))
    model_type  = input_dict.get("model_type", "inconnu")
    modality    = input_dict.get("dataset_modality", "inconnu")
    nb_params   = input_dict.get("nb_params", 0)
    nb_samples  = input_dict.get("nb_train_samples", 0)
    nb_classes  = input_dict.get("nb_classes", 0)
    dropout     = input_dict.get("dropout", 0)
    weight_decay = input_dict.get("weight_decay", 0)
    epochs      = input_dict.get("epochs", 0)
    aug         = "oui" if input_dict.get("data_augmentation") else "non"
    intra_var   = input_dict.get("dataset_intra_variance", "N/A")
    inter_dist  = input_dict.get("dataset_inter_class_distance", "N/A")
    train_acc   = input_dict.get("train_accuracy")
    test_acc    = input_dict.get("test_accuracy")

    perf_section = ""
    if train_acc is not None and test_acc is not None:
        perf_section = f"- Précision entraînement : {train_acc:.1%}, test : {test_acc:.1%}, gap : {gap:.3f}\n"

    prompt = f"""Tu es un expert en sécurité des modèles de machine learning, spécialisé dans les attaques par inférence d'appartenance (Membership Inference Attack, MIA).

Voici les caractéristiques du modèle évalué :
- Type de modèle : {model_type}
- Modalité des données : {modality}
- Nombre de paramètres : {nb_params:,}
- Profondeur : {input_dict.get('depth', 'N/A')}
- Dimension embedding : {input_dict.get('embed_dim', 'N/A')}
- Dataset : {nb_samples:,} échantillons, {nb_classes} classes
- Variance intra-classe : {intra_var}, Distance inter-classes : {inter_dist}
- Epochs : {epochs}, Batch size : {input_dict.get('batch_size', 'N/A')}
- Learning rate : {input_dict.get('learning_rate', 'N/A')}, Weight decay : {weight_decay}
- Dropout : {dropout}, Data augmentation : {aug}
{perf_section}
Résultat de l'évaluation :
- AUC d'attaque estimée : {auc:.3f}
- Niveau de risque MIA : {risk_level}

Rédige un rapport d'analyse concis (4 à 6 phrases) en français, destiné au développeur du modèle. Le rapport doit :
1. Interpréter l'AUC estimée et ce qu'elle signifie concrètement pour ce modèle
2. Identifier les 1 ou 2 facteurs principaux qui contribuent le plus au risque
3. Conclure avec le niveau d'urgence des actions à prendre

Ne liste pas de recommandations (elles sont fournies séparément). Écris en prose fluide, sans bullet points."""

    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()


def _rule_report(input_dict: Dict[str, Any], auc: float, risk_level: str) -> str:
    gap = max(0.0, input_dict.get("train_accuracy", 0) - input_dict.get("test_accuracy", 0))
    model_type = input_dict.get("model_type", "inconnu")
    nb_samples = input_dict.get("nb_train_samples", 0)

    risk_interp = {
        "Faible":  "suggère que le modèle résiste bien à ce type d'attaque",
        "Moyen":   "indique une vulnérabilité modérée qui mérite attention",
        "Élevé":   "révèle une vulnérabilité significative — des défenses sont nécessaires",
    }.get(risk_level, "")

    return (
        f"L'AUC d'attaque estimée à {auc:.3f} pour ce modèle {model_type} {risk_interp}. "
        f"Le gap train/test de {gap:.3f} et la taille du dataset ({nb_samples:,} échantillons) "
        f"sont les principaux facteurs influençant ce score. "
        f"Niveau de risque global : {risk_level}."
    )
