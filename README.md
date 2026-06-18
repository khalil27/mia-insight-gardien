# MIA Insight Guardian

Outil web d'estimation de la vulnérabilité d'un modèle Transformer aux **attaques par inférence d'appartenance** (Membership Inference Attack — MIA), sans exécuter la moindre attaque réelle.

L'utilisateur dépose son modèle `.pkl` et son dataset, un pipeline de trois agents analyse, prédit et génère un rapport, et les résultats sont sauvegardés dans une base de données personnelle.

---

## Table des matières

- [Aperçu de l'architecture](#aperçu-de-larchitecture)
- [Fonctionnalités](#fonctionnalités)
- [Prérequis](#prérequis)
- [Installation et lancement](#installation-et-lancement)
  - [Backend (FastAPI)](#backend-fastapi)
  - [Frontend (React + Vite)](#frontend-react--vite)
- [Variables d'environnement](#variables-denvironnement)
- [Structure du projet](#structure-du-projet)
- [Pipeline multi-agents](#pipeline-multi-agents)
- [Seuils de risque MIA](#seuils-de-risque-mia)
- [Ajouter un vrai modèle XGBoost](#ajouter-un-vrai-modèle-xgboost)

---

## Aperçu de l'architecture

```
┌─────────────────────────────────┐        ┌──────────────────────────────┐
│  Frontend  (React 19 / Vite)    │        │  Backend  (FastAPI / Python)  │
│  http://localhost:5173          │◄──────►│  http://localhost:8000        │
│                                 │  REST  │                               │
│  TanStack Router                │  +SSE  │  Auth JWT + bcrypt            │
│  TanStack Query                 │        │  Pipeline multi-agents        │
│  shadcn/ui + Tailwind           │        │  SQLAlchemy (SQLite / PG)     │
└─────────────────────────────────┘        └──────────────────────────────┘
```

---

## Fonctionnalités

| Page | Description |
|------|-------------|
| **Accueil** | Niveaux de risque, méthodologie, 5 dernières évaluations de l'utilisateur |
| **Évaluation** | Upload `.pkl` + `config.json` (optionnel) + dataset (fichier ou URL) · saisie des hyperparamètres · progression en temps réel des agents (SSE) |
| **Historique** | Toutes les évaluations, dépliables, avec paramètres, rapport et recommandations |
| **Model Insights** | Importance des features du méta-modèle XGBoost |
| **Résultats** | Scatter gap/AUC + histogramme AUC sur le jeu expérimental |
| **Documentation** | Interprétation du score, types d'attaque, défenses |

---

## Prérequis

| Outil | Version minimale |
|-------|-----------------|
| Python | 3.10+ |
| Node.js | 18+ |
| npm | 9+ (ou Bun si installé) |

---

## Installation et lancement

### Backend (FastAPI)

```bash
# 1. Se placer dans le dossier backend
cd backend

# 2. Créer l'environnement virtuel (une seule fois)
python -m venv .venv

# 3. Activer l'environnement virtuel
#    Windows PowerShell :
.venv\Scripts\activate
#    Linux / macOS :
# source .venv/bin/activate

# 4. Installer les dépendances (une seule fois)
pip install -r requirements.txt

# 5. Lancer le serveur avec hot-reload
uvicorn app.main:app --reload --port 8000
```

Le backend démarre sur **http://localhost:8000**  
Documentation Swagger interactive : **http://localhost:8000/docs**

---

### Frontend (React + Vite)

```bash
# 1. Se placer dans le dossier frontend
cd frontend

# 2. Installer les dépendances (une seule fois)
npm install --legacy-peer-deps

# 3. Lancer le serveur de développement
npm run dev
```

Le frontend démarre sur **http://localhost:5173**

> **Note :** Si Bun est installé, remplacez `npm install --legacy-peer-deps` par `bun install` et `npm run dev` par `bun run dev`.

---

## Variables d'environnement

### Frontend — `frontend/.env`

```env
VITE_API_URL=http://localhost:8000
```

Sans cette variable, le frontend bascule en **mode mock** (données locales, aucun backend requis).

### Backend — variables optionnelles

Créez un fichier `backend/.env` pour surcharger les valeurs par défaut :

```env
# Clé secrète JWT — changez obligatoirement en production
SECRET_KEY=change-me-in-production-use-32-random-bytes

# Durée de vie du token en minutes (défaut : 1440 = 24h)
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Base de données
# SQLite (défaut dev)
DATABASE_URL=sqlite:///./mia.db
# PostgreSQL (prod)
# DATABASE_URL=postgresql://user:password@localhost:5432/mia_db

# Origines CORS autorisées (séparées par des virgules)
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

---

## Structure du projet

```
mia-insight-guardian/
│
├── README.md
│
├── frontend/                     # Application React
│   ├── .env                      # VITE_API_URL=http://localhost:8000
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── src/                      # Sources React
│       ├── api/
│       │   └── client.ts         # Client HTTP + mock backend + SSE streaming
│       ├── components/
│       │   ├── app-shell.tsx     # Layout principal
│       │   ├── app-sidebar.tsx   # Navigation latérale
│       │   └── risk-badge.tsx    # Badge niveau de risque
│       ├── lib/
│       │   └── auth-context.tsx  # Contexte d'authentification
│       └── routes/
│           ├── index.tsx         # Accueil + dernières évaluations
│           ├── evaluate.tsx      # Page d'évaluation (upload + SSE)
│           ├── evaluations.tsx   # Historique des évaluations
│           ├── insights.tsx      # Importance des features
│           ├── results.tsx       # Visualisations expérimentales
│           ├── docs.tsx          # Documentation
│           ├── login.tsx         # Connexion
│           └── signup.tsx        # Inscription
│
└── backend/
    ├── requirements.txt
    ├── artifacts/
    │   └── predictor.pkl         # ← déposez ici le modèle XGBoost entraîné
    └── app/
        ├── main.py               # FastAPI app + CORS + migration légère
        ├── api/
        │   ├── auth.py           # POST /auth/signup|login  GET /auth/me
        │   ├── evaluations.py    # POST /evaluate  POST /evaluate/submit
        │   │                     # GET  /evaluate/{id}/stream  GET /evaluations
        │   ├── insights.py       # GET /insights/feature-importance
        │   └── results.py        # GET /results/summary
        ├── core/
        │   ├── config.py         # Variables d'environnement
        │   ├── security.py       # bcrypt + JWT + get_current_user
        │   └── jobs.py           # Registry de jobs SSE (asyncio.Queue)
        ├── db/
        │   ├── database.py       # SQLAlchemy engine + SessionLocal
        │   └── models.py         # User, Evaluation, Report
        ├── schemas/
        │   ├── auth.py           # SignupRequest, AuthResponse, MeResponse
        │   ├── evaluation.py     # EvaluateInput, EvaluateResponse, EvaluationRecord
        │   ├── insights.py       # FeatureImportance
        │   └── results.py        # ResultsSummary
        └── pipeline/
            ├── agent_analyzer.py # Extraction depuis .pkl, config.json, dataset
            ├── predictor.py      # XGBoost (ou fallback heuristique)
            ├── analyzer.py       # Features dérivées (train_test_gap, params_per_sample)
            ├── report_agent.py   # Recommandations + rapport texte
            └── features.py       # build_X(), auc_to_risk(), FEATURE_COLUMNS
```

---

## Pipeline multi-agents

```
[Fichier .pkl   ]
[config.json    ]  ──►  Agent Analyseur   ──►  features dict complet
[Dataset .csv   ]        (extraction auto)
[Params manuels ]              │
                               ▼
                        Agent Prédicteur  ──►  AUC  +  risk_level
                        (XGBoost / fallback)
                               │
                               ▼
                        Agent Générateur  ──►  rapport  +  recommandations
                        (règles → LLM plus tard)
                               │
                               ▼
                        Base de données   ──►  EvaluationRecord sauvegardé
```

Chaque transition pousse un événement **SSE** (`text/event-stream`) que le frontend consomme via `fetch + ReadableStream` pour afficher la progression en temps réel.

### Paramètres extraits automatiquement

| Source | Paramètres |
|--------|-----------|
| `.pkl` sklearn/XGBoost | `model_type`, `nb_params` |
| `config.json` HuggingFace | `depth`, `num_heads`, `embed_dim`, `mlp_ratio`, `patch_size`, `dropout`, `model_type`, `dataset_modality` |
| Dataset CSV/Parquet | `nb_train_samples`, `nb_classes`, `class_balance`, `dataset_modality` |
| Saisie manuelle | `epochs`, `learning_rate`, `batch_size`, `dropout`, `weight_decay`, `data_augmentation`, `train_accuracy`, `test_accuracy` |

---

## Seuils de risque MIA

| AUC prédite | Niveau de risque |
|-------------|-----------------|
| < 0.55 | 🟢 **Faible** — peu de fuite d'appartenance |
| 0.55 – 0.65 | 🟡 **Moyen** — défenses recommandées |
| ≥ 0.65 | 🔴 **Élevé** — défenses urgentes (DP-SGD, distillation, MemGuard) |

---

## Ajouter un vrai modèle XGBoost

1. Entraînez un régresseur XGBoost sur vos runs MIA réels (target = AUC d'attaque).
2. Sérialisez-le avec joblib :
   ```python
   import joblib
   joblib.dump(model, "backend/artifacts/predictor.pkl")
   ```
3. Redémarrez le backend — `predictor.pkl` est chargé au premier appel, sans aucune modification de code.

En l'absence du fichier, le backend utilise automatiquement une **heuristique de fallback** basée sur le gap train/test et les régularisations.
