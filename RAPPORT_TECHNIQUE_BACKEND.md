# Rapport Technique — Backend
## MIA Insight Gardien

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Stack technique](#2-stack-technique)
3. [Structure des fichiers](#3-structure-des-fichiers)
4. [Point d'entrée — `main.py`](#4-point-dentrée--mainpy)
5. [Configuration — `core/config.py`](#5-configuration--coreconfigpy)
6. [Sécurité & Auth — `core/security.py`](#6-sécurité--auth--coresecuritypy)
7. [Système de jobs SSE — `core/jobs.py`](#7-système-de-jobs-sse--corejobspy)
8. [Base de données — `db/`](#8-base-de-données--db)
9. [Schémas Pydantic — `schemas/`](#9-schémas-pydantic--schemas)
10. [Routes API — `api/`](#10-routes-api--api)
11. [Pipeline de traitement — `pipeline/`](#11-pipeline-de-traitement--pipeline)
12. [Module RAG — `rag/`](#12-module-rag--rag)
13. [Tableau récapitulatif des endpoints](#13-tableau-récapitulatif-des-endpoints)
14. [Flux complet d'une évaluation](#14-flux-complet-dune-évaluation)

---

## 1. Vue d'ensemble

Le backend est une API REST + SSE construite avec **FastAPI**. Son rôle est d'estimer la vulnérabilité d'un modèle de Machine Learning aux attaques par **Membership Inference Attack (MIA)** sans jamais exécuter l'attaque réelle.

L'estimation repose sur 4 meta-modèles **XGBoost** (pré-entraînés hors-ligne) qui prédisent une AUC d'attaque à partir des hyperparamètres du modèle analysé.

La pipeline est asynchrone : le frontend envoie les fichiers, reçoit un `job_id`, puis écoute un flux SSE pour suivre la progression en temps réel.

---

## 2. Stack technique

| Composant | Technologie | Version |
|---|---|---|
| Framework web | FastAPI | ≥ 0.111 |
| Serveur ASGI | Uvicorn | ≥ 0.29 |
| ORM | SQLAlchemy | ≥ 2.0 |
| Validation | Pydantic | ≥ 2.0 |
| Auth JWT | python-jose | ≥ 3.3 |
| Hashage mot de passe | bcrypt | ≥ 4.0 |
| Meta-modèles prédiction | XGBoost | ≥ 2.0 |
| Preprocessing | scikit-learn / pandas / numpy | ≥ 1.4 / 2.0 / 1.26 |
| Désérialisation modèles | joblib | ≥ 1.3 |
| Génération rapports LLM | Groq API (`llama-3.3-70b-versatile`) | ≥ 0.4 |
| Base vectorielle RAG | ChromaDB | ≥ 0.5 |
| Embeddings RAG | ONNX Runtime (DefaultEmbeddingFunction) | ≥ 1.17 |
| Upload fichiers | python-multipart | ≥ 0.0.9 |
| Base de données | SQLite (dev) / PostgreSQL (prod) | — |
| Variables d'env | python-dotenv | ≥ 1.0 |

---

## 3. Structure des fichiers

```
backend/
├── app/
│   ├── main.py                    ← Démarrage FastAPI, migrations, middlewares
│   ├── core/
│   │   ├── config.py              ← Variables d'environnement
│   │   ├── security.py            ← JWT, bcrypt, dépendance auth
│   │   └── jobs.py                ← Système de jobs pour SSE
│   ├── db/
│   │   ├── database.py            ← Connexion SQLAlchemy
│   │   └── models.py              ← Modèles ORM (tables SQL)
│   ├── schemas/
│   │   ├── auth.py                ← Schémas Pydantic auth
│   │   ├── evaluation.py          ← Schémas évaluation
│   │   ├── insights.py            ← Schéma feature importance
│   │   └── results.py             ← Schémas résultats / stats
│   ├── api/
│   │   ├── auth.py                ← Endpoints /auth/*
│   │   ├── evaluations.py         ← Endpoints /evaluate/* et /evaluations
│   │   ├── insights.py            ← Endpoint /insights/feature-importance
│   │   └── results.py             ← Endpoint /results/summary
│   ├── pipeline/
│   │   ├── features.py            ← Liste FEATURE_COLUMNS + auc_to_risk()
│   │   ├── analyzer.py            ← Calcul features dérivées (gap, params_per_sample)
│   │   ├── agent_analyzer.py      ← Coordinateur legacy (endpoint /evaluate)
│   │   ├── agent_model.py         ← Agent : analyse fichier .pkl
│   │   ├── agent_dataset.py       ← Agent : analyse fichier dataset
│   │   ├── predictor.py           ← Chargement XGBoost + prédiction AUC
│   │   └── report_agent.py        ← Génération rapport + recommandations (Groq + fallback règles)
│   └── rag/
│       ├── __init__.py            ← (vide)
│       ├── store.py               ← Accès ChromaDB (singleton lazy)
│       └── retriever.py           ← Construction requête + recherche sémantique
└── artifacts/
    ├── model_A_regressor.json     ← XGBoost régresseur 21 features
    ├── model_A_classifier.json    ← XGBoost classifieur 21 features
    ├── model_B_regressor.json     ← XGBoost régresseur 18 features (sans accuracy)
    └── model_B_classifier.json    ← XGBoost classifieur 18 features
```

---

## 4. Point d'entrée — `main.py`

`main.py` est le fichier chargé par Uvicorn. Il s'exécute une seule fois au démarrage.

### Actions au démarrage (dans l'ordre)

**1. Configuration du logger**
Crée un handler sur le logger `app.*` avec un format `LEVEL  name - message`. Ce handler est indépendant de celui d'Uvicorn pour garantir la visibilité des logs applicatifs.

**2. Création des tables SQL**
```python
models.Base.metadata.create_all(bind=engine)
```
Crée toutes les tables (users, evaluations, reports) si elles n'existent pas encore. Opération idempotente.

**3. Migration légère sans Alembic**
```python
for _col in ("model_name VARCHAR", "dataset_name VARCHAR", ...):
    _conn.execute(text(f"ALTER TABLE evaluations ADD COLUMN {_col}"))
```
Ajoute les nouvelles colonnes à une base existante. Chaque `ALTER TABLE` est dans un `try/except` — si la colonne existe déjà, l'erreur est silencieuse.

**4. Création de l'application FastAPI**
Titre, description, version définis ici.

**5. Middleware CORS**
Autorise les origines listées dans `CORS_ORIGINS` (variable d'env ou défaut : localhost 5173/3000/4173/8081).

**6. Handler d'erreur HTTP personnalisé**
Remplace la réponse JSON par défaut (`{"detail":"..."}`) par du texte brut. Ainsi le frontend peut afficher directement `err.message`.

**7. Inclusion des 4 routers**
```python
app.include_router(auth.router)        # préfixe /auth
app.include_router(evaluations.router) # pas de préfixe
app.include_router(insights.router)    # préfixe /insights
app.include_router(results.router)     # préfixe /results
```

**8. Health check**
```python
GET / → {"status": "ok"}
```

---

## 5. Configuration — `core/config.py`

Charge `.env` avec `load_dotenv()` puis expose des constantes globales.

| Constante | Variable d'env | Défaut |
|---|---|---|
| `SECRET_KEY` | `SECRET_KEY` | `"change-me-in-production..."` |
| `ALGORITHM` | — | `"HS256"` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` (24h) |
| `DATABASE_URL` | `DATABASE_URL` | `"sqlite:///./mia.db"` |
| `GROQ_API_KEY` | `GROQ_API_KEY` | `""` (vide = pas de LLM) |
| `CORS_ORIGINS` | `CORS_ORIGINS` | `"http://localhost:5173,..."` |
| `MAX_MODEL_SIZE` | — | `200 * 1024 * 1024` (200 Mo) |
| `MAX_DATASET_SIZE` | — | `100 * 1024 * 1024` (100 Mo) |

Si `GROQ_API_KEY` est vide, le système de rapport tombe en mode fallback par règles (aucune dépendance externe).

---

## 6. Sécurité & Auth — `core/security.py`

### `hash_password(password: str) → str`
Hashe le mot de passe avec `bcrypt.hashpw()`. bcrypt génère automatiquement un sel aléatoire. Le résultat est une chaîne encodée en UTF-8.

### `verify_password(plain: str, hashed: str) → bool`
Compare un mot de passe en clair avec son hash bcrypt. Utilise `bcrypt.checkpw()` qui est résistant aux attaques temporelles.

### `create_access_token(data: dict) → str`
Crée un JWT signé avec `SECRET_KEY` via l'algorithme `HS256`. Le payload contient :
- `sub` : UUID de l'utilisateur
- `email` : email de l'utilisateur
- `exp` : timestamp d'expiration (now + 24h)

### `get_current_user(credentials, db) → models.User`
Dépendance FastAPI utilisée avec `Depends(get_current_user)` sur toutes les routes protégées.
1. Extrait le token Bearer du header `Authorization`
2. Décode le JWT avec `jose.jwt.decode()`
3. Extrait `sub` (user ID) du payload
4. Récupère l'utilisateur depuis la base
5. Lance `HTTPException 401` à chaque étape en cas d'échec

---

## 7. Système de jobs SSE — `core/jobs.py`

Le système de jobs permet d'envoyer des événements temps réel (Server-Sent Events) au frontend pendant l'exécution de la pipeline en arrière-plan.

### Classe `Job`

```
Job
├── id         : str (UUID)
├── queue      : asyncio.Queue
└── done       : bool
```

**`push(event: dict)`**
Enfile un événement dans la queue. Structure typique :
```json
{"step": "agent_model", "status": "running", "message": "Analyse du fichier modèle…"}
```

**`finish(result: dict)`**
Enfile l'événement final puis le sentinel `None` :
```json
{"step": "done", "result": {"auc": 0.712, "risk_level": "Élevé", ...}}
```
puis `None` pour signaler la fin du stream.

**`fail(message: str)`**
Enfile un événement d'erreur puis `None` :
```json
{"step": "error", "message": "Agent Modèle : ..."}
```

**`event_stream()`**
Générateur async qui défile la queue avec `asyncio.wait_for(timeout=60)`. Si 60 secondes s'écoulent sans événement, il envoie `{"step": "ping"}` pour maintenir la connexion SSE vivante. S'arrête quand `None` est reçu.

### Registre global

```python
_registry: Dict[str, Job] = {}
```

Dictionnaire en mémoire. Un job survive tant que le processus tourne. En cas de redémarrage du serveur, les jobs en cours sont perdus.

**`create_job()`** — crée un Job avec UUID, l'enregistre, retourne le Job.

**`get_job(job_id)`** — retourne le Job ou `None`.

---

## 8. Base de données — `db/`

### `database.py`

**`engine`**
Créé avec `create_engine(DATABASE_URL)`. Pour SQLite : `connect_args={"check_same_thread": False}` pour permettre les accès depuis plusieurs threads (FastAPI + BackgroundTasks).

**`SessionLocal`**
Factory de sessions : `autocommit=False`, `autoflush=False`. Chaque requête HTTP ouvre sa propre session.

**`Base`**
Classe `DeclarativeBase` dont héritent tous les modèles ORM.

**`get_db()`**
Générateur utilisé comme dépendance FastAPI. Ouvre une session, la cède, puis la ferme dans le bloc `finally` — garantit la fermeture même en cas d'exception.

### `models.py` — Tables SQL

#### Table `users`

| Colonne | Type | Contrainte | Rôle |
|---|---|---|---|
| `id` | String | PK | UUID généré automatiquement |
| `email` | String | UNIQUE, NOT NULL, INDEX | Identifiant de connexion |
| `hashed_password` | String | NOT NULL | Hash bcrypt |
| `created_at` | DateTime | — | Date de création |

Relation : `evaluations` (liste d'`Evaluation`, relation `back_populates`).

#### Table `evaluations`

Stocke les inputs et outputs de chaque évaluation.

**Colonnes d'architecture**

| Colonne | Type | Défaut |
|---|---|---|
| `model_type` | String | — |
| `dataset_modality` | String | — |
| `depth` | Integer | — |
| `num_heads` | Integer | — |
| `embed_dim` | Integer | — |
| `mlp_ratio` | Float | — |
| `nb_params` | Integer | — |
| `patch_size` | Integer | — |

**Colonnes d'entraînement**

| Colonne | Type |
|---|---|
| `epochs` | Integer |
| `learning_rate` | Float |
| `batch_size` | Integer |
| `dropout` | Float |
| `weight_decay` | Float |
| `data_augmentation` | Boolean |

**Colonnes de dataset**

| Colonne | Type | Note |
|---|---|---|
| `nb_train_samples` | Integer | — |
| `nb_classes` | Integer | — |
| `class_balance` | Float | Legacy, nullable |
| `dataset_intra_variance` | Float | Nullable |
| `dataset_inter_class_distance` | Float | Nullable |

**Colonnes de performance**

| Colonne | Type |
|---|---|
| `train_accuracy` | Float |
| `test_accuracy` | Float |

**Colonnes de résultat**

| Colonne | Type | Note |
|---|---|---|
| `auc` | Float | AUC prédite |
| `risk_level` | String | "Faible", "Moyen", "Élevé" |
| `recommendations` | Text | JSON array sérialisé |
| `model_name` | String | Nom du fichier modèle |
| `dataset_name` | String | Nom du fichier dataset ou URL |
| `model_used` | String | "A", "B", ou "heuristique" |

Relation : `user` (FK → users), `report` (relation 1:1 avec `Report`, `uselist=False`).

#### Table `reports`

| Colonne | Type | Note |
|---|---|---|
| `id` | String | PK, UUID |
| `evaluation_id` | String | FK → evaluations, NOT NULL |
| `content` | Text | Texte complet du rapport |
| `created_at` | DateTime | — |

Relation : `evaluation` (FK → evaluations).

---

## 9. Schémas Pydantic — `schemas/`

### `auth.py`

| Schéma | Champs | Usage |
|---|---|---|
| `SignupRequest` | `email: str`, `password: str` | Body POST /auth/signup |
| `LoginRequest` | `email: str`, `password: str` | Body POST /auth/login |
| `AuthResponse` | `access_token: str`, `token_type: str = "bearer"` | Réponse signup/login |
| `MeResponse` | `id: str`, `email: str` | Réponse GET /auth/me |

### `evaluation.py`

**`EvaluateInput`** — 20 champs avec valeurs par défaut

| Groupe | Champs |
|---|---|
| Architecture | `model_type`, `dataset_modality`, `depth`, `num_heads`, `embed_dim`, `mlp_ratio`, `nb_params`, `patch_size` |
| Entraînement | `epochs`, `learning_rate`, `batch_size`, `dropout`, `weight_decay`, `data_augmentation` |
| Dataset | `nb_train_samples`, `nb_classes`, `dataset_intra_variance`, `dataset_inter_class_distance` |
| Performance | `train_accuracy`, `test_accuracy` |

**`EvaluateResponse`**
```python
auc: float
risk_level: str          # "Faible" | "Moyen" | "Élevé"
recommendations: List[str]
report: str
model_name: Optional[str]
dataset_name: Optional[str]
model_used: Optional[str]   # "A" | "B" | "heuristique"
```

**`EvaluationRecord`**
Hérite de `EvaluateResponse` et ajoute `id`, `created_at`, `input: EvaluateInput`.
`model_config = {"from_attributes": True}` permet la conversion depuis un objet SQLAlchemy.

**`SubmitResponse`**
```python
job_id: str   # UUID retourné après soumission
```

### `insights.py`

**`FeatureImportance`**
```python
feature: str    # nom de la feature
importance: float
```

### `results.py`

**`GapAucPoint`** — un point du scatter plot
```python
gap: float       # train_accuracy - test_accuracy
auc: float
modality: str    # "image" | "tabular" | "text"
```

**`ResultsSummary`**
```python
runs: int                        # nombre d'évaluations
gap_vs_auc: List[GapAucPoint]   # points pour scatter plot
auc_histogram: List[int]         # 10 buckets de 0.05 chacun
```

---

## 10. Routes API — `api/`

### `auth.py` — Préfixe `/auth`

#### `POST /auth/signup`
**Corps** : `SignupRequest` (email, password)
**Logique** :
1. Cherche un utilisateur existant avec le même email → 400 si trouvé
2. Crée `models.User` avec UUID généré et mot de passe haché
3. Génère un JWT et le retourne

**Réponse** : `AuthResponse` (access_token)

#### `POST /auth/login`
**Corps** : `LoginRequest` (email, password)
**Logique** :
1. Cherche l'utilisateur par email → 401 si introuvable
2. Vérifie le mot de passe avec bcrypt → 401 si incorrect
3. Génère un JWT et le retourne

**Réponse** : `AuthResponse` (access_token)

#### `GET /auth/me` *(protégé)*
**Dépendances** : `get_current_user`
**Logique** : Retourne les informations de l'utilisateur extrait du JWT
**Réponse** : `MeResponse` (id, email)

---

### `insights.py` — Préfixe `/insights`

#### `GET /insights/feature-importance` *(public)*
**Logique** :
1. Appelle `_load_models()` pour charger les XGBoost si pas encore fait
2. Essaie de récupérer `model_A_regressor.feature_importances_`
3. Trie par importance décroissante et retourne la liste
4. Si le modèle n'est pas disponible → retourne `_FALLBACK` (liste codée en dur avec les importances approximatives basées sur la connaissance domaine)

**Réponse** : `List[FeatureImportance]`

**`_FALLBACK`** contient 11 features dont les plus importantes sont :
- `train_test_gap` : 0.29
- `nb_train_samples_log` : 0.18
- `dropout` : 0.11

---

### `results.py` — Préfixe `/results`

#### `GET /results/summary` *(protégé)*
**Dépendances** : `get_current_user`, `get_db`
**Logique** :
1. Récupère toutes les évaluations de l'utilisateur (sans filtrage de date)
2. Pour chaque évaluation :
   - `gap = max(0, train_accuracy - test_accuracy)`
   - `bucket = min(9, int((auc - 0.5) / 0.05))` → 10 buckets de AUC=0.50 à AUC=0.99
3. Construit `gap_vs_auc` (scatter) et `auc_histogram` (distribution)

**Réponse** : `ResultsSummary`

---

### `evaluations.py` — Pas de préfixe global

#### `POST /evaluate` *(protégé, legacy)*
**Corps** : `EvaluateInput` (JSON)
**Usage** : Formulaire manuel sans upload de fichiers
**Logique** :
1. `enrich(input_dict)` → calcule `params_per_sample` + `train_test_gap`
2. `predictor.predict(enriched)` → AUC + risk_level + model_used
3. `report_agent.generate_full()` → rapport + recommandations
4. `_save_evaluation()` → persistance en base

**Réponse** : `EvaluateResponse`

---

#### `POST /evaluate/submit` *(protégé)*
**Corps** : `multipart/form-data`

| Champ | Type | Obligatoire |
|---|---|---|
| `model_file` | UploadFile (.pkl) | Non |
| `config_file` | UploadFile (.json) | Non |
| `dataset_file` | UploadFile (.csv/.json) | Non |
| `dataset_url` | str | Non |
| `manual_params` | str (JSON) | Non (défaut `{}`) |

**Logique** :
1. Lit les bytes de chaque fichier uploadé
2. Vérifie les tailles : modèle ≤ 200 Mo, dataset ≤ 100 Mo → 413 si dépassement
3. Parse `manual_params` JSON (silencieux si invalide)
4. Crée un Job avec UUID
5. Lance `_run_pipeline()` en background via `BackgroundTasks`
6. Retourne immédiatement `{"job_id": "..."}`

**Réponse** : `SubmitResponse` (job_id)

---

#### `GET /evaluate/{job_id}/stream` *(protégé)*
**Usage** : Écoute les événements SSE d'un job
**Logique** :
1. Vérifie que le job existe → 404 si introuvable
2. Ouvre un générateur async qui drain la queue du Job
3. Chaque événement est formaté en SSE : `data: {json}\n\n`
4. Le client maintient la connexion jusqu'à l'événement `{"step": "done"}`

**Réponse** : `StreamingResponse` (media_type `text/event-stream`)

Headers spéciaux :
```
Cache-Control: no-cache
X-Accel-Buffering: no
Connection: keep-alive
```

---

#### `GET /evaluations` *(protégé)*
**Dépendances** : `get_current_user`, `get_db`
**Logique** :
1. Récupère toutes les évaluations de l'utilisateur, triées par `created_at DESC`
2. Pour chaque évaluation reconstruit un `EvaluationRecord` complet :
   - Désérialise `recommendations` depuis JSON string
   - Accède au rapport via `e.report.content` (relation lazy)
   - Reconstruit l'objet `EvaluateInput` depuis les colonnes SQL

**Réponse** : `List[EvaluationRecord]`

---

#### `_run_pipeline()` — Tâche de fond

Fonction async executée en arrière-plan après chaque `POST /evaluate/submit`.

**Étape 1 — Agent Modèle**
```python
job.push({"step": "agent_model", "status": "running", ...})
result = ag_model.analyze_pkl(model_bytes, model_filename)
result += ag_model.analyze_config(config_bytes)
features.update(result)
job.push({"step": "agent_model", "status": "done", "extracted": model_features})
```

**Étape 2 — Agent Dataset** *(optionnel, si `has_dataset`)*
```python
job.push({"step": "agent_dataset", "status": "running", ...})
dataset_features = ag_dataset.analyze(dataset_bytes, dataset_filename, dataset_url)
features.update(dataset_features)
job.push({"step": "agent_dataset", "status": "done", "extracted": dataset_features})
```

**Application des paramètres manuels**
```python
for k, v in manual_params.items():
    if v is not None and v != "":
        features[k] = v
agent_analyzer._coerce(features)
```
Les `manual_params` ont la priorité maximale — ils écrasent tout ce qu'ont extrait les agents.

**Étape 3 — Predictor**
```python
enriched = enrich(features)     # ajoute gap + params_per_sample
auc, risk_level, model_used = predictor.predict(enriched)
```

**Étape 4 — Reporter**
```python
context_chunks = rag_retriever.retrieve(features, auc, risk_level)
report_text, recommendations = report_agent.generate_full(
    features, auc, risk_level, context_chunks
)
```

**Persistance**
```python
db = SessionLocal()
_save_evaluation(db, user_id, input_obj, auc, ...)
db.close()
```

**Fin**
```python
job.finish({"auc": auc, "risk_level": ..., "recommendations": ..., "report": ...})
```

---

#### `_save_evaluation()`

Crée un enregistrement `Evaluation` avec tous les paramètres, le flush en base pour obtenir l'`id`, puis crée un `Report` lié. Commit final.

---

## 11. Pipeline de traitement — `pipeline/`

### `features.py`

Définit deux éléments utilisés partout :

**`FEATURE_COLUMNS`** — les 21 features du modèle A (dans l'ordre exact de l'entraînement) :
```
model_type_enc, nb_params_log, depth, embed_dim, mlp_ratio, patch_size,
dropout, dataset_modality_enc, nb_train_samples_log, nb_classes_log,
data_augmentation, epochs, learning_rate, batch_size, weight_decay,
train_accuracy, test_accuracy, train_test_gap, params_per_sample_log,
dataset_intra_variance, dataset_inter_class_distance
```

**`auc_to_risk(auc: float) → str`**
Seuillage :
- `auc < 0.55` → `"Faible"`
- `0.55 ≤ auc < 0.65` → `"Moyen"`
- `auc ≥ 0.65` → `"Élevé"`

---

### `analyzer.py`

**`analyze(input_dict: dict) → dict`**
Calcule deux features dérivées avant de passer au prédicteur :
- `params_per_sample = nb_params / nb_train_samples` — ratio taille modèle / dataset
- `train_test_gap = max(0, train_accuracy - test_accuracy)` — mesure du sur-apprentissage

Retourne `input_dict` enrichi de ces deux champs.

---

### `agent_analyzer.py`

Coordinateur legacy utilisé uniquement par l'endpoint synchrone `POST /evaluate`.

**`analyze(model_bytes, model_filename, config_bytes, dataset_bytes, dataset_filename, dataset_url, manual_params)`**
Orchestre les deux agents dans l'ordre :
1. `agent_model.analyze_pkl()` si `model_bytes`
2. `agent_model.analyze_config()` si `config_bytes`
3. `agent_dataset.analyze()` si `dataset_bytes ou dataset_url`
4. Applique `manual_params` (priorité maximale)
5. Applique `_DEFAULTS` sur les champs manquants (`setdefault`)
6. Appelle `_coerce(features)`

**`_coerce(f: dict)`**
Conversion des types pour tous les champs :
- `int_keys` : depth, num_heads, embed_dim, nb_params, patch_size, epochs, batch_size, nb_train_samples, nb_classes
- `float_keys` : mlp_ratio, learning_rate, dropout, weight_decay, dataset_intra_variance, dataset_inter_class_distance, train_accuracy, test_accuracy
- `data_augmentation` : convertit "true"/"1"/"yes" → `True`

---

### `agent_model.py`

Analyse un fichier `.pkl` pour extraire les caractéristiques architecturales **sans se fier au nom du fichier**.

#### Constantes

**`_TYPE_TO_MODALITY`**
```python
{
    "ViT": "image", "ViT-B": "image", "ViT-Small": "image", "ViT-Tiny": "image",
    "CNN": "image", "ResNet": "image", "VGG": "image", ...
    "Transformer": "text", "RNN": "text",
    "MLP": "tabular", "XGBoost": "tabular", "sklearn": "tabular",
}
```

**`_TYPE_HINTS`**
Liste ordonnée `(keyword, model_type)`, du plus spécifique au plus général :
```python
[("ViT-B", "ViT-B"), ("ViT-Small", "ViT-Small"), ("ViT-Tiny", "ViT-Tiny"),
 ("ViT", "ViT"), ("resnet", "ResNet"), ("densenet", "DenseNet"), ...]
```

#### Fonctions internes

**`_detect_framework(model)`**
Inspecte `type(model).__module__` :
- commence par `"torch."` → `"pytorch"`
- commence par `"tensorflow."` ou `"keras."` → `"keras"`
- commence par `"xgboost."` → `"xgboost"`
- commence par `"sklearn."` → `"sklearn"`
- Sinon duck-typing : cherche `named_modules`, `layers`, `predict`...

**`_detect_model_type(model, filename)`**
Construit une chaîne de référence `cls_name + module_name + filename` et cherche chaque keyword de `_TYPE_HINTS` dedans (case-insensitive).

**`_extract_pytorch(model)`**
Inspecte `model.named_modules()` pour extraire :
- `nb_params` = `sum(p.numel() for p in model.parameters())`
- `depth` = nombre de couches MultiheadAttention + Conv2d + Linear
- `num_heads`, `embed_dim` depuis `nn.MultiheadAttention.num_heads` et `.embed_dim`
- `dropout` depuis `nn.Dropout.p` ou `nn.Dropout2d.p`
- `patch_size` depuis `Conv2d` où `kernel_size == stride > 1` (embeddings ViT)
- `mlp_ratio` = taille FFN / embed_dim (si les deux sont connus)

**`_extract_keras(model)`**
- `nb_params` via `model.count_params()`
- Inspection des `model.layers` : MultiHeadAttention, Conv2D, Dense, Dropout

**`_extract_xgb(model)`**
- `learning_rate` depuis `model.learning_rate`
- `depth` depuis `model.max_depth`
- `epochs` depuis `model.n_estimators`
- `weight_decay` depuis `model.reg_lambda`
- `nb_params` = nombre de feuilles estimé (dump JSON)

**`_extract_sklearn(model)`**
- `epochs` depuis `n_estimators` (RandomForest, GradientBoosting...)
- `depth` depuis `max_depth`
- `learning_rate` si numérique
- `weight_decay` depuis `alpha` (ridge, etc.)
- Pour MLP sklearn : `hidden_layer_sizes` → `embed_dim`, nombre de couches → `depth`

**`analyze_pkl(model_bytes, filename)`**
1. Désérialise avec `joblib.load(BytesIO(model_bytes))`
2. Détecte le framework → appelle la bonne fonction `_extract_*()`
3. Définit `dataset_modality` depuis `_TYPE_TO_MODALITY[model_type]`
4. Retourne le dictionnaire de features

**`analyze_config(config_bytes)`**
Parse un `config.json` HuggingFace :
- `model_type` depuis `"model_type"` ou `"architectures"`
- `embed_dim` depuis `"hidden_size"`
- `num_heads` depuis `"num_attention_heads"`
- `depth` depuis `"num_hidden_layers"`

**`summary_message(features)`**
Génère un message lisible : `"Modèle : ViT · 86,000,000 params · depth=12 · heads=12 · embed=768 · dropout=0.1 · lr=0.0001"`

---

### `agent_dataset.py`

Analyse un fichier dataset pour extraire les statistiques.

**`analyze(dataset_bytes, filename, url)`**
1. Si `dataset_bytes` : essaie de parser en CSV (`pd.read_csv`) puis JSON/JSONL (`pd.read_json`)
2. Si `url` : télécharge avec `requests.get()` puis parse CSV
3. Calcule sur le DataFrame :
   - `nb_train_samples` = nombre de lignes
   - `nb_classes` = nombre de valeurs uniques dans la colonne label
   - `dataset_intra_variance` = moyenne des variances numériques par classe (mesure la compacité)
   - `dataset_inter_class_distance` = distance euclidienne moyenne entre centroïdes de classes (mesure la séparabilité)

**`_find_label_col(df)`**
Heuristique pour trouver la colonne label :
1. Cherche "label", "target", "class", "y" dans les noms de colonnes (insensible à la casse)
2. Sinon : prend la dernière colonne si elle a peu de valeurs uniques (≤ 20)

**`summary_message(features)`**
Génère : `"Dataset : 10,000 échantillons · 2 classes · var. intra : 0.42 · dist. inter : 0.31"`

---

### `predictor.py`

Charge et exécute les 4 modèles XGBoost.

#### Mappings LabelEncoder

```python
MODEL_TYPE_ENC = {
    "AlexNet": 0, "CNN": 1, "DenseNet": 2, "EfficientNet": 3, "MLP": 4,
    "RNN": 5, "ResNet": 6, "Transformer": 7, "VGG": 8, "ViT": 9,
    "ViT-B": 10, "ViT-Small": 11, "ViT-Tiny": 12, "WideResNet": 13,
}
MODALITY_ENC = {"image": 0, "tabular": 1, "text": 2}
RISK_LABELS = {0: "Faible", 1: "Moyen", 2: "Élevé"}
```

#### Sélection du modèle

| Condition | Modèle sélectionné | Features | Performance |
|---|---|---|---|
| `train_accuracy` ET `test_accuracy` présents | **Modèle A** | 21 features | R²=0.98, F1=0.95 |
| Sans accuracy | **Modèle B** | 18 features | R²=0.98, F1=0.945 |
| Aucun fichier JSON présent | **Heuristique** | Règles codées | Approx. |

#### `_load_models()`
Chargement lazy (une seule fois grâce au flag `_models_loaded`). Charge les 4 fichiers JSON depuis `backend/artifacts/`. Si un fichier est absent, il est ignoré silencieusement.

#### `_preprocess(raw: dict) → dict`
Transformations appliquées avant inférence (identiques à celles de l'entraînement) :
- LabelEncoding de `model_type` et `dataset_modality`
- Log1p de `nb_params`, `nb_train_samples`, `nb_classes`, `params_per_sample`
- `data_augmentation` → int (0 ou 1)
- `train_test_gap` = max(0, train_accuracy - test_accuracy)

#### `predict(features_dict) → Tuple[float, str, str]`
Retourne `(auc, risk_level, model_used)` :
1. Sélectionne A ou B selon la présence des accuracies
2. Préprocesse les features
3. Construit un DataFrame pandas avec les colonnes dans le bon ordre
4. Le régresseur prédit l'AUC (clampé entre 0.50 et 0.99)
5. Le classifieur prédit la classe de risque (0/1/2)
6. Si le classifieur est absent → `auc_to_risk()` depuis `features.py`

#### `_fallback_auc(features_dict) → float`
Calcul heuristique : base 0.5 + ajouts conditionnels :
- Gap élevé → `+0.9 * gap`
- Pas de dropout → `+0.04`
- Pas de weight decay → `+0.03`
- Pas de data augmentation → `+0.04`
- Epochs > 100 → `+0.03`
- Dataset < 5000 → `+0.05`
- embed_dim > 512 → `+0.02`
- Dataset tabulaire → `+0.02`

---

### `report_agent.py`

Génère rapport et recommandations, en deux modes : LLM Groq ou règles.

#### `generate_full(input_dict, auc, risk_level, context_chunks) → Tuple[str, List[str]]`
Point d'entrée principal.
1. Si `GROQ_API_KEY` absent → log + fallback règles
2. Sinon → appel `_groq_full()` dans try/except
3. Si Groq échoue → log warning + fallback règles

Logs émis :
```
INFO   [report] GROQ_API_KEY absent → rapport par règles
INFO   [report] Appel Groq JSON (llama-3.3-70b-versatile) — RAG chunks : 4
INFO   [report] Groq OK — 4 recommandations générées
WARNING [report] Groq ECHEC (RateLimitError) → fallback règles
```

#### `_groq_full(input_dict, auc, risk_level, context_chunks)`
Construit un prompt complet avec :
- Tous les paramètres du modèle
- Les chunks RAG (si disponibles) sous forme d'extraits de littérature
- Instructions : générer un JSON `{"report": "...", "recommendations": [...]}`

Le rapport et les recommandations sont générés dans le même contexte → cohérence garantie.

#### `_rule_report(input_dict, auc, risk_level) → str`
Génère un rapport textuel basé sur des règles : mentionne le gap, le niveau de risque, la taille du dataset.

#### `_rule_recommendations(input_dict, auc, risk_level) → List[str]`
Génère des recommandations basées sur des seuils :
- `gap > 0.1` → réduire le sur-apprentissage
- `dropout < 0.1` → augmenter le dropout
- `weight_decay < 1e-4` → augmenter weight decay
- `data_augmentation=False` → activer l'augmentation
- `nb_train_samples < 5000` → élargir le dataset
- `dataset_intra_variance < 0.3` → dataset trop homogène
- `auc >= 0.65` → défenses DP-SGD/distillation/MemGuard
- `auc >= 0.55` → surveiller + renforcer régularisation

---

## 12. Module RAG — `rag/`

Enrichit les rapports avec des extraits de papiers de recherche sur la MIA.

### `store.py`

**Architecture** : Singleton lazy — la collection ChromaDB est ouverte une seule fois au premier appel et réutilisée.

**`_CHROMA_DIR`** : `backend/chroma_db/` (calculé dynamiquement via `Path(__file__)`).

**`_get_collection() → Optional[collection]`**
1. Si le singleton existe déjà → retourne-le
2. Si `backend/chroma_db/` n'existe pas → retourne `None` (dégradation silencieuse)
3. Ouvre ChromaDB avec `PersistentClient`
4. Utilise `DefaultEmbeddingFunction` (ONNX, sans sentence-transformers)
5. En cas d'erreur → retourne `None`

**`search(query, n_results=4) → List[Dict[str, str]]`**
Effectue une recherche sémantique et retourne `[{"text": ..., "source": ...}]`.
Retourne `[]` si la collection est indisponible.

**`is_available() → bool`**
Retourne `True` si le ChromaDB est chargeable. Utilisé par `retriever.retrieve()`.

### `retriever.py`

**`_build_query(features, auc, risk_level) → str`**
Construit une requête en langage naturel à partir du contexte d'évaluation. Exemples de termes ajoutés :
- Toujours : `"membership inference attack privacy"`
- Type de modèle : `"CNN model"`
- AUC + niveau : `"AUC 0.72 Élevé risk"`
- Si gap > 0.1 : `"overfitting train test gap 0.15"`
- Si dropout < 0.1 : `"low dropout memorization"`
- Si weight_decay < 1e-4 : `"no regularization generalization"`
- Si auc ≥ 0.65 : `"high vulnerability defense differential privacy distillation"`
- Si nb_samples < 5000 : `"small dataset memorization risk"`

**`retrieve(features, auc, risk_level, n=4) → List[str]`**
Vérifie `store.is_available()`, construit la query, appelle `store.search()`, retourne les textes seuls (sans métadonnées source). Retourne `[]` si RAG indisponible — dégradation silencieuse garantie.

---

## 13. Tableau récapitulatif des endpoints

| Méthode | URL | Auth | Corps | Réponse |
|---|---|---|---|---|
| `POST` | `/auth/signup` | Non | `{email, password}` | `{access_token}` |
| `POST` | `/auth/login` | Non | `{email, password}` | `{access_token}` |
| `GET` | `/auth/me` | JWT | — | `{id, email}` |
| `POST` | `/evaluate` | JWT | `EvaluateInput` (JSON) | `EvaluateResponse` |
| `POST` | `/evaluate/submit` | JWT | multipart/form-data | `{job_id}` |
| `GET` | `/evaluate/{job_id}/stream` | JWT | — | SSE stream |
| `GET` | `/evaluations` | JWT | — | `List[EvaluationRecord]` |
| `GET` | `/insights/feature-importance` | Non | — | `List[FeatureImportance]` |
| `GET` | `/results/summary` | JWT | — | `ResultsSummary` |
| `GET` | `/` | Non | — | `{"status": "ok"}` |

---

## 14. Flux complet d'une évaluation

```
┌──────────────────────────────────────────────────────────┐
│                       FRONTEND                           │
│                                                          │
│  1. POST /evaluate/submit (model.pkl + dataset.csv)      │
│     ← réponse : {job_id: "abc-123"}                      │
│                                                          │
│  2. GET /evaluate/abc-123/stream (SSE)                   │
│     ← écoute les événements en temps réel                │
└──────────────────────────────────────────────────────────┘
                         │
                         │ BackgroundTask
                         ▼
┌──────────────────────────────────────────────────────────┐
│               _run_pipeline() (async)                    │
│                                                          │
│  ┌─ Étape 1 : agent_model ────────────────────────────┐  │
│  │  analyze_pkl() → framework + type + params         │  │
│  │  analyze_config() → num_heads, embed_dim, depth    │  │
│  │  → event "agent_model done" + extracted features   │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ Étape 2 : agent_dataset (si fichier fourni) ──────┐  │
│  │  analyze() → nb_samples, nb_classes,               │  │
│  │              intra_variance, inter_distance         │  │
│  │  → event "agent_dataset done" + extracted features │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  [manual_params écrasent tout — priorité max]            │
│  [_coerce() force les types]                             │
│                                                          │
│  ┌─ Étape 3 : predictor ──────────────────────────────┐  │
│  │  enrich() → train_test_gap + params_per_sample     │  │
│  │  predict() → sélectionne modèle A ou B             │  │
│  │           → XGBoost régression → AUC               │  │
│  │           → XGBoost classification → risk_level    │  │
│  │  → event "predictor done" (AUC + niveau)           │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ Étape 4 : reporter ───────────────────────────────┐  │
│  │  rag_retriever.retrieve() → 4 chunks ChromaDB      │  │
│  │  report_agent.generate_full()                      │  │
│  │    ├─ [Groq] 1 appel JSON → rapport + recs         │  │
│  │    └─ [Fallback] règles → rapport + recs           │  │
│  │  _save_evaluation() → SQLite                       │  │
│  │  → event "reporter done"                           │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  job.finish({auc, risk_level, recommendations, report})  │
└──────────────────────────────────────────────────────────┘
                         │
                         │ SSE event "done"
                         ▼
                    FRONTEND affiche les résultats
```
