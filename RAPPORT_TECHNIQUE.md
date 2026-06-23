# Rapport Technique — MIA Insight Gardien

---

## 1. Vue d'ensemble

**MIA Insight Gardien** est une application web qui estime la vulnérabilité d'un modèle de Machine Learning à une **Membership Inference Attack (MIA)** — une attaque qui tente de déterminer si un exemple donné a été utilisé dans le dataset d'entraînement du modèle.

L'outil ne lance aucune attaque réelle. Il prédit l'AUC d'attaque probable à partir des hyperparamètres et de la structure du modèle, en s'appuyant sur 4 **méta-modèles XGBoost** pré-entraînés sur des centaines de configurations réelles.

---

## 2. Architecture Générale

```
┌──────────────────────────────────┐        ┌─────────────────────────────────┐
│         FRONTEND (React)         │        │         BACKEND (FastAPI)        │
│                                  │        │                                  │
│  React 19 + Vite                 │◄──────►│  FastAPI + Uvicorn              │
│  TanStack Router / Query         │  HTTP  │  SQLAlchemy ORM                 │
│  shadcn/ui + Tailwind CSS        │  SSE   │  JWT Auth + bcrypt              │
│  Recharts (graphiques)           │        │  Pipeline 4 agents              │
└──────────────────────────────────┘        └────────────┬────────────────────┘
                                                         │
                                     ┌───────────────────┼───────────────────┐
                                     │                   │                   │
                               ┌─────▼─────┐     ┌──────▼──────┐   ┌───────▼──────┐
                               │  SQLite   │     │  XGBoost    │   │  Groq API    │
                               │  (dev)    │     │  artifacts/ │   │  llama-3.3   │
                               │  PostgreSQL│    │  (4 modèles)│   │  -70b        │
                               │  (prod)   │     └─────────────┘   └──────────────┘
                               └───────────┘
```

---

## 3. Backend

### 3.1 Frameworks & dépendances

| Bibliothèque | Version | Rôle |
|---|---|---|
| `fastapi` | ≥ 0.111 | Framework HTTP asynchrone |
| `uvicorn[standard]` | ≥ 0.29 | Serveur ASGI |
| `sqlalchemy` | ≥ 2.0 | ORM base de données |
| `pydantic` | ≥ 2.0 | Validation des schémas |
| `python-jose[cryptography]` | ≥ 3.3 | JWT tokens |
| `bcrypt` | ≥ 4.0 | Hachage des mots de passe |
| `xgboost` | ≥ 2.0 | Chargement et inférence des méta-modèles |
| `scikit-learn` | ≥ 1.4 | Utilitaires ML |
| `pandas` | ≥ 2.0 | Manipulation des données tabulaires |
| `numpy` | ≥ 1.26 | Calculs numériques |
| `joblib` | ≥ 1.3 | Chargement des fichiers `.pkl` |
| `groq` | ≥ 0.4 | API LLM Groq (llama-3.3-70b-versatile) |
| `python-multipart` | ≥ 0.0.9 | Upload de fichiers multipart |
| `python-dotenv` | ≥ 1.0 | Chargement des variables d'environnement |

---

### 3.2 Structure des fichiers backend

