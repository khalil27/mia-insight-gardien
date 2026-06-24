"""
Génère le rapport d'analyse et les recommandations MIA.

Stratégie :
  - generate_full() : appel unique Groq (JSON mode) → rapport + recommandations
    cohérents entre eux, enrichis par le contexte RAG.
  - Fallback automatique vers les règles si Groq est absent ou échoue.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Point d'entrée principal ──────────────────────────────────────────────────

def generate_full(
    input_dict: Dict[str, Any],
    auc: float,
    risk_level: str,
    context_chunks: Optional[List[str]] = None,
) -> Tuple[str, List[str]]:
    """Retourne (rapport, recommandations).
    Groq génère les deux en un seul appel JSON pour garantir la cohérence.
    Fallback règles si GROQ_API_KEY absent ou appel échoue.
    """
    from ..core.config import GROQ_API_KEY
    chunks = context_chunks or []

    if not GROQ_API_KEY:
        logger.info("[report] GROQ_API_KEY absent → règles")
        return _rule_report(input_dict, auc, risk_level), _rule_recommendations(input_dict, auc, risk_level)

    try:
        logger.info("[report] Appel Groq JSON (llama-3.3-70b-versatile) — RAG chunks : %d", len(chunks))
        report, recs = _groq_full(input_dict, auc, risk_level, chunks)
        logger.info("[report] Groq OK — %d recommandations générées", len(recs))
        return report, recs
    except Exception as exc:
        logger.warning("[report] Groq ECHEC (%s) → fallback règles", exc)
        return _rule_report(input_dict, auc, risk_level), _rule_recommendations(input_dict, auc, risk_level)


# ── Groq — rapport + recommandations en un seul appel JSON ───────────────────

def _groq_full(
    input_dict: Dict[str, Any],
    auc: float,
    risk_level: str,
    context_chunks: List[str],
) -> Tuple[str, List[str]]:
    from groq import Groq
    from ..core.config import GROQ_API_KEY

    gap          = max(0.0, input_dict.get("train_accuracy", 0) - input_dict.get("test_accuracy", 0))
    model_type   = input_dict.get("model_type", "inconnu")
    modality     = input_dict.get("dataset_modality", "inconnu")
    nb_params    = input_dict.get("nb_params", 0)
    nb_samples   = input_dict.get("nb_train_samples", 0)
    nb_classes   = input_dict.get("nb_classes", 0)
    dropout      = input_dict.get("dropout", 0)
    weight_decay = input_dict.get("weight_decay", 0)
    epochs       = input_dict.get("epochs", 0)
    aug          = "oui" if input_dict.get("data_augmentation") else "non"
    intra_var    = input_dict.get("dataset_intra_variance", "N/A")
    inter_dist   = input_dict.get("dataset_inter_class_distance", "N/A")
    train_acc    = input_dict.get("train_accuracy")
    test_acc     = input_dict.get("test_accuracy")

    perf_section = ""
    if train_acc is not None and test_acc is not None:
        perf_section = f"- Précision entraînement : {train_acc:.1%}, test : {test_acc:.1%}, gap : {gap:.3f}\n"

    rag_section = ""
    if context_chunks:
        extraits = "\n---\n".join(context_chunks)
        rag_section = f"""
Extraits de littérature scientifique pertinents :
---
{extraits}
---
"""

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
{rag_section}
Génère une analyse en deux parties cohérentes l'une avec l'autre.

Réponds UNIQUEMENT en JSON valide avec cette structure :
{{
  "report": "Rapport en prose fluide (4 à 6 phrases) qui interprète l'AUC, identifie les facteurs de risque principaux, s'appuie sur la littérature si disponible, et conclut sur l'urgence.",
  "recommendations": [
    "Recommandation 1 concrète et actionnelle basée sur le rapport",
    "Recommandation 2",
    "..."
  ]
}}

Règles :
- Le rapport est en prose, sans bullet points, en français.
- Les recommandations découlent directement du rapport (pas de répétition mot pour mot).
- Entre 3 et 6 recommandations, chacune concrète et actionnelle.
- Aucun texte en dehors du JSON."""

    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=700,
        temperature=0.4,
    )

    raw  = response.choices[0].message.content.strip()
    data = json.loads(raw)

    report = str(data.get("report", "")).strip()
    recs   = data.get("recommendations", [])
    if not isinstance(recs, list):
        recs = [str(recs)]
    recs = [str(r).strip() for r in recs if str(r).strip()]

    if not report:
        raise ValueError("Groq a retourné un rapport vide")

    return report, recs


# ── Fallback règles ───────────────────────────────────────────────────────────

def _rule_report(input_dict: Dict[str, Any], auc: float, risk_level: str) -> str:
    gap        = max(0.0, input_dict.get("train_accuracy", 0) - input_dict.get("test_accuracy", 0))
    model_type = input_dict.get("model_type", "inconnu")
    nb_samples = input_dict.get("nb_train_samples", 0)

    risk_interp = {
        "Faible": "suggère que le modèle résiste bien à ce type d'attaque",
        "Moyen":  "indique une vulnérabilité modérée qui mérite attention",
        "Élevé":  "révèle une vulnérabilité significative — des défenses sont nécessaires",
    }.get(risk_level, "")

    return (
        f"L'AUC d'attaque estimée à {auc:.3f} pour ce modèle {model_type} {risk_interp}. "
        f"Le gap train/test de {gap:.3f} et la taille du dataset ({nb_samples:,} échantillons) "
        f"sont les principaux facteurs influençant ce score. "
        f"Niveau de risque global : {risk_level}."
    )


def _rule_recommendations(input_dict: Dict[str, Any], auc: float, risk_level: str) -> List[str]:
    gap  = max(0.0, input_dict.get("train_accuracy", 0) - input_dict.get("test_accuracy", 0))
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


# ── Compatibilité ascendante (anciens appels directs) ─────────────────────────

def generate_recommendations(input_dict: Dict[str, Any], auc: float, risk_level: str) -> List[str]:
    return _rule_recommendations(input_dict, auc, risk_level)


def generate_report(
    input_dict: Dict[str, Any],
    auc: float,
    risk_level: str,
    context_chunks: Optional[List[str]] = None,
) -> str:
    report, _ = generate_full(input_dict, auc, risk_level, context_chunks)
    return report
