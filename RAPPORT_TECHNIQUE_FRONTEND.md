# Rapport Technique — Frontend
## MIA Insight Gardien

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Stack technique](#2-stack-technique)
3. [Structure des fichiers](#3-structure-des-fichiers)
4. [Couche client API — `api/client.ts`](#4-couche-client-api--apiclientts)
5. [Contexte d'authentification — `lib/auth-context.tsx`](#5-contexte-dauthentification--libauth-contexttsx)
6. [Routeur — `router.tsx`](#6-routeur--routertsx)
7. [Racine de l'app — `routes/__root.tsx`](#7-racine-de-lapp--routes__roottsx)
8. [Pages (routes)](#8-pages-routes)
9. [Composants partagés](#9-composants-partagés)
10. [Composants UI (shadcn)](#10-composants-ui-shadcn)
11. [Flux d'authentification](#11-flux-dauthentification)
12. [Flux d'une évaluation côté frontend](#12-flux-dune-évaluation-côté-frontend)

---

## 1. Vue d'ensemble

Le frontend est une **Single Page Application (SPA)** construite avec React 19. Il communique avec le backend FastAPI via une couche client API centralisée (`api/client.ts`). Il dispose d'un **mode mock intégré** qui simule tout le backend dans le navigateur (localStorage) quand aucune URL d'API n'est configurée.

Les pages sont organisées comme des **file routes** TanStack Router — chaque fichier dans `routes/` devient automatiquement une route.

---

## 2. Stack technique

| Composant | Technologie | Version |
|---|---|---|
| Framework UI | React | 19 |
| Bundler | Vite | — |
| Routeur | TanStack Router | file-based routing |
| State serveur / cache | TanStack Query (React Query) | — |
| Composants UI | shadcn/ui (Radix UI + Tailwind) | — |
| CSS | Tailwind CSS | v4 |
| Icônes | Lucide React | — |
| Graphiques | Recharts | — |
| Toasts | Sonner | — |
| Typage | TypeScript | — |

---

## 3. Structure des fichiers

```
frontend/src/
├── api/
│   └── client.ts              ← Client HTTP + types TypeScript + mock backend
├── lib/
│   ├── auth-context.tsx       ← Contexte React d'authentification (user, login, logout)
│   ├── utils.ts               ← Utilitaires Tailwind (cn())
│   └── error-capture.ts       ← Capture d'erreurs
├── components/
│   ├── app-shell.tsx          ← Layout protégé (sidebar + garde de route)
│   ├── app-sidebar.tsx        ← Barre latérale de navigation
│   ├── risk-badge.tsx         ← Badge coloré de niveau de risque
│   └── ui/                    ← ~40 composants shadcn/ui (Button, Card, Input...)
├── routes/
│   ├── __root.tsx             ← Route racine (providers globaux, meta HTML)
│   ├── index.tsx              ← Page d'accueil (/)
│   ├── login.tsx              ← Page de connexion (/login)
│   ├── signup.tsx             ← Page d'inscription (/signup)
│   ├── evaluate.tsx           ← Page d'évaluation (/evaluate) — pipeline UI
│   ├── evaluations.tsx        ← Historique des évaluations (/evaluations)
│   ├── results.tsx            ← Graphiques statistiques (/results)
│   ├── insights.tsx           ← Feature importance (/insights)
│   └── docs.tsx               ← Documentation (/docs)
├── router.tsx                 ← Création du routeur TanStack
├── routeTree.gen.ts           ← Arbre de routes auto-généré (ne pas modifier)
├── start.ts                   ← Point d'entrée SSR/client
└── server.ts                  ← Serveur de rendu (mode SSR)
```

---

## 4. Couche client API — `api/client.ts`

C'est le **seul fichier** qui communique avec le backend. Toutes les pages passent par `api.*` pour faire des requêtes.

### Gestion du token JWT

```typescript
const TOKEN_KEY = "mia_token";
export function getToken(): string | null
export function setToken(t: string | null): void
```

Le token est stocké dans `localStorage` sous la clé `"mia_token"`. `setToken(null)` supprime la clé (déconnexion).

### Mode mock

```typescript
const API_URL = import.meta.env.VITE_API_URL || "";
const USE_MOCK = !API_URL;
```

Si `VITE_API_URL` n'est pas défini, `USE_MOCK = true`. Toutes les fonctions de `api.*` basculent vers une implémentation locale en localStorage. Cela permet de développer ou démo sans backend démarré.

**Données mock stockées dans localStorage** :
- `mia_mock_users` : `Record<email, {id, password}>` — utilisateurs
- `mia_mock_evals` : `EvaluationRecord[]` — évaluations (max 50)

**Token mock** : encode `{email, t: Date.now()}` en base64 (pas de signature).

**`predictAuc(i: EvaluateInput)`** — heuristique locale identique au `_fallback_auc()` du backend. Calcule AUC + risk_level + recommandations dans le navigateur.

### Fonction HTTP générique

```typescript
async function request<T>(path: string, opts: RequestInit = {}): Promise<T>
```

- Ajoute le header `Authorization: Bearer <token>` si un token est présent
- Si la réponse n'est pas OK : lit le corps texte et lance `new Error(text)` — le message d'erreur vient directement du backend (texte brut)
- Parse et retourne le JSON

### Types TypeScript exportés

Tous les types sont définis ici et partagés par toutes les pages.

| Type | Description |
|---|---|
| `AuthResponse` | `{access_token, token_type}` |
| `MeResponse` | `{id, email}` |
| `ModelType` | Union des types de modèles acceptés |
| `EvaluateInput` | 20 champs — miroir exact du schéma backend |
| `RiskLevel` | `"Faible" \| "Moyen" \| "Élevé"` |
| `EvaluateResponse` | `{auc, risk_level, recommendations, report, model_name, dataset_name, model_used}` |
| `EvaluationRecord` | `EvaluateResponse + {id, created_at, input}` |
| `FeatureImportance` | `{feature, importance}` |
| `ResultsSummary` | `{runs, gap_vs_auc, auc_histogram}` |
| `JobEvent` | `{step, status?, message?, result?, extracted?}` |

### Méthodes de l'objet `api`

#### `api.signup(email, password) → Promise<AuthResponse>`
- Mock : vérifie que l'email n'existe pas, crée l'utilisateur, retourne un token base64
- Réel : `POST /auth/signup`

#### `api.login(email, password) → Promise<AuthResponse>`
- Mock : vérifie email + password en clair (mock, pas bcrypt)
- Réel : `POST /auth/login`

#### `api.me() → Promise<MeResponse>`
- Mock : décode le token base64, retourne `{id, email}`
- Réel : `GET /auth/me`

#### `api.evaluate(input) → Promise<EvaluateResponse>`
- Mock : appelle `predictAuc()`, sauvegarde en localStorage
- Réel : `POST /evaluate` (endpoint legacy JSON)

#### `api.submitEvaluation(formData) → Promise<{job_id}>`
- Mock : génère un `job_id`, planifie des événements SSE simulés avec `setTimeout()` sur un calendrier de ~4 secondes
- Réel : `POST /evaluate/submit` (multipart, sans `Content-Type` header — laissé au navigateur pour le boundary)

#### `api.streamJob(jobId, onEvent) → Promise<void>`
Mode réel — parsing SSE manuel :
```typescript
// Lit le ReadableStream par morceaux
const reader = res.body!.getReader();
// Reconstruit les lignes avec un buffer
buffer += decoder.decode(value, { stream: true });
// Découpe sur "\n\n" (délimiteur SSE)
const chunks = buffer.split("\n\n");
// Parse les lignes "data: {...}"
onEvent(JSON.parse(line.slice(6)));
```

Mode mock — poll toutes les 100ms sur un tableau `_mockJobs[jobId]` alimenté par les `setTimeout` du `submitEvaluation` mock.

#### `api.evaluations() → Promise<EvaluationRecord[]>`
- Mock : lit `mia_mock_evals` depuis localStorage
- Réel : `GET /evaluations`

#### `api.featureImportance() → Promise<FeatureImportance[]>`
- Mock : retourne une liste codée en dur de 11 features avec importances
- Réel : `GET /insights/feature-importance`

#### `api.resultsSummary() → Promise<ResultsSummary>`
- Mock : génère 120 points aléatoires (gap/AUC) et leur histogramme
- Réel : `GET /results/summary`

---

## 5. Contexte d'authentification — `lib/auth-context.tsx`

React Context qui gère l'état d'authentification de manière globale. Accessible depuis n'importe quel composant via le hook `useAuth()`.

### État interne

```typescript
interface AuthCtx {
  user: MeResponse | null;   // null = non connecté
  loading: boolean;           // true pendant la vérification initiale du token
  login(email, password): Promise<void>;
  signup(email, password): Promise<void>;
  logout(): void;
}
```

### `AuthProvider` — Provider React

**Initialisation (useEffect au montage)**
1. Lit le token dans localStorage
2. Si absent → `loading = false`, `user = null`
3. Si présent → appelle `api.me()` pour valider et récupérer les infos
   - Succès → `setUser(me)`
   - Échec (token expiré/invalide) → `setToken(null)` (suppression)
   - Dans tous les cas → `setLoading(false)`

**`login(email, password)`**
1. `api.login()` → reçoit `access_token`
2. `setToken(access_token)` → sauvegarde dans localStorage
3. `api.me()` → récupère les infos utilisateur
4. `setUser(me)` → met à jour l'état global

**`signup(email, password)`**
Même séquence que `login`.

**`logout()`**
1. `setToken(null)` → supprime de localStorage
2. `setUser(null)` → vide l'état global
(Pas de redirection — c'est `AppShell` qui gère ça)

### `useAuth()`
Hook qui consomme le contexte. Lance une erreur si utilisé hors du `AuthProvider`.

---

## 6. Routeur — `router.tsx`

```typescript
export const getRouter = () => {
  const queryClient = new QueryClient();
  const router = createRouter({
    routeTree,         // arbre auto-généré par TanStack Router
    context: { queryClient },
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
  });
  return router;
};
```

- `routeTree` est auto-généré dans `routeTree.gen.ts` par le plugin Vite TanStack Router
- `scrollRestoration: true` — restaure la position de scroll lors de la navigation back/forward
- `defaultPreloadStaleTime: 0` — précharge les données dès que le lien est survolé
- Le `queryClient` est injecté dans le contexte du routeur pour être accessible depuis les routes

---

## 7. Racine de l'app — `routes/__root.tsx`

C'est la route parente de toutes les autres. Elle définit la structure HTML globale et monte les providers.

### Meta HTML (`head()`)

```typescript
meta: [
  { charSet: "utf-8" },
  { name: "viewport", content: "width=device-width, initial-scale=1" },
  { title: "MIA Insight Gardien" },
  { name: "description", content: "Estimez la vulnérabilité MIA..." },
  { property: "og:title", content: "MIA Insight Gardien" },
  { name: "twitter:card", content: "summary" },
]
```

### `RootShell`
Génère le HTML de base : `<html>`, `<head>`, `<HeadContent />`, `<body>`, `<Scripts />`.

### `RootComponent`
Monte les deux providers globaux dans l'ordre :
```tsx
<QueryClientProvider client={queryClient}>
  <AuthProvider>
    <Outlet />
    <Toaster richColors position="top-right" />
  </AuthProvider>
</QueryClientProvider>
```

- **`QueryClientProvider`** — fournit TanStack Query à toute l'app
- **`AuthProvider`** — fournit le contexte d'auth
- **`<Outlet />`** — emplacement où les routes enfants sont rendues
- **`<Toaster />`** — Sonner : affiche les toasts en haut à droite, avec couleurs riches

### `NotFoundComponent`
Affiche une page 404 avec un lien vers `/`.

### `ErrorComponent`
Affiche une page d'erreur générique avec un bouton "Réessayer" (invalide le routeur et reset le boundary) et un lien "Retour à l'accueil".

---

## 8. Pages (routes)

### `routes/login.tsx` — `/login`

Page de connexion sans sidebar, accessible sans authentification.

**État local** : `email`, `password`, `loading`

**`useEffect`** : Si l'utilisateur est déjà connecté (`user !== null`), redirige vers `redirect` (query param) ou `/`.

**`onSubmit(e)`** :
1. `auth.login(email, password)`
2. Toast success + navigation vers `redirect || "/"`
3. En cas d'erreur → Toast error avec le message du backend

**Route search params** : `validateSearch` extrait `redirect: string` depuis les query params. Utilisé par `AppShell` pour rediriger après connexion.

---

### `routes/signup.tsx` — `/signup`

Page d'inscription identique à login en structure.

Différences :
- Utilise `auth.signup()` au lieu de `auth.login()`
- Pas de `validateSearch` (pas de redirect param)
- Redirige toujours vers `/` après succès
- Lien "Déjà inscrit ? Se connecter" → `/login`

---

### `routes/index.tsx` — `/` (Accueil)

Page d'accueil. Protégée par `AppShell`.

**Données chargées** :
```typescript
useQuery({
  queryKey: ["evaluations-home"],
  queryFn: () => api.evaluations(),
  enabled: !!user,   // désactivé si non connecté
})
```

**Composants affichés** :

**1. Section "Niveaux de risque"** — 3 cartes `RiskCard` :
- Risque Faible (AUC < 0.55) — fond `var(--risk-low)` — icône `ShieldCheck`
- Risque Moyen (0.55 ≤ AUC < 0.65) — fond `var(--risk-medium)` — icône `ShieldQuestion`
- Risque Élevé (AUC ≥ 0.65) — fond `var(--risk-high)` — icône `ShieldAlert`

**2. Section "Méthode"** — Card explicative sur le méta-modèle XGBoost.

**3. Section "Dernières évaluations"** — *(si connecté)* Affiche les 5 dernières évaluations avec AUC + `RiskBadge`. Lien "Voir tout" → `/evaluations`.

**4. Bouton CTA** — "Lancer une évaluation" → `/evaluate`.

---

### `routes/evaluate.tsx` — `/evaluate` (Pipeline)

Page la plus complexe. Gère le formulaire d'upload et l'affichage temps réel de la pipeline.

#### Types internes

**`StepStatus`** : `"pending" | "running" | "done" | "error"`

**`StepState`**
```typescript
{
  id: string;          // "agent_model" | "agent_dataset" | "predictor" | "reporter"
  label: string;       // "Agent Modèle" | ...
  status: StepStatus;
  message: string;
  extracted?: Record<string, unknown>;   // paramètres extraits par l'agent
}
```

**`ManualParams`**
```typescript
{
  train_accuracy, test_accuracy, data_augmentation,
  batch_size, epochs, learning_rate, weight_decay, dropout
}
```

#### Système de précision

```typescript
type PrecisionLevel = "basic" | "improved" | "max";
```

| Niveau | Condition | Barre | Étoiles |
|---|---|---|---|
| `basic` | Modèle seul | Jaune 33% | ★☆☆ |
| `improved` | + Dataset OU + Params | Bleu 66% | ★★☆ |
| `max` | + Dataset ET + Params | Vert 100% | ★★★ |

#### État de la page

```typescript
// Fichiers
const [modelFile, setModelFile] = useState<File | null>(null);
const [configFile, setConfigFile] = useState<File | null>(null);
const [datasetFile, setDatasetFile] = useState<File | null>(null);
const [datasetUrl, setDatasetUrl] = useState("");

// Sections optionnelles
const [datasetOn, setDatasetOn] = useState(false);
const [manualOn, setManualOn] = useState(false);
const [params, setParams] = useState<ManualParams>(MANUAL_DEFAULTS);

// Pipeline
const [loading, setLoading] = useState(false);
const [steps, setSteps] = useState<StepState[]>(buildSteps(false));
const [started, setStarted] = useState(false);
const [result, setResult] = useState<EvaluateResponse | null>(null);
```

#### Fonction `submit(e)`

```typescript
async function submit(e: React.FormEvent) {
  // 1. Valide : modelFile obligatoire
  // 2. setLoading(true), setStarted(true), reset steps
  // 3. Construit FormData :
  formData.append("model_file", modelFile);
  formData.append("config_file", configFile);      // optionnel
  formData.append("dataset_file", datasetFile);    // si datasetOn
  formData.append("dataset_url", datasetUrl);      // si datasetOn
  formData.append("manual_params", JSON.stringify(params) | "{}");
  // 4. api.submitEvaluation(formData) → {job_id}
  // 5. api.streamJob(job_id, onEvent)
}
```

**Callback `onEvent(event: JobEvent)`** :
- `event.step === "done"` → `setResult(event.result)`, `setLoading(false)`, toast success
- `event.step === "error"` → toast error, `setLoading(false)`
- `event.step === "ping"` → ignoré
- Autre step → `setSteps(prev => prev.map(s => s.id === event.step ? {...s, ...update} : s))`

#### Formulaire en 3 sections

**Section 1 — Modèle (toujours visible)**
- Zone de drop `.pkl` : affiche le nom + taille si chargé, bouton X pour supprimer
- Zone de drop `config.json` (optionnel, plus petite)

**Section 2 — Dataset (toggle Switch)**
- Quand le toggle est OFF : section grisée (opacity-90), bannière d'info bleue visible
- Quand ON : affiche zone de drop `.csv/.parquet/.json` + séparateur "ou URL" + Input URL

**Section 3 — Paramètres manuels (toggle Switch)**
- Quand OFF : section grisée, bannière d'info violette visible
- Quand ON : affiche les sliders et inputs :
  - `SliderF` pour `train_accuracy` et `test_accuracy` (0-100%)
  - Switch pour `data_augmentation`
  - `NF` (NumberField) pour `batch_size`, `epochs`, `learning_rate`, `weight_decay`, `dropout`

#### Composants de sous-rendu

**`StepIcon({ status })`**
- `"pending"` → `Circle` (gris, transparent)
- `"running"` → `Loader2` (animé, couleur primaire)
- `"done"` → `CheckCircle2` (vert)
- `"error"` → `XCircle` (rouge)

**`ExtractedTable({ data })`**
Tableau compact des paramètres extraits par chaque agent. Traduit les noms techniques via `EXTRACTED_LABELS`. Formate les nombres (séparateur de milliers, décimales).

**`ResultCard({ result })`**
Affiche le résultat final :
- AUC en grand (taille 6xl, police mono)
- `RiskBadge` grande taille
- Badge coloré "Modèle A / B / Heuristique"
- Texte du rapport
- Liste de recommandations avec icônes `CheckCircle2`

---

### `routes/evaluations.tsx` — `/evaluations` (Historique)

**Données chargées** :
```typescript
useQuery({ queryKey: ["evaluations"], queryFn: () => api.evaluations() })
```

**`EvaluationsPage`** : affiche loading, erreur, ou la liste d'`EvalCard`.

**`EvalCard({ ev })`** — Card accordéon

**En-tête (toujours visible)** :
- Nom du modèle + icône FileText
- Nom du dataset + date (format `fr-FR`) + icône Calendar
- AUC en gros (tabular-nums) + `RiskBadge` taille "md"
- Icône `ChevronDown/Up` selon l'état d'ouverture

**Détail dépliant (si `open === true`)** :
1. **Rapport** : texte complet du rapport
2. **Recommandations** : liste avec icônes `CheckCircle2`
3. **Paramètres utilisés** : grille 2-4 colonnes de 16 champs

Champs affichés avec null guards :
```typescript
["nb_params", ev.input.nb_params?.toLocaleString() ?? "—"],
["train_acc", ev.input.train_accuracy != null ? ev.input.train_accuracy.toFixed(2) : "—"],
["test_acc",  ev.input.test_accuracy  != null ? ev.input.test_accuracy.toFixed(2)  : "—"],
```

---

### `routes/results.tsx` — `/results` (Statistiques)

**Données chargées** :
```typescript
useQuery({ queryKey: ["results-summary"], queryFn: () => api.resultsSummary() })
```

**Graphique 1 — Scatter "Gap train/test vs AUC"** (Recharts `ScatterChart`)
- Axe X : `train_test_gap` (0 → 0.4)
- Axe Y : `auc` (0.5 → 1.0)
- 3 séries colorées : image (`var(--primary)`), tabular (violet), text (orange)
- Tooltip avec fond `var(--card)`

**Graphique 2 — Histogramme "Distribution des AUC"** (Recharts `BarChart`)
- 10 buckets de 0.05 chacun : de AUC=0.50 à AUC=0.99
- Labels sur X : `"0.50"`, `"0.55"`, ..., `"0.95"`
- Couleur des barres selon le bucket :
  - Bucket 0-1 (AUC 0.50-0.59) → `var(--risk-low)` (vert)
  - Bucket 2-3 (AUC 0.60-0.69) → `var(--risk-medium)` (orange)
  - Bucket 4+ (AUC ≥ 0.70) → `var(--risk-high)` (rouge)

---

### `routes/insights.tsx` — `/insights` (Feature Importance)

**Données chargées** :
```typescript
useQuery({ queryKey: ["feature-importance"], queryFn: () => api.featureImportance() })
```

**Graphique — Barres horizontales** (Recharts `BarChart` layout `"vertical"`)
- Axe Y (catégorie) : nom de la feature, largeur 140px
- Axe X (valeur) : importance (0.0 → ~0.30)
- Toutes les barres en `var(--primary)`
- Tooltip formaté à 3 décimales

---

## 9. Composants partagés

### `components/app-shell.tsx`

**`AppShell({ children })`** — Layout principal avec garde de route.

Logique de rendu :
1. Si `loading === true` → affiche un écran de chargement centré
2. Si `user === null` → `<Navigate to="/login" search={{redirect: pathname}} />` (redirection avec mémorisation du chemin)
3. Si `user !== null` → affiche la sidebar + le contenu

```tsx
<div className="flex min-h-screen w-full bg-background">
  <AppSidebar />
  <main className="flex-1 min-w-0">{children}</main>
</div>
```

**`PageHeader({ title, description })`** — En-tête de page standardisé avec `h1` (3xl, font-semibold) et description (muted-foreground).

---

### `components/app-sidebar.tsx`

Sidebar fixe à gauche, masquée sur mobile (`hidden md:flex`), largeur `w-64`.

**Items de navigation** :
```typescript
const items = [
  { title: "Accueil",        url: "/",            icon: Home },
  { title: "Évaluation",    url: "/evaluate",    icon: FlaskConical },
  { title: "Historique",    url: "/evaluations", icon: History },
  { title: "Résultats",     url: "/results",     icon: LineChart },
  { title: "Documentation", url: "/docs",        icon: BookOpen },
];
```

**Mise en évidence de l'item actif** :
```typescript
const active = pathname === it.url;
// active → "bg-sidebar-accent text-sidebar-accent-foreground"
// inactif → "text-sidebar-foreground/75 hover:bg-sidebar-accent/60"
```

**En-tête** : Logo shield + "MIA Insight Gardien" + sous-titre "Vulnerability AI"

**Pied de page** : Email de l'utilisateur connecté + bouton "Se déconnecter" (appelle `auth.logout()`)

---

### `components/risk-badge.tsx`

Badge coloré affiché sur les évaluations. Accepte 3 tailles.

```typescript
const map: Record<RiskLevel, { bg: string; label: string }> = {
  Faible:  { bg: "bg-[color:var(--risk-low)]",    label: "Risque Faible" },
  Moyen:   { bg: "bg-[color:var(--risk-medium)]", label: "Risque Moyen" },
  "Élevé": { bg: "bg-[color:var(--risk-high)]",   label: "Risque Élevé" },
};
const sizes = {
  sm: "px-2 py-0.5 text-xs",
  md: "px-3 py-1 text-sm",
  lg: "px-4 py-2 text-base",
};
```

Rendu : badge arrondi (`rounded-full`) avec un petit cercle blanc à gauche et le label en blanc.

Les couleurs `--risk-low`, `--risk-medium`, `--risk-high` sont des variables CSS définies dans le thème global.

---

## 10. Composants UI (shadcn)

Environ 40 composants dans `components/ui/`. Ce sont des wrappers de composants Radix UI stylés avec Tailwind CSS. Ils ne contiennent pas de logique métier.

Composants les plus utilisés dans ce projet :

| Composant | Usage |
|---|---|
| `Button` | Boutons primaires, ghosts, liens |
| `Card`, `CardHeader`, `CardTitle`, `CardContent` | Conteneurs de sections |
| `Input` | Champs texte, nombre, email |
| `Label` | Labels de formulaire accessibles |
| `Slider` | Sliders 0-1 pour train/test accuracy |
| `Switch` | Toggle pour dataset/manual sections |
| `Separator` | Ligne de séparation |
| `Badge` | (remplacé par `RiskBadge` custom) |
| `Toaster` (Sonner) | Notifications toast |
| `Skeleton` | États de chargement |
| `Tabs` | Onglets |
| `Dialog` | Modales |
| `Select` | Listes déroulantes |

---

## 11. Flux d'authentification

```
┌───────────────────────────────────────────────────────┐
│  App démarre                                          │
│  AuthProvider mount                                   │
│    ├─ Token dans localStorage ?                       │
│    │   OUI → api.me() → setUser()                    │
│    │   NON → setLoading(false), user = null           │
│    └─ loading = false                                 │
└───────────────────────────────────────────────────────┘
                         │
              Route protégée demandée
                         │
                         ▼
┌───────────────────────────────────────────────────────┐
│  AppShell                                             │
│    ├─ loading === true → spinner                      │
│    ├─ user === null → <Navigate to="/login"           │
│    │                            search={{redirect}}> │
│    └─ user !== null → affiche la page                 │
└───────────────────────────────────────────────────────┘
                         │
              Utilisateur non connecté
                         │
                         ▼
┌───────────────────────────────────────────────────────┐
│  /login                                               │
│    ├─ onSubmit → auth.login()                         │
│    │   → api.login() → access_token                   │
│    │   → setToken(access_token)                       │
│    │   → api.me() → user info                         │
│    │   → setUser(me)                                  │
│    └─ navigate({to: redirect || "/"})                 │
└───────────────────────────────────────────────────────┘
```

---

## 12. Flux d'une évaluation côté frontend

```
┌──────────────────────────────────────────────────────────────┐
│  Page /evaluate                                              │
│                                                              │
│  1. Utilisateur dépose model.pkl                             │
│     → setModelFile(file)                                     │
│     → indicateur de précision : "Basique ★☆☆"               │
│                                                              │
│  2. Active le toggle Dataset, dépose dataset.csv             │
│     → indicateur de précision : "Améliorée ★★☆"             │
│                                                              │
│  3. Active le toggle Paramètres, ajuste train/test accuracy  │
│     → indicateur de précision : "Maximale ★★★"              │
│                                                              │
│  4. Clique "Évaluer la vulnérabilité MIA"                    │
│     → submit() construit FormData                            │
│     → api.submitEvaluation(formData)                         │
│     ← {job_id: "abc-123"}                                    │
│                                                              │
│  5. api.streamJob("abc-123", onEvent)                        │
│     Connexion SSE ouverte sur /evaluate/abc-123/stream       │
│                                                              │
│  6. Événements reçus en temps réel :                         │
│                                                              │
│     {step:"agent_model", status:"running", message:"..."}    │
│     → steps[0].status = "running" (icône Loader2 animé)     │
│                                                              │
│     {step:"agent_model", status:"done", extracted:{...}}     │
│     → steps[0].status = "done" (icône CheckCircle2 vert)    │
│     → ExtractedTable affiche les features extraites          │
│                                                              │
│     {step:"agent_dataset", status:"running", ...}            │
│     {step:"agent_dataset", status:"done", extracted:{...}}   │
│                                                              │
│     {step:"predictor", status:"running", ...}                │
│     {step:"predictor", status:"done", message:"AUC: 0.712"}  │
│                                                              │
│     {step:"reporter", status:"running", ...}                 │
│     {step:"reporter", status:"done", ...}                    │
│                                                              │
│     {step:"done", result:{auc:0.712, risk_level:"Élevé",...}}│
│     → setResult(event.result)                                │
│     → ResultCard s'affiche avec AUC + badge + rapport + recs│
│     → toast.success("Évaluation terminée !")                 │
└──────────────────────────────────────────────────────────────┘
```

### Structure de ResultCard (rendu final)

```
┌─────────────────────────────────────────────────────┐
│  AUC prédite                                        │
│  0.712                   ● Risque Élevé             │
│                          Modèle : resnet50.pkl      │
│                          Dataset : train.csv        │
│                          [Modèle A — précision max] │
│                                                     │
│  Rapport texte généré par Groq (ou règles)          │
│  ─────────────────────────────────────────────────  │
│  Recommandations                                    │
│  ✓ Augmenter le dropout (0.1–0.3)                  │
│  ✓ Activer la data augmentation                    │
│  ✓ Envisager DP-SGD ou knowledge distillation      │
└─────────────────────────────────────────────────────┘
```