```
backend/
├── app/
│   ├── main.py                  # Point d'entrée FastAPI, CORS, migrations légères
│   ├── core/
│   │   ├── config.py            # Variables d'environnement (SECRET_KEY, DATABASE_URL…)
│   │   ├── security.py          # JWT, bcrypt, dépendance get_current_user
│   │   └── jobs.py              # Registre des jobs SSE (asyncio.Queue)
│   ├── db/
│   │   ├── database.py          # Engine SQLAlchemy, SessionLocal, get_db
│   │   └── models.py            # Tables ORM : User, Evaluation, Report
│   ├── api/
│   │   ├── auth.py              # /auth/signup, /auth/login, /auth/me
│   │   ├── evaluations.py       # /evaluate, /evaluate/submit, /evaluate/{id}/stream, /evaluations
│   │   ├── results.py           # /results/summary
│   │   └── insights.py          # /insights/feature-importance
│   ├── pipeline/
│   │   ├── agent_model.py       # Agent 1 — extraction features depuis .pkl
│   │   ├── agent_dataset.py     # Agent 2 — extraction features depuis CSV/Parquet/JSON
│   │   ├── agent_analyzer.py    # Coercion et validation des types
│   │   ├── analyzer.py          # Preprocessing final (enrichissement features)
│   │   ├── predictor.py         # Agent 3 — inférence XGBoost (4 modèles A/B)
│   │   ├── report_agent.py      # Agent 4 — rapport LLM (Groq) + fallback règles
│   │   └── features.py          # Constantes features, fonction auc_to_risk()
│   └── schemas/
│       ├── auth.py              # SignupRequest, LoginRequest, AuthResponse, MeResponse
│       ├── evaluation.py        # EvaluateInput, EvaluateResponse, EvaluationRecord
│       └── results.py           # ResultsSummary, GapAucPoint
└── artifacts/
    ├── model_A_regressor.json   # XGBoost — 21 features, prédit AUC  (R²=0.98)
    ├── model_A_classifier.json  # XGBoost — 21 features, prédit classe risque (F1=0.95)
    ├── model_B_regressor.json   # XGBoost — 18 features, prédit AUC  (R²=0.98)
    └── model_B_classifier.json  # XGBoost — 18 features, prédit classe risque (F1=0.945)
```

---

### 3.3 Base de données

**SQLite** en développement, **PostgreSQL** en production (via variable `DATABASE_URL`).

