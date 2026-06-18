const API_URL = (import.meta as any).env?.VITE_API_URL || "";
const USE_MOCK = !API_URL;

const TOKEN_KEY = "mia_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}
export interface MeResponse {
  id: string;
  email: string;
}

export type ModelType =
  | "CNN" | "MLP" | "ResNet" | "WideResNet" | "DenseNet"
  | "AlexNet" | "ViT" | "ViT-B" | "EfficientNet" | "MobileNet" | "Transformer";

export interface EvaluateInput {
  model_type: ModelType | string;
  dataset_modality: "image" | "tabular" | "text";
  depth: number;
  num_heads: number;
  embed_dim: number;
  mlp_ratio: number;
  nb_params: number;
  patch_size: number;
  epochs: number;
  learning_rate: number;
  batch_size: number;
  dropout: number;
  weight_decay: number;
  data_augmentation: boolean;
  nb_train_samples: number;
  nb_classes: number;
  dataset_intra_variance: number;
  dataset_inter_class_distance: number;
  train_accuracy: number;
  test_accuracy: number;
}

export type RiskLevel = "Faible" | "Moyen" | "Élevé";

export interface EvaluateResponse {
  auc: number;
  risk_level: RiskLevel;
  recommendations: string[];
  report: string;
  model_name?: string;
  dataset_name?: string;
}

export interface EvaluationRecord extends EvaluateResponse {
  id: string;
  created_at: string;
  input: EvaluateInput;
  model_name?: string;
  dataset_name?: string;
}

export interface FeatureImportance {
  feature: string;
  importance: number;
}

export interface ResultsSummary {
  runs: number;
  gap_vs_auc: { gap: number; auc: number; modality: string }[];
  auc_histogram: number[];
}

export interface JobEvent {
  step: string;
  status?: "running" | "done" | "error";
  message?: string;
  result?: EvaluateResponse;
}

