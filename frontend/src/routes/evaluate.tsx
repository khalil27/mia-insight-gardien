import { createFileRoute } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { AppShell, PageHeader } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { RiskBadge } from "@/components/risk-badge";
import { api, type EvaluateResponse, type JobEvent } from "@/api/client";
import { toast } from "sonner";
import {
  CheckCircle2, Circle, FlaskConical, Loader2,
  Upload, XCircle, FileText, Database, Settings2, Info,
} from "lucide-react";

export const Route = createFileRoute("/evaluate")({
  component: EvaluatePage,
});

// ── Types ─────────────────────────────────────────────────────────────────────

type StepStatus = "pending" | "running" | "done" | "error";

interface StepState {
  id: string;
  label: string;
  status: StepStatus;
  message: string;
  extracted?: Record<string, unknown>;
}

interface ManualParams {
  train_accuracy: number;
  test_accuracy: number;
  data_augmentation: boolean;
  batch_size: number;
  epochs: number;
  learning_rate: number;
  weight_decay: number;
  dropout: number;
}

const MANUAL_DEFAULTS: ManualParams = {
  train_accuracy: 0.95,
  test_accuracy: 0.88,
  data_augmentation: true,
  batch_size: 64,
  epochs: 50,
  learning_rate: 0.0003,
  weight_decay: 0.0001,
  dropout: 0.1,
};

type PrecisionLevel = "basic" | "improved" | "max";

function getPrecisionLevel(hasDataset: boolean, hasManual: boolean): PrecisionLevel {
  const extras = (hasDataset ? 1 : 0) + (hasManual ? 1 : 0);
  if (extras >= 2) return "max";
  if (extras === 1) return "improved";
  return "basic";
}

const PRECISION_CONFIG = {
  basic:    { label: "Basique",    pct: 33,  bar: "bg-yellow-400", text: "text-yellow-700", stars: 1 },
  improved: { label: "Améliorée",  pct: 66,  bar: "bg-blue-400",   text: "text-blue-700",   stars: 2 },
  max:      { label: "Maximale",   pct: 100, bar: "bg-green-500",  text: "text-green-700",  stars: 3 },
};

function buildSteps(hasDataset: boolean): StepState[] {
  return [
    { id: "agent_model",   label: "Agent Modèle",    status: "pending", message: "" },
    ...(hasDataset ? [{ id: "agent_dataset", label: "Agent Dataset",   status: "pending" as StepStatus, message: "" }] : []),
    { id: "predictor",     label: "Agent Prédicteur", status: "pending", message: "" },
    { id: "reporter",      label: "Agent Générateur", status: "pending", message: "" },
  ];
}

// ── Main component ────────────────────────────────────────────────────────────

