# MIA Insight Guardian

Outil web d'estimation de la vulnérabilité d'un modèle de machine learning aux **attaques par inférence d'appartenance** (Membership Inference Attack — MIA), sans exécuter la moindre attaque réelle.

L'utilisateur dépose son modèle `.pkl` et son dataset ; un pipeline de quatre agents analyse, prédit via deux méta-modèles XGBoost, génère un rapport enrichi par LLM (Groq) et sauvegarde les résultats dans une base de données personnelle.

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
- [Méta-modèles XGBoost](#méta-modèles-xgboost)
- [Seuils de risque MIA](#seuils-de-risque-mia)

---

## Aperçu de l'architecture

```
┌─────────────────────────────────┐        ┌──────────────────────────────────┐
│  Frontend  (React 19 / Vite)    │        │  Backend  (FastAPI / Python)      │
│  http://localhost:5173          │◄──────►│  http://localhost:8000            │
│                                 │  REST  │                                  │
│  TanStack Router                │  +SSE  │  Auth JWT + bcrypt               │
│  TanStack Query                 │        │  Pipeline 4 agents               │
│  shadcn/ui + Tailwind           │        │  XGBoost Model A & B             │
└─────────────────────────────────┘        │  Rapport LLM (Groq)              │
                                           │  SQLAlchemy (SQLite / PostgreSQL) │
                                           └──────────────────────────────────┘
```

---

## Fonctionnalités

| Page | Description |
|------|-------------|
| **Accueil** | Niveaux de risque, méthodologie, 5 dernières évaluations de l'utilisateur |
| **Évaluation** | Upload `.pkl` + `config.json` (optionnel) + dataset (fichier ou URL) · saisie des hyperparamètres · progression en temps réel (SSE) · features extraites affichées par agent |
| **Historique** | Toutes les évaluations, dépliables, avec paramètres, rapport LLM et recommandations |
| **Model Insights** | Importance des features du méta-modèle XGBoost A (triée par score) |
| **Résultats** | Scatter gap/AUC + histogramme AUC — données personnelles de l'utilisateur |
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

# 5. Configurer les variables d'environnement (voir section dédiée)
# Créer backend/.env et y renseigner au minimum GROQ_API_KEY

# 6. Lancer le serveur avec hot-reload
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

### Backend — `backend/.env`

```env
# ── LLM (obligatoire pour les rapports enrichis) ──────────────────────────────
# Créez un compte gratuit sur https://console.groq.com et générez une clé API
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ── Sécurité ──────────────────────────────────────────────────────────────────
# Clé secrète JWT — changez obligatoirement en production (32 octets aléatoires)
SECRET_KEY=change-me-in-production-use-32-random-bytes

# Durée de vie du token en minutes (défaut : 1440 = 24h)
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ── Base de données ────────────────────────────────────────────────────────────
# SQLite (défaut dev)
DATABASE_URL=sqlite:///./mia.db
# PostgreSQL (prod)
# DATABASE_URL=postgresql://user:password@localhost:5432/mia_db

# ── CORS ──────────────────────────────────────────────────────────────────────
# Origines autorisées (séparées par des virgules)
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

> **Sans `GROQ_API_KEY`**, le rapport est généré par des règles locales (fallback automatique). Aucune erreur n'est levée.

---

## Structure du projet

```
mia-insight-guardian/
│
├── README.md
│
├── frontend/                        # Application React
│   ├── .env                         # VITE_API_URL=http://localhost:8000
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── api/
│       │   └── client.ts            # Client HTTP + mock backend + SSE streaming
│       ├── components/
│       │   ├── app-shell.tsx        # Layout principal
│       │   ├── app-sidebar.tsx      # Navigation latérale
│       │   └── risk-badge.tsx       # Badge niveau de risque
│       ├── lib/
│       │   └── auth-context.tsx     # Contexte d'authentification
│       └── routes/
│           ├── index.tsx            # Accueil + dernières évaluations
│           ├── evaluate.tsx         # Page d'évaluation (upload + SSE + features extraites)
│           ├── evaluations.tsx      # Historique des évaluations
│           ├── insights.tsx         # Importance des features XGBoost
│           ├── results.tsx          # Visualisations (scatter + histogramme)
│           ├── docs.tsx             # Documentation
│           ├── login.tsx            # Connexion
│           └── signup.tsx           # Inscription
│
└── backend/
    ├── requirements.txt
    ├── artifacts/                   # Méta-modèles XGBoost (format JSON natif)
    │   ├── model_A_regressor.json   # ← Modèle A : prédit l'AUC  (R²=0.98, 21 features)
    │   ├── model_A_classifier.json  # ← Modèle A : prédit le niveau de risque (F1=0.95)
    │   ├── model_B_regressor.json   # ← Modèle B : AUC sans accuracy (R²=0.98)
    │   └── model_B_classifier.json  # ← Modèle B : risque sans accuracy (F1=0.945)
    └── app/
        ├── main.py                  # FastAPI app + CORS + migrations légères
        ├── api/
        │   ├── auth.py              # POST /auth/signup|login  GET /auth/me
        │   ├── evaluations.py       # POST /evaluate  POST /evaluate/submit
        │   │                        # GET  /evaluate/{id}/stream  GET /evaluations
        │   ├── insights.py          # GET /insights/feature-importance
        │   └── results.py           # GET /results/summary  (filtré par utilisateur)
        ├── core/
        │   ├── config.py            # Variables d'environnement + limites upload
        │   ├── security.py          # bcrypt + JWT + get_current_user
        │   └── jobs.py              # Registry de jobs SSE (asyncio.Queue)
        ├── db/
        │   ├── database.py          # SQLAlchemy engine + SessionLocal
        │   └── models.py            # User, Evaluation (+ model_used), Report
        ├── schemas/
        │   ├── auth.py              # SignupRequest, AuthResponse, MeResponse
        │   ├── evaluation.py        # EvaluateInput, EvaluateResponse, EvaluationRecord
        │   ├── insights.py          # FeatureImportance
        │   └── results.py           # ResultsSummary
        └── pipeline/
            ├── agent_model.py       # Agent 1 — extrait features depuis .pkl et config.json
            ├── agent_dataset.py     # Agent 2 — analyse CSV/Parquet (variance, distance)
            ├── agent_analyzer.py    # Coordinateur legacy + coercition de types
            ├── analyzer.py          # Features dérivées (train_test_gap, params_per_sample)
            ├── predictor.py         # Sélection Modèle A/B + preprocessing + inférence XGBoost
            ├── report_agent.py      # Rapport LLM via Groq + fallback règles
            └── features.py          # FEATURE_COLUMNS (21 features Model A) + auc_to_risk()
```

---

## Pipeline multi-agents

```
[Fichier .pkl    ]
[config.json     ]  ──►  Agent Modèle      ──►  model_type, nb_params, depth…
[Dataset CSV     ]        (extraction auto)
[Params manuels  ]              │
                                ▼
                         Agent Dataset     ──►  nb_samples, nb_classes,
                         (si fourni)            intra_variance, inter_distance
                                │
                                ▼
                         Agent Prédicteur  ──►  AUC  +  risk_level  +  model_used
                         (XGBoost A ou B        (sélection automatique selon
                          ou heuristique)        disponibilité des données)
                                │
                                ▼
                         Agent Générateur  ──►  rapport LLM (Groq llama-3.3-70b)
                         (Groq + fallback)       + recommandations (règles)
                                │
                                ▼
                         Base de données   ──►  EvaluationRecord sauvegardé
```

Chaque transition pousse un événement **SSE** (`text/event-stream`) que le frontend consomme en temps réel. Les agents Modèle et Dataset incluent dans leur événement `done` le détail des features extraites, affichées dans un tableau sur la page d'évaluation.

### Paramètres extraits automatiquement

| Source | Paramètres extraits |
|--------|---------------------|
| `.pkl` sklearn/XGBoost | `model_type`, `nb_params`, `depth`, `learning_rate`, `epochs` |
| `config.json` HuggingFace | `depth`, `num_heads`, `embed_dim`, `mlp_ratio`, `patch_size`, `dropout`, `model_type`, `dataset_modality` |
| Dataset CSV/Parquet/JSON | `nb_train_samples`, `nb_classes`, `dataset_modality`, `dataset_intra_variance`, `dataset_inter_class_distance` |
| Saisie manuelle | `train_accuracy`, `test_accuracy`, `epochs`, `learning_rate`, `batch_size`, `dropout`, `weight_decay`, `data_augmentation` |

---

## Méta-modèles XGBoost

Deux paires de modèles sont disponibles dans `backend/artifacts/`. Le backend sélectionne automatiquement le plus précis selon les données disponibles.

| Modèle | Fichiers | Features | Condition d'utilisation | Performance |
|--------|----------|----------|------------------------|-------------|
| **A** | `model_A_regressor.json` + `model_A_classifier.json` | 21 (avec `train_accuracy`, `test_accuracy`, `train_test_gap`) | `train_accuracy` ET `test_accuracy` fournis | R²=0.98 / F1=0.95 |
| **B** | `model_B_regressor.json` + `model_B_classifier.json` | 18 (sans accuracy) | Hyperparamètres uniquement | R²=0.98 / F1=0.945 |
| **Heuristique** | — | — | Aucun fichier JSON présent | Approximation |

### Preprocessing appliqué avant inférence

| Transformation | Champs concernés |
|---------------|-----------------|
| `np.log1p` | `nb_params`, `nb_train_samples`, `nb_classes`, `params_per_sample` |
| LabelEncoder (alphabétique) | `model_type` (14 classes), `dataset_modality` (3 classes) |
| Cast en int | `data_augmentation` (0 ou 1) |
| Feature dérivée | `train_test_gap = max(0, train_acc − test_acc)` |

### Types de modèles reconnus

`AlexNet`, `CNN`, `DenseNet`, `EfficientNet`, `MLP`, `RNN`, `ResNet`, `Transformer`, `VGG`, `ViT`, `ViT-B`, `ViT-Small`, `ViT-Tiny`, `WideResNet`

---

## Seuils de risque MIA

| AUC prédite | Niveau de risque |
|-------------|-----------------|
| < 0.55 | **Faible** — peu de fuite d'appartenance |
| 0.55 – 0.65 | **Moyen** — défenses recommandées |
| ≥ 0.65 | **Élevé** — défenses urgentes (DP-SGD, distillation, MemGuard) |

Le niveau de risque est produit directement par le classificateur XGBoost (classes 0/1/2), indépendamment de l'AUC du régresseur, ce qui garantit la cohérence des deux sorties.