Les tables sont créées automatiquement au démarrage via `Base.metadata.create_all()`.  
Les colonnes ajoutées après coup sont migrées via des `ALTER TABLE` légers dans `main.py` (pas d'Alembic).

---

#### Table `users`

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | VARCHAR | PK, UUID | Identifiant unique |
| `email` | VARCHAR | UNIQUE, NOT NULL, INDEX | Adresse email |
| `hashed_password` | VARCHAR | NOT NULL | Mot de passe haché (bcrypt) |
| `created_at` | DATETIME | — | Date de création du compte |

---

#### Table `evaluations`

| Colonne | Type | Description |
|---|---|---|
| `id` | VARCHAR (UUID) | Clé primaire |
| `user_id` | VARCHAR (FK → users.id) | Propriétaire de l'évaluation |
| **Architecture** | | |
| `model_type` | VARCHAR | Ex : ResNet, ViT, CNN, MLP, Transformer… |
| `dataset_modality` | VARCHAR | image / tabular / text |
| `depth` | INTEGER | Profondeur du modèle (couches Conv2d, attention…) |
| `num_heads` | INTEGER | Nombre de têtes d'attention |
| `embed_dim` | INTEGER | Dimension de l'embedding |
| `mlp_ratio` | FLOAT | Ratio FFN / embed_dim |
| `nb_params` | INTEGER | Nombre total de paramètres |
| `patch_size` | INTEGER | Taille des patches (ViT uniquement) |
| **Entraînement** | | |
| `epochs` | INTEGER | Nombre d'epochs |
| `learning_rate` | FLOAT | Taux d'apprentissage |
| `batch_size` | INTEGER | Taille du batch |
| `dropout` | FLOAT | Taux de dropout |
| `weight_decay` | FLOAT | Régularisation L2 |
| `data_augmentation` | BOOLEAN | Augmentation de données activée |
| **Dataset** | | |
| `nb_train_samples` | INTEGER | Nombre d'exemples d'entraînement |
| `nb_classes` | INTEGER | Nombre de classes |
| `dataset_intra_variance` | FLOAT | Variance intra-classe normalisée [0,1] |
| `dataset_inter_class_distance` | FLOAT | Distance inter-centroïdes normalisée [0,1] |
| **Performance** | | |
| `train_accuracy` | FLOAT | Précision sur le dataset d'entraînement |
| `test_accuracy` | FLOAT | Précision sur le dataset de test |
| **Résultats** | | |
| `auc` | FLOAT | AUC MIA prédite (entre 0.5 et 0.99) |
| `risk_level` | VARCHAR | Faible / Moyen / Élevé |
| `recommendations` | TEXT | Tableau JSON de recommandations |
| `model_name` | VARCHAR | Nom du fichier modèle uploadé |
| `dataset_name` | VARCHAR | Nom du fichier dataset uploadé |
| `model_used` | VARCHAR | "A", "B" ou "heuristique" |
| `created_at` | DATETIME | Horodatage de l'évaluation |

---

#### Table `reports`

| Colonne | Type | Description |
|---|---|---|
| `id` | VARCHAR (UUID) | Clé primaire |
| `evaluation_id` | VARCHAR (FK → evaluations.id) | Évaluation associée |
| `content` | TEXT | Texte du rapport (généré par LLM ou par règles) |
| `created_at` | DATETIME | Horodatage |

---

### 3.4 Endpoints API

| Méthode | Route | Auth requise | Description |
|---|---|---|---|
| `POST` | `/auth/signup` | Non | Créer un compte (email + password) |
| `POST` | `/auth/login` | Non | Se connecter, retourne un token JWT |
| `GET` | `/auth/me` | Oui | Retourne l'email et l'id de l'utilisateur connecté |
| `POST` | `/evaluate` | Oui | Évaluation manuelle via JSON body |
| `POST` | `/evaluate/submit` | Oui | Soumission du pipeline avec upload de fichiers |
| `GET` | `/evaluate/{job_id}/stream` | Oui | Connexion SSE — événements temps réel du pipeline |
| `GET` | `/evaluations` | Oui | Historique des évaluations (filtré par utilisateur) |
| `GET` | `/results/summary` | Oui | Statistiques agrégées (scatter, histogramme) |
| `GET` | `/insights/feature-importance` | Oui | Importance des features du méta-modèle |
| `GET` | `/` | Non | Health check |

---

### 3.5 Pipeline — Les 4 agents

Le pipeline est exécuté en **tâche de fond** (`BackgroundTasks` FastAPI) et communique avec le frontend en temps réel via **Server-Sent Events (SSE)** grâce à une file `asyncio.Queue` par job.

```
Fichiers uploadés (.pkl + dataset optionnel)
              │
              ▼
┌─────────────────────────────────────────────────┐
│ AGENT 1 — agent_model.py                        │
│                                                  │
│  Détecte le framework ML depuis la hiérarchie   │
│  de classes Python (pas le nom du fichier) :    │
│    torch.* → PyTorch                            │
│    tensorflow.* / keras.* → Keras               │
│    xgboost.* → XGBoost                          │
│    sklearn.* → scikit-learn                     │
│                                                  │
│  Extrait depuis la structure des couches :      │
│    PyTorch : nb_params (exact), depth,          │
│              num_heads, embed_dim, dropout,      │
│              patch_size, mlp_ratio              │
│    Keras   : nb_params, depth, num_heads,       │
│              embed_dim, dropout                 │
│    XGBoost : learning_rate, depth, epochs,      │
│              weight_decay, nb_params            │
│    sklearn : epochs, depth, learning_rate,      │
│              weight_decay, nb_params            │
│                                                  │
│  Infère dataset_modality depuis le type modèle :│
│    ViT/CNN/ResNet/VGG → image                   │
│    Transformer/RNN    → text                    │
│    MLP/XGBoost        → tabular                 │
│                                                  │
│  → SSE event : running / done + extracted {}    │
└─────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│ AGENT 2 — agent_dataset.py (optionnel)          │
│                                                  │
│  Charge : CSV / Parquet / JSON (fichier ou URL) │
│  Détecte la colonne label automatiquement        │
│    (cherche : label, target, class, y, output…) │
│                                                  │
│  Calcule :                                       │
│    nb_train_samples  : nombre de lignes          │
│    nb_classes        : cardinalité du label      │
│    dataset_intra_variance :                      │
│      variance moyenne par classe normalisée [0,1]│
│    dataset_inter_class_distance :                │
│      distance inter-centroïdes normalisée [0,1]  │
│                                                  │
│  → SSE event : running / done + extracted {}    │
└─────────────────────────────────────────────────┘
              │
              ▼  Merge : DEFAULTS ← model_features ← dataset_features ← manual_params
              │
┌─────────────────────────────────────────────────┐
│ AGENT 3 — predictor.py                          │
│                                                  │
│  Preprocessing :                                 │
│    log1p(nb_params, nb_train_samples,            │
│           nb_classes, params_per_sample)         │
│    LabelEncoder hardcodé (alphabétique) :        │
│      14 classes model_type                       │
│      3 classes dataset_modality                  │
│    data_augmentation → int (0/1)                 │
│    train_test_gap = max(0, train_acc - test_acc) │
│                                                  │
│  Sélection du modèle :                           │
│    Modèle A (21 features) si train_accuracy      │
│              ET test_accuracy disponibles        │
│    Modèle B (18 features) sinon                  │
│    Heuristique si aucun fichier .json trouvé     │
│                                                  │
│  Inférence :                                     │
│    Regressor → AUC prédit [0.5, 0.99]           │
│    Classifier → classe risque (0/1/2)            │
│                                                  │
│  → SSE event : running / done (AUC + risque)    │
└─────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│ AGENT 4 — report_agent.py                       │
│                                                  │
│  generate_report() :                             │
│    Si GROQ_API_KEY défini :                      │
│      Appel API Groq — llama-3.3-70b-versatile   │
│      Prompt en français avec tous les paramètres │
│      Rapport prose 4–6 phrases (max_tokens=400)  │
│      Fallback automatique si erreur API          │
│    Sinon :                                       │
│      Rapport basé sur des règles statiques       │
│                                                  │
│  generate_recommendations() :                    │
│    Toujours basé sur des règles (déterministe)   │
│    Analyse gap, dropout, weight_decay,           │
│    data_augmentation, nb_samples, intra_variance │
│                                                  │
│  → SSE event : running / done                   │
└─────────────────────────────────────────────────┘
              │
              ▼
  Sauvegarde en base : table evaluations + table reports
              │
              ▼
  SSE finish event → résultat final au frontend
```

---

### 3.6 Méta-modèles XGBoost

Quatre modèles pré-entraînés stockés dans `backend/artifacts/` au format JSON XGBoost :

| Fichier | Features | Sortie | Performance |
|---|---|---|---|
| `model_A_regressor.json` | 21 (avec précisions) | AUC continue | R² = 0.98 |
| `model_A_classifier.json` | 21 (avec précisions) | Classe risque (0/1/2) | F1 = 0.95 |
| `model_B_regressor.json` | 18 (sans précisions) | AUC continue | R² = 0.98 |
| `model_B_classifier.json` | 18 (sans précisions) | Classe risque (0/1/2) | F1 = 0.945 |

**Features du Modèle A (21) :**
`model_type_enc, nb_params_log, depth, embed_dim, mlp_ratio, patch_size, dropout,
dataset_modality_enc, nb_train_samples_log, nb_classes_log, data_augmentation,
epochs, learning_rate, batch_size, weight_decay,
train_accuracy, test_accuracy, train_test_gap,
params_per_sample_log, dataset_intra_variance, dataset_inter_class_distance`

**Features du Modèle B (18) :** identiques sans `train_accuracy`, `test_accuracy`, `train_test_gap`.

---

### 3.7 Authentification & Sécurité

- **JWT HS256** — token signé avec `SECRET_KEY`, expiration 24h
- **bcrypt** — hachage des mots de passe (coût adaptatif)
- Toutes les routes protégées utilisent `Depends(get_current_user)`
- Les évaluations sont filtrées par `user_id` — aucun accès croisé entre utilisateurs
- **CORS** configuré explicitement (pas de wildcard `*`)
- Taille max des uploads : 200 Mo (modèle), 100 Mo (dataset)

---

## 4. Frontend

### 4.1 Frameworks & dépendances

| Bibliothèque | Rôle |
|---|---|
| React 19 | Interface utilisateur |
| Vite | Bundler, serveur de développement |
| TanStack Router v2 | Routing file-based (routes définies dans `src/routes/`) |
| TanStack Query v5 | Fetching HTTP, cache, gestion de l'état serveur |
| shadcn/ui | Composants UI (Card, Badge, Button, Dialog…) |
| Tailwind CSS v4 | Styles utilitaires |
| Recharts | Graphiques interactifs (scatter plot, bar chart) |
| Lucide React | Bibliothèque d'icônes |
| Sonner | Notifications toast |

---

### 4.2 Structure des fichiers frontend

```
frontend/src/
├── api/
│   └── client.ts              # Toutes les fonctions API + mock backend complet
├── components/
│   ├── app-shell.tsx           # Layout principal (sidebar + contenu)
│   ├── app-sidebar.tsx         # Navigation latérale avec routes
│   ├── risk-badge.tsx          # Badge coloré Faible / Moyen / Élevé
│   └── ui/                     # Composants shadcn générés
├── lib/
│   ├── auth-context.tsx        # Contexte React : user, login(), logout()
│   └── lovable-error-reporting.ts
├── routes/
│   ├── __root.tsx              # Racine : meta HTML, providers, error boundary
│   ├── index.tsx               # Page d'accueil
│   ├── login.tsx               # Connexion
│   ├── signup.tsx              # Inscription
│   ├── evaluate.tsx            # Pipeline d'évaluation + SSE
│   ├── evaluations.tsx         # Historique des évaluations
│   ├── results.tsx             # Graphiques statistiques
│   ├── insights.tsx            # Feature importance (non affiché dans le menu)
│   └── docs.tsx                # Documentation utilisateur
└── styles.css                  # Variables CSS globales (couleurs risque, thème)
```

---

### 4.3 Pages & fonctionnalités

#### Accueil (`/`)
- Présentation des 3 niveaux de risque (Faible / Moyen / Élevé) avec seuils AUC
- Explication de la méthode (méta-modèle, sans exécuter d'attaque)
- Affichage des 5 dernières évaluations de l'utilisateur
- Bouton d'accès rapide vers l'évaluation

#### Connexion & Inscription (`/login`, `/signup`)
- Formulaires email + mot de passe
- Redirection automatique après authentification
- Gestion des erreurs (email déjà utilisé, identifiants invalides)

#### Évaluation (`/evaluate`)
Fonctionnement en deux temps :

**1. Formulaire de soumission :**
- Upload fichier `.pkl` (modèle PyTorch, Keras, XGBoost, sklearn)
- Upload optionnel dataset CSV / Parquet / JSON (ou URL)
- Upload optionnel `config.json` HuggingFace
- Saisie manuelle des paramètres non extractables (learning_rate, epochs, batch_size, train/test accuracy, data_augmentation…)

**2. Progression en temps réel (SSE) :**
- Affichage des 4 étapes avec indicateur running / done / error
- Tableau des features extraites sous chaque étape terminée (labels en français)
- Affichage final : AUC, badge risque, rapport prose, recommandations, badge Modèle A/B/heuristique

#### Historique (`/evaluations`)
- Liste de toutes les évaluations de l'utilisateur, triées par date
- Chaque entrée est dépliable et affiche :
  - Rapport textuel
  - Liste des recommandations
  - Tableau de tous les paramètres utilisés
- Affichage du nom du modèle, du dataset, de la date et du niveau de risque

#### Résultats (`/results`)
- **Scatter plot** : gap train/test en abscisse, AUC prédite en ordonnée, coloré par modalité (image / tabular / text)
- **Histogramme** : distribution des AUC sur toutes les évaluations de l'utilisateur, coloré selon le niveau de risque

---

### 4.4 Client API (`client.ts`)

Toutes les communications avec le backend passent par un seul fichier.

**Interfaces principales :**

```typescript
EvaluateInput        // 21 champs (params modèle + dataset + performance)
EvaluateResponse     // auc, risk_level, recommendations, report, model_used
EvaluationRecord     // EvaluateResponse + id, created_at, input
JobEvent             // step, status, message, result?, extracted?
```

**Mock backend intégré :**  
Si `VITE_API_URL` n'est pas défini, toutes les fonctions API utilisent `localStorage` comme base de données et simulent le pipeline avec des délais réalistes. Permet de tester l'UI sans backend.

---

### 4.5 Navigation (sidebar)

| Icône | Label | Route |
|---|---|---|
| Home | Accueil | `/` |
| FlaskConical | Évaluation | `/evaluate` |
| History | Historique | `/evaluations` |
| LineChart | Résultats | `/results` |
| BookOpen | Documentation | `/docs` |

---

## 5. Configuration

### Variables d'environnement backend (`backend/.env`)

| Variable | Valeur par défaut | Description |
|---|---|---|
| `SECRET_KEY` | `"change-me-in-production"` | Clé de signature JWT — **à changer en prod** |
| `DATABASE_URL` | `sqlite:///./mia.db` | URL de connexion base de données |
| `GROQ_API_KEY` | `""` | Clé API Groq pour la génération LLM du rapport |
| `CORS_ORIGINS` | `localhost:5173,3000,4173,8081` | Origines CORS autorisées (séparées par virgule) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` (24h) | Durée de vie du token JWT |

### Variables d'environnement frontend (`frontend/.env`)

| Variable | Description |
|---|---|
| `VITE_API_URL` | URL complète du backend (ex : `http://localhost:8000`) |

---

## 6. Lancer l'application

```bash
# ── Backend ──────────────────────────────────────
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows
# source .venv/bin/activate     # Linux / Mac

pip install -r requirements.txt

# Créer le fichier .env
echo SECRET_KEY=ma-cle-secrete          > .env
echo DATABASE_URL=sqlite:///./mia.db   >> .env
echo GROQ_API_KEY=gsk_xxxxxxxxxxxxx    >> .env

uvicorn app.main:app --reload --port 8000


# ── Frontend ─────────────────────────────────────
cd frontend
npm install --legacy-peer-deps

# Créer le fichier .env
echo VITE_API_URL=http://localhost:8000 > .env

npm run dev
```

L'application est accessible sur `http://localhost:5173` (ou le port affiché par Vite).

---

## 7. Flux complet d'une évaluation

```
1. L'utilisateur se connecte → token JWT stocké dans localStorage

2. Upload model.pkl + (optionnel) dataset.csv + paramètres manuels
   POST /evaluate/submit (multipart/form-data, Authorization: Bearer <token>)
   ├── Vérification taille fichiers (max 200 Mo modèle, 100 Mo dataset)
   ├── Création d'un Job (asyncio.Queue)
   ├── Lancement de _run_pipeline() en BackgroundTask
   └── Retourne { job_id }

3. Connexion SSE
   GET /evaluate/{job_id}/stream
   Le frontend reçoit les événements en temps réel :

   ┌─ agent_model  : running → done (+ extracted : params extraits du .pkl)
   ├─ agent_dataset: running → done (+ extracted : stats dataset)          ← si dataset fourni
   ├─ predictor    : running → done (AUC + niveau risque + modèle utilisé)
   ├─ reporter     : running → done
   └─ finish       : { auc, risk_level, recommendations, report, model_used }

4. Sauvegarde en base de données
   ├── Table evaluations (tous les paramètres + résultats)
   └── Table reports (texte du rapport)

5. Frontend affiche le résultat final :
   ├── Score AUC (ex : 0.742)
   ├── Badge risque (Élevé)
   ├── Badge modèle utilisé (A / B / heuristique)
   ├── Rapport en prose (généré par Groq LLM ou règles)
   └── Liste de recommandations
```

---

## 8. Limitations connues

| Limitation | Explication |
|---|---|
| Paramètres d'entraînement non extractables | `learning_rate`, `epochs`, `batch_size`, `weight_decay`, `data_augmentation`, `train_accuracy`, `test_accuracy` ne sont pas stockés dans un fichier `.pkl` après entraînement — saisie manuelle obligatoire (exception : XGBoost et sklearn les conservent dans l'objet) |
| Modèles PyTorch sans `torch` installé | Si `torch` n'est pas dans l'environnement Python du backend, seul `nb_params` peut être extrait par duck-typing |
| Support HuggingFace via `config.json` | Les modèles HuggingFace peuvent fournir un `config.json` pour une extraction complète (depth, num_heads, embed_dim, dropout, patch_size) |
| SQLite en développement | SQLite ne supporte pas la concurrence en écriture — utiliser PostgreSQL en production |
| Token SSE non persisté | Si l'utilisateur recharge la page pendant le pipeline, les événements SSE passés sont perdus |

---

*Document généré le 19 juin 2026*
