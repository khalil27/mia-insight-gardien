# Backend — MIA Insight Guardian

API FastAPI qui implémente le pipeline multi-agents d'évaluation MIA.

---

## Démarrage rapide

```bash
cd backend

# Créer l'environnement virtuel (une seule fois)
python -m venv .venv

# Activer
.venv\Scripts\activate          # Windows PowerShell
# source .venv/bin/activate     # Linux / macOS

# Installer les dépendances
pip install -r requirements.txt

# Lancer
uvicorn app.main:app --reload --port 8000
```

**Swagger UI** : http://localhost:8000/docs

---

## Endpoints

| Méthode | Chemin | Auth | Description |
|---------|--------|------|-------------|
| `POST` | `/auth/signup` | — | Créer un compte → retourne JWT |
| `POST` | `/auth/login` | — | Se connecter → retourne JWT |
| `GET` | `/auth/me` | ✅ | Utilisateur courant |
| `POST` | `/evaluate` | ✅ | Évaluation via formulaire JSON (legacy) |
| `POST` | `/evaluate/submit` | ✅ | Évaluation via fichiers (`multipart/form-data`) → `job_id` |
| `GET` | `/evaluate/{job_id}/stream` | ✅ | Flux SSE de progression du pipeline |
| `GET` | `/evaluations` | ✅ | Historique de l'utilisateur courant |
| `GET` | `/insights/feature-importance` | — | Importance des features du modèle |
| `GET` | `/results/summary` | — | Statistiques globales |

### POST `/evaluate/submit` — paramètres `multipart/form-data`

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `model_file` | fichier | Non | Modèle `.pkl` |
| `config_file` | fichier | Non | `config.json` HuggingFace |
| `dataset_file` | fichier | Non | Dataset `.csv` / `.parquet` / `.json` |
| `dataset_url` | string | Non | URL vers un CSV raw |
| `manual_params` | string (JSON) | Non | Hyperparamètres manuels (voir ci-dessous) |

`manual_params` accepte tous les champs de `EvaluateInput` :

```json
{
  "epochs": 50,
  "learning_rate": 0.0003,
  "batch_size": 64,
  "dropout": 0.1,
  "weight_decay": 0.0001,
  "data_augmentation": true,
  "train_accuracy": 0.95,
  "test_accuracy": 0.88,
  "depth": 12,
  "num_heads": 12,
  "embed_dim": 768
}
```

### GET `/evaluate/{job_id}/stream` — format SSE

```
data: {"step": "analyzer",  "status": "running", "message": "Analyse du modèle…"}
data: {"step": "analyzer",  "status": "done",    "message": "ViT · 86M params · 50k samples"}
data: {"step": "predictor", "status": "running", "message": "Prédiction MIA…"}
data: {"step": "predictor", "status": "done",    "message": "AUC : 0.672 — Risque Élevé"}
data: {"step": "reporter",  "status": "running", "message": "Génération du rapport…"}
data: {"step": "reporter",  "status": "done",    "message": "Rapport généré."}
data: {"step": "done",      "result": { "auc": 0.672, "risk_level": "Élevé", ... }}
```

---

## Variables d'environnement

Créez `backend/.env` :

```env
SECRET_KEY=change-me-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DATABASE_URL=sqlite:///./mia.db
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

---

## Structure

```
backend/
├── requirements.txt
├── artifacts/
│   └── predictor.pkl          ← modèle XGBoost (déposez-le ici)
└── app/
    ├── main.py                FastAPI app + CORS + migration SQLite
    ├── api/
    │   ├── auth.py
    │   ├── evaluations.py     submit, stream SSE, historique
    │   ├── insights.py
    │   └── results.py
    ├── core/
    │   ├── config.py          lecture des variables d'env
    │   ├── security.py        bcrypt + JWT + get_current_user
    │   └── jobs.py            asyncio.Queue par job (SSE registry)
    ├── db/
    │   ├── database.py        engine SQLAlchemy + get_db
    │   └── models.py          User · Evaluation · Report
    ├── schemas/               Pydantic v2
    └── pipeline/
        ├── agent_analyzer.py  extraction .pkl / config.json / dataset
        ├── predictor.py       charge predictor.pkl ou heuristique fallback
        ├── analyzer.py        features dérivées (gap, params_per_sample)
        ├── report_agent.py    recommandations + rapport texte
        └── features.py        build_X() · auc_to_risk() · FEATURE_COLUMNS
```

---

## Base de données

Trois tables SQLAlchemy (SQLite en dev, PostgreSQL en prod via `DATABASE_URL`) :

- **`users`** — `id`, `email` (unique), `hashed_password`, `created_at`
- **`evaluations`** — tous les champs de `EvaluateInput` + `auc`, `risk_level`, `recommendations` (JSON), `model_name`, `dataset_name`, `user_id` (FK), `created_at`
- **`reports`** — `id`, `evaluation_id` (FK), `content`, `created_at`

La migration des colonnes `model_name` / `dataset_name` sur une BDD existante est automatique au démarrage (via `ALTER TABLE … ADD COLUMN` silencieux).

---

## Ajouter le modèle XGBoost

```python
import joblib, xgboost as xgb

model = xgb.XGBRegressor(...)
model.fit(X_train, y_train)          # y = AUC d'attaque MIA

joblib.dump(model, "artifacts/predictor.pkl")
```

Redémarrez le backend — le modèle est chargé en mémoire au premier appel à `/evaluate`.  
Sans `predictor.pkl`, un **fallback heuristique** est utilisé automatiquement.