function EvaluatePage() {
  // Section 1 — Model (always required)
  const [modelFile,  setModelFile]  = useState<File | null>(null);
  const [configFile, setConfigFile] = useState<File | null>(null);
  const modelInputRef  = useRef<HTMLInputElement>(null);
  const configInputRef = useRef<HTMLInputElement>(null);

  // Section 2 — Dataset (optional toggle)
  const [datasetOn,   setDatasetOn]   = useState(false);
  const [datasetFile, setDatasetFile] = useState<File | null>(null);
  const [datasetUrl,  setDatasetUrl]  = useState("");
  const datasetInputRef = useRef<HTMLInputElement>(null);

  // Section 3 — Manual params (optional toggle)
  const [manualOn, setManualOn] = useState(false);
  const [params,   setParams]   = useState<ManualParams>(MANUAL_DEFAULTS);

  // Pipeline state
  const [loading, setLoading] = useState(false);
  const [steps,   setSteps]   = useState<StepState[]>(buildSteps(false));
  const [started, setStarted] = useState(false);
  const [result,  setResult]  = useState<EvaluateResponse | null>(null);

  function upParam<K extends keyof ManualParams>(k: K, v: ManualParams[K]) {
    setParams((p) => ({ ...p, [k]: v }));
  }

  const precision = getPrecisionLevel(datasetOn, manualOn);
  const cfg       = PRECISION_CONFIG[precision];

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!modelFile) {
      toast.error("Veuillez déposer votre fichier modèle (.pkl).");
      return;
    }
    const hasDatasetData = datasetOn && (!!datasetFile || !!datasetUrl);

    setLoading(true);
    setStarted(true);
    setResult(null);
    setSteps(buildSteps(datasetOn).map((s) => ({ ...s, status: "pending", message: "" })));

    try {
      const formData = new FormData();
      formData.append("model_file", modelFile);
      if (configFile)  formData.append("config_file", configFile);
      if (hasDatasetData && datasetFile) formData.append("dataset_file", datasetFile);
      if (hasDatasetData && datasetUrl)  formData.append("dataset_url",  datasetUrl);
      formData.append("manual_params", manualOn ? JSON.stringify(params) : "{}");

      const { job_id } = await api.submitEvaluation(formData);

      await api.streamJob(job_id, (event: JobEvent) => {
        if (event.step === "done" && event.result) {
          setResult(event.result);
          setLoading(false);
          toast.success("Évaluation terminée !");
        } else if (event.step === "error") {
          toast.error(event.message || "Erreur pipeline");
          setLoading(false);
        } else if (event.step !== "ping") {
          setSteps((prev) =>
            prev.map((s) =>
              s.id === event.step
                ? {
                    ...s,
                    status: (event.status as StepStatus) || s.status,
                    message: event.message || "",
                    ...(event.extracted ? { extracted: event.extracted } : {}),
                  }
                : s
            )
          );
        }
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="p-8 lg:p-12 max-w-3xl">
        <PageHeader
          title="Évaluation MIA"
          description="Déposez votre modèle — les agents extraient tout automatiquement. Ajoutez le dataset ou des paramètres pour affiner la précision."
        />

        <form onSubmit={submit} className="space-y-4">

          {/* ── Precision indicator ── */}
          <Card className="border-0 bg-muted/40">
            <CardContent className="pt-4 pb-4">
              <div className="flex items-center gap-4">
                <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">Précision</span>
                <div className="flex-1 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className={`text-sm font-semibold ${cfg.text}`}>{cfg.label}</span>
                    <span className="text-sm tracking-widest">
                      {"★".repeat(cfg.stars)}
                      <span className="text-muted-foreground/40">{"★".repeat(3 - cfg.stars)}</span>
                    </span>
                  </div>
                  <div className="h-2 bg-background rounded-full overflow-hidden border">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${cfg.bar}`}
                      style={{ width: `${cfg.pct}%` }}
                    />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* ── Section 1 : Modèle (requis) ── */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">1</div>
                <FileText className="h-4 w-4" />
                Modèle
                <span className="ml-1 text-xs font-normal text-muted-foreground">(requis)</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* .pkl drop zone */}
              <div
                className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
                  modelFile ? "border-green-400 bg-green-50/40" : "hover:border-primary/60"
                }`}
                onClick={() => modelInputRef.current?.click()}
              >
                {modelFile ? (
                  <div className="flex items-center justify-center gap-2 text-sm">
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                    <span className="font-medium">{modelFile.name}</span>
                    <span className="text-muted-foreground">({(modelFile.size / 1024).toFixed(0)} Ko)</span>
                    <button type="button" onClick={(ev) => { ev.stopPropagation(); setModelFile(null); }}>
                      <XCircle className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                    </button>
                  </div>
                ) : (
                  <div className="text-muted-foreground text-sm">
                    <Upload className="h-8 w-8 mx-auto mb-2 opacity-40" />
                    Cliquez ou glissez votre fichier <strong>.pkl</strong>
                  </div>
                )}
                <input ref={modelInputRef} type="file" accept=".pkl" className="hidden"
                  onChange={(e) => setModelFile(e.target.files?.[0] ?? null)} />
              </div>

              {/* config.json optional */}
              <div
                className="border border-dashed rounded-lg p-3 text-center cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => configInputRef.current?.click()}
              >
                {configFile ? (
                  <div className="flex items-center justify-center gap-2 text-xs">
                    <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                    <span className="font-medium">{configFile.name}</span>
                    <button type="button" onClick={(ev) => { ev.stopPropagation(); setConfigFile(null); }}>
                      <XCircle className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
                    </button>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    + <strong>config.json</strong> <span className="font-normal">(optionnel — extrait depth, num_heads, embed_dim…)</span>
                  </p>
                )}
                <input ref={configInputRef} type="file" accept=".json" className="hidden"
                  onChange={(e) => setConfigFile(e.target.files?.[0] ?? null)} />
              </div>
            </CardContent>
          </Card>

          {/* ── Section 2 : Dataset (toggle) ── */}
          <Card className={datasetOn ? "" : "opacity-90"}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-muted-foreground text-xs font-bold">2</div>
                  <Database className="h-4 w-4" />
                  Dataset
                </CardTitle>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{datasetOn ? "activé" : "désactivé"}</span>
                  <Switch
                    checked={datasetOn}
                    onCheckedChange={(v) => {
                      setDatasetOn(v);
                      if (!v) { setDatasetFile(null); setDatasetUrl(""); }
                    }}
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* Info banner always visible */}
              <div className="rounded-lg border border-blue-200 bg-blue-50/60 px-3 py-2.5 text-xs text-blue-800 flex items-start gap-2">
                <Info className="h-3.5 w-3.5 shrink-0 mt-0.5 text-blue-500" />
                <span>
                  L'Agent Dataset analyse automatiquement les classes, la variance intra-classe et la distance inter-centroïdes — <strong>aucune saisie requise</strong>.
                  Cela améliore significativement la précision de l'estimation.
                </span>
              </div>

              {/* Upload zone — only when ON */}
              {datasetOn && (
                <div className="space-y-3 pt-1">
                  <div
                    className={`border-2 border-dashed rounded-lg p-5 text-center cursor-pointer transition-colors ${
                      datasetFile ? "border-green-400 bg-green-50/40" : "hover:border-primary/60"
                    }`}
                    onClick={() => datasetInputRef.current?.click()}
                  >
                    {datasetFile ? (
                      <div className="flex items-center justify-center gap-2 text-sm">
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                        <span className="font-medium">{datasetFile.name}</span>
                        <span className="text-muted-foreground">({(datasetFile.size / 1024).toFixed(0)} Ko)</span>
                        <button type="button" onClick={(ev) => { ev.stopPropagation(); setDatasetFile(null); }}>
                          <XCircle className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                        </button>
                      </div>
                    ) : (
                      <div className="text-muted-foreground text-sm">
                        <Upload className="h-7 w-7 mx-auto mb-2 opacity-40" />
                        Glissez un fichier <strong>.csv / .parquet / .json</strong>
                      </div>
                    )}
                    <input ref={datasetInputRef} type="file" accept=".csv,.parquet,.json,.jsonl" className="hidden"
                      onChange={(e) => setDatasetFile(e.target.files?.[0] ?? null)} />
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="h-px flex-1 bg-border" />
                    <span className="text-xs text-muted-foreground">ou URL</span>
                    <div className="h-px flex-1 bg-border" />
                  </div>
                  <Input
                    placeholder="https://raw.githubusercontent.com/…/dataset.csv"
                    value={datasetUrl}
                    onChange={(e) => setDatasetUrl(e.target.value)}
                  />
                </div>
              )}
            </CardContent>
          </Card>

          {/* ── Section 3 : Paramètres manuels (toggle) ── */}
          <Card className={manualOn ? "" : "opacity-90"}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-muted-foreground text-xs font-bold">3</div>
                  <Settings2 className="h-4 w-4" />
                  Paramètres manuels
                </CardTitle>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{manualOn ? "activé" : "désactivé"}</span>
                  <Switch
                    checked={manualOn}
                    onCheckedChange={setManualOn}
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Info banner always visible */}
              <div className="rounded-lg border border-purple-200 bg-purple-50/60 px-3 py-2.5 text-xs text-purple-800 flex items-start gap-2">
                <Info className="h-3.5 w-3.5 shrink-0 mt-0.5 text-purple-500" />
                <span>
                  La précision train/test et la régularisation sont les <strong>signaux les plus forts</strong> pour estimer le risque MIA.
                  Renseignez-les pour maximiser la précision de l'estimation.
                </span>
              </div>

              {/* Form — only when ON */}
              {manualOn && (
                <div className="space-y-4 pt-1">
                  {/* Performances */}
                  <div>
                    <h4 className="text-xs uppercase tracking-wide text-muted-foreground mb-3 font-semibold">Performances mesurées</h4>
                    <div className="grid sm:grid-cols-2 gap-4">
                      <SliderF label="train_accuracy" value={params.train_accuracy} onChange={(v) => upParam("train_accuracy", v)} />
                      <SliderF label="test_accuracy"  value={params.test_accuracy}  onChange={(v) => upParam("test_accuracy", v)} />
                    </div>
                  </div>

                  {/* Training params */}
                  <div>
                    <h4 className="text-xs uppercase tracking-wide text-muted-foreground mb-3 font-semibold">Hyperparamètres</h4>
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      <div className="space-y-1.5">
                        <Label className="text-xs uppercase tracking-wide text-muted-foreground">data_augmentation</Label>
                        <div className="flex items-center gap-3 h-10">
                          <Switch checked={params.data_augmentation} onCheckedChange={(v) => upParam("data_augmentation", v)} />
                          <span className="text-sm text-muted-foreground">{params.data_augmentation ? "oui" : "non"}</span>
                        </div>
                      </div>
                      <NF label="batch_size"   value={params.batch_size}   onChange={(v) => upParam("batch_size", +v)} />
                      <NF label="epochs"       value={params.epochs}       onChange={(v) => upParam("epochs", +v)} />
                      <NF label="learning_rate" value={params.learning_rate} onChange={(v) => upParam("learning_rate", +v)} step="0.00001" />
                      <NF label="weight_decay" value={params.weight_decay}  onChange={(v) => upParam("weight_decay", +v)} step="0.00001" />
                      <NF label="dropout"      value={params.dropout}       onChange={(v) => upParam("dropout", +v)} step="0.01" />
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* ── Submit ── */}
          <div className="flex justify-end pt-1">
            <Button type="submit" size="lg" disabled={loading || !modelFile}>
              {loading
                ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Analyse en cours…</>
                : <><FlaskConical className="h-4 w-4 mr-2" /> Évaluer la vulnérabilité MIA</>}
            </Button>
          </div>
        </form>

        {/* ── Pipeline progress ── */}
        {started && (
          <Card className="mt-6">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Progression du pipeline</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {steps.map((s) => (
                <div key={s.id} className="flex items-start gap-3">
                  <StepIcon status={s.status} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{s.label}</span>
                      {s.status === "running" && (
                        <span className="text-xs text-muted-foreground animate-pulse">en cours…</span>
                      )}
                    </div>
                    {s.message && (
                      <p className="text-xs text-muted-foreground mt-0.5">{s.message}</p>
                    )}
                    {s.status === "done" && s.extracted && Object.keys(s.extracted).length > 0 && (
                      <ExtractedTable data={s.extracted} />
                    )}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* ── Result ── */}
        {result && <ResultCard result={result} />}
      </div>
    </AppShell>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

const EXTRACTED_LABELS: Record<string, string> = {
  model_type:                  "Type de modèle",
  nb_params:                   "Nb paramètres",
  depth:                       "Profondeur",
  num_heads:                   "Têtes d'attention",
  embed_dim:                   "Dimension embedding",
  mlp_ratio:                   "Ratio MLP",
  patch_size:                  "Taille patch",
  learning_rate:               "Learning rate",
  dropout:                     "Dropout",
  weight_decay:                "Weight decay",
  epochs:                      "Epochs",
  nb_train_samples:            "Nb échantillons",
  nb_classes:                  "Nb classes",
  dataset_modality:            "Modalité",
  dataset_intra_variance:      "Variance intra-classe",
  dataset_inter_class_distance:"Distance inter-classes",
};

function formatExtractedValue(key: string, val: unknown): string {
  if (typeof val === "boolean") return val ? "oui" : "non";
  if (typeof val === "number") {
    if (key === "nb_params" || key === "nb_train_samples")
      return val.toLocaleString("fr-FR");
    if (Number.isInteger(val)) return String(val);
    return val.toFixed(4).replace(/\.?0+$/, "");
  }
  return String(val);
}

function ExtractedTable({ data }: { data: Record<string, unknown> }) {
  const rows = Object.entries(data).filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (rows.length === 0) return null;
  return (
    <div className="mt-2 rounded-md border border-border overflow-hidden">
      <table className="w-full text-xs">
        <tbody>
          {rows.map(([key, val]) => (
            <tr key={key} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
              <td className="px-3 py-1.5 text-muted-foreground font-medium w-1/2">
                {EXTRACTED_LABELS[key] ?? key}
              </td>
              <td className="px-3 py-1.5 font-mono text-foreground">
                {formatExtractedValue(key, val)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StepIcon({ status }: { status: StepStatus }) {
  if (status === "done")    return <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />;
  if (status === "running") return <Loader2     className="h-5 w-5 text-primary animate-spin shrink-0 mt-0.5" />;
  if (status === "error")   return <XCircle     className="h-5 w-5 text-destructive shrink-0 mt-0.5" />;
  return <Circle className="h-5 w-5 text-muted-foreground/40 shrink-0 mt-0.5" />;
}

function NF({
  label, value, onChange, step = "1",
}: { label: string; value: number; onChange: (v: string) => void; step?: string }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs uppercase tracking-wide text-muted-foreground">{label}</Label>
      <Input type="number" step={step} value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

function SliderF({
  label, value, onChange,
}: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs uppercase tracking-wide text-muted-foreground">
        {label} — <span className="font-semibold text-foreground">{(value * 100).toFixed(1)}%</span>
      </Label>
      <Slider value={[value]} min={0} max={1} step={0.01} onValueChange={(v) => onChange(v[0])} />
    </div>
  );
}

function ResultCard({ result }: { result: EvaluateResponse }) {
  return (
    <Card className="mt-6 border-primary/30 shadow-sm">
      <CardContent className="pt-6">
        <div className="flex flex-col md:flex-row md:items-center gap-6">
          <div className="text-center md:text-left">
            <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">AUC prédite</div>
            <div className="text-6xl font-bold tracking-tight tabular-nums">
              {result.auc.toFixed(3)}
            </div>
          </div>
          <div className="flex-1 space-y-2">
            <RiskBadge level={result.risk_level} size="lg" />
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              {result.model_name && (
                <span>Modèle : <span className="font-medium text-foreground">{result.model_name}</span></span>
              )}
              {result.dataset_name && (
                <span>Dataset : <span className="font-medium text-foreground">{result.dataset_name}</span></span>
              )}
              {result.model_used && (
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${
                  result.model_used === "A"
                    ? "bg-green-50 text-green-700 ring-green-600/20"
                    : result.model_used === "B"
                    ? "bg-blue-50 text-blue-700 ring-blue-600/20"
                    : "bg-muted text-muted-foreground ring-border"
                }`}>
                  {result.model_used === "A"
                    ? "Modèle A — précision maximale"
                    : result.model_used === "B"
                    ? "Modèle B — sans accuracy"
                    : "Heuristique"}
                </span>
              )}
            </div>
            <p className="text-sm text-muted-foreground">{result.report}</p>
          </div>
        </div>
        {result.recommendations.length > 0 && (
          <div className="mt-6 pt-5 border-t">
            <h3 className="text-sm font-semibold mb-3">Recommandations</h3>
            <ul className="space-y-2">
              {result.recommendations.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <CheckCircle2 className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