// ── HTTP helper ──────────────────────────────────────────────────────────────

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Erreur ${res.status}`);
  }
  return res.json();
}

// ── Mock backend ─────────────────────────────────────────────────────────────

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const MOCK_USERS_KEY = "mia_mock_users";
const MOCK_EVALS_KEY = "mia_mock_evals";

function readMockUsers(): Record<string, { id: string; password: string }> {
  if (typeof window === "undefined") return {};
  try { return JSON.parse(localStorage.getItem(MOCK_USERS_KEY) || "{}"); } catch { return {}; }
}
function writeMockUsers(u: Record<string, { id: string; password: string }>) {
  localStorage.setItem(MOCK_USERS_KEY, JSON.stringify(u));
}
function readMockEvals(): EvaluationRecord[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(localStorage.getItem(MOCK_EVALS_KEY) || "[]"); } catch { return []; }
}
function writeMockEvals(e: EvaluationRecord[]) {
  localStorage.setItem(MOCK_EVALS_KEY, JSON.stringify(e));
}
function makeToken(email: string): string { return btoa(JSON.stringify({ email, t: Date.now() })); }
function emailFromToken(token: string): string | null {
  try { return JSON.parse(atob(token)).email; } catch { return null; }
}

function predictAuc(i: EvaluateInput): EvaluateResponse {
  const gap = Math.max(0, i.train_accuracy - i.test_accuracy);
  let auc = 0.5 + gap * 0.9;
  if (i.dropout < 0.1) auc += 0.04;
  if (i.weight_decay < 1e-4) auc += 0.03;
  if (!i.data_augmentation) auc += 0.04;
  if (i.epochs > 100) auc += 0.03;
  if (i.nb_train_samples < 5000) auc += 0.05;
  if (i.dataset_intra_variance < 0.3) auc += 0.03;
  if (i.dataset_inter_class_distance < 0.3) auc += 0.03;
  auc = Math.max(0.5, Math.min(0.99, auc));

  let risk: RiskLevel = "Faible";
  if (auc >= 0.65) risk = "Élevé";
  else if (auc >= 0.55) risk = "Moyen";

  const recs: string[] = [];
  if (gap > 0.1) recs.push("Réduire le sur-apprentissage : ↑ régularisation, ↓ epochs ou early stopping.");
  if (i.dropout < 0.1) recs.push("Augmenter le dropout (0.1 – 0.3) pour limiter la mémorisation.");
  if (i.weight_decay < 1e-4) recs.push("Augmenter le weight decay (≥ 1e-4).");
  if (!i.data_augmentation) recs.push("Activer la data augmentation pour brouiller les signatures.");
  if (i.nb_train_samples < 5000) recs.push("Élargir le dataset d'entraînement.");
  if (auc >= 0.65) recs.push("Envisager une défense : DP-SGD, knowledge distillation ou MemGuard.");
  if (recs.length === 0) recs.push("Configuration robuste : maintenir la régularisation et surveiller le gap.");

  const report = `Estimation AUC ≈ ${auc.toFixed(3)}. Gap train/test = ${gap.toFixed(3)}. Niveau : ${risk}.`;
  return { auc: Number(auc.toFixed(3)), risk_level: risk, recommendations: recs, report };
}

const _mockJobs: Record<string, JobEvent[]> = {};

// ── Public API ────────────────────────────────────────────────────────────────

export const api = {
  async signup(email: string, password: string): Promise<AuthResponse> {
    if (USE_MOCK) {
      await sleep(400);
      const users = readMockUsers();
      if (users[email]) throw new Error("Un compte existe déjà pour cet email.");
      users[email] = { id: crypto.randomUUID(), password };
      writeMockUsers(users);
      return { access_token: makeToken(email), token_type: "bearer" };
    }
    return request("/auth/signup", { method: "POST", body: JSON.stringify({ email, password }) });
  },

  async login(email: string, password: string): Promise<AuthResponse> {
    if (USE_MOCK) {
      await sleep(400);
      const users = readMockUsers();
      const u = users[email];
      if (!u || u.password !== password) throw new Error("Identifiants invalides.");
      return { access_token: makeToken(email), token_type: "bearer" };
    }
    return request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
  },

  async me(): Promise<MeResponse> {
    if (USE_MOCK) {
      await sleep(150);
      const token = getToken();
      if (!token) throw new Error("Non authentifié");
      const email = emailFromToken(token);
      if (!email) throw new Error("Token invalide");
      const users = readMockUsers();
      const u = users[email];
      if (!u) throw new Error("Utilisateur inconnu");
      return { id: u.id, email };
    }
    return request("/auth/me");
  },

  async evaluate(input: EvaluateInput): Promise<EvaluateResponse> {
    if (USE_MOCK) {
      await sleep(700);
      const res = predictAuc(input);
      const evals = readMockEvals();
      evals.unshift({ ...res, id: crypto.randomUUID(), created_at: new Date().toISOString(), input });
      writeMockEvals(evals.slice(0, 50));
      return res;
    }
    return request("/evaluate", { method: "POST", body: JSON.stringify(input) });
  },

  async submitEvaluation(formData: FormData): Promise<{ job_id: string }> {
    if (USE_MOCK) {
      await sleep(300);
      const jobId    = crypto.randomUUID();
      _mockJobs[jobId] = [];
      const hasDataset = formData.has("dataset_file") || !!formData.get("dataset_url");
      const auc   = Number((0.5 + Math.random() * 0.45).toFixed(3));
      const risk: RiskLevel = auc >= 0.65 ? "Élevé" : auc >= 0.55 ? "Moyen" : "Faible";

      const schedule: [number, JobEvent][] = [
        [300,  { step: "agent_model",   status: "running", message: "Analyse du fichier modèle…" }],
        [1200, { step: "agent_model",   status: "done",    message: "Modèle analysé · paramètres extraits." }],
        ...(hasDataset ? [
          [1300, { step: "agent_dataset", status: "running", message: "Analyse du dataset…" }],
          [2200, { step: "agent_dataset", status: "done",    message: "Dataset analysé · 10 000 échantillons · 2 classes · var. intra : 0.42." }],
        ] as [number, JobEvent][] : []),
        [hasDataset ? 2300 : 1300, { step: "predictor", status: "running", message: "Prédiction de la vulnérabilité MIA…" }],
        [hasDataset ? 3200 : 2200, { step: "predictor", status: "done",    message: `AUC estimée : ${auc.toFixed(3)} — Risque ${risk}` }],
        [hasDataset ? 3300 : 2300, { step: "reporter",  status: "running", message: "Génération du rapport et des recommandations…" }],
        [hasDataset ? 4000 : 3000, { step: "reporter",  status: "done",    message: "Rapport généré avec succès." }],
        [hasDataset ? 4100 : 3100, { step: "done",      result: {
          auc, risk_level: risk,
          recommendations: ["Augmenter le dropout (0.1–0.3).", "Activer la data augmentation."],
          report: `Estimation AUC ≈ ${auc.toFixed(3)}. Niveau : ${risk}. (mode démo)`,
          model_name: "mock_model.pkl",
          dataset_name: hasDataset ? "mock_dataset.csv" : undefined,
        }}],
        [hasDataset ? 4200 : 3200, { step: "__end__" }],
      ];

      schedule.forEach(([delay, event]) => setTimeout(() => _mockJobs[jobId].push(event), delay));
      return { job_id: jobId };
    }
    const token = getToken();
    const res = await fetch(`${API_URL}/evaluate/submit`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(text || `Erreur ${res.status}`);
    }
    return res.json();
  },

  async streamJob(jobId: string, onEvent: (e: JobEvent) => void): Promise<void> {
    if (USE_MOCK) {
      return new Promise((resolve) => {
        let idx = 0;
        const timer = setInterval(() => {
          const events = _mockJobs[jobId] || [];
          while (idx < events.length) {
            const ev = events[idx++] as any;
            if (ev.step === "__end__") { clearInterval(timer); resolve(); return; }
            onEvent(ev);
          }
        }, 100);
      });
    }
    const token = getToken();
    const res = await fetch(`${API_URL}/evaluate/${jobId}/stream`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(`Stream erreur ${res.status}`);
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() ?? "";
      for (const chunk of chunks) {
        const line = chunk.trim();
        if (line.startsWith("data: ")) {
          try { onEvent(JSON.parse(line.slice(6))); } catch { /* malformed */ }
        }
      }
    }
  },

  async evaluations(): Promise<EvaluationRecord[]> {
    if (USE_MOCK) {
      await sleep(200);
      return readMockEvals();
    }
    return request("/evaluations");
  },

  async featureImportance(): Promise<FeatureImportance[]> {
    if (USE_MOCK) {
      await sleep(300);
      return [
        { feature: "train_test_gap",               importance: 0.28 },
        { feature: "nb_train_samples",             importance: 0.16 },
        { feature: "dataset_intra_variance",       importance: 0.12 },
        { feature: "dataset_inter_class_distance", importance: 0.10 },
        { feature: "dropout",                      importance: 0.09 },
        { feature: "weight_decay",                 importance: 0.08 },
        { feature: "epochs",                       importance: 0.07 },
        { feature: "data_augmentation",            importance: 0.06 },
        { feature: "embed_dim",                    importance: 0.04 },
        { feature: "depth",                        importance: 0.03 },
        { feature: "learning_rate",                importance: 0.02 },
      ];
    }
    return request("/insights/feature-importance");
  },

  async resultsSummary(): Promise<ResultsSummary> {
    if (USE_MOCK) {
      await sleep(300);
      const modalities = ["image", "tabular", "text"] as const;
      const points = Array.from({ length: 120 }, () => {
        const gap = Math.random() * 0.4;
        const auc = Math.max(0.5, Math.min(0.95, 0.5 + gap * 0.9 + (Math.random() - 0.5) * 0.08));
        return { gap: +gap.toFixed(3), auc: +auc.toFixed(3), modality: modalities[Math.floor(Math.random() * 3)] };
      });
      const hist = Array.from({ length: 10 }, () => 0);
      points.forEach((p) => { const b = Math.min(9, Math.floor((p.auc - 0.5) / 0.05)); hist[b]++; });
      return { runs: points.length, gap_vs_auc: points, auc_histogram: hist };
    }
    return request("/results/summary");
  },
};
