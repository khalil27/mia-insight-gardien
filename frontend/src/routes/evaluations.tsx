import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell, PageHeader } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RiskBadge } from "@/components/risk-badge";
import { api, type EvaluationRecord } from "@/api/client";
import { CheckCircle2, ChevronDown, ChevronUp, FileText, Database, Calendar } from "lucide-react";

export const Route = createFileRoute("/evaluations")({
  component: EvaluationsPage,
});

function EvaluationsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["evaluations"],
    queryFn: () => api.evaluations(),
  });

  return (
    <AppShell>
      <div className="p-8 lg:p-12 max-w-5xl">
        <PageHeader
          title="Historique des évaluations"
          description="Toutes vos évaluations enregistrées, de la plus récente à la plus ancienne."
        />

        {isLoading && (
          <div className="text-sm text-muted-foreground animate-pulse">Chargement…</div>
        )}
        {error && (
          <div className="text-sm text-destructive">Erreur de chargement des évaluations.</div>
        )}
        {data && data.length === 0 && (
          <Card>
            <CardContent className="pt-6 text-sm text-muted-foreground">
              Aucune évaluation pour l'instant. Lancez votre première évaluation depuis la page <strong>Évaluation</strong>.
            </CardContent>
          </Card>
        )}
        {data && data.length > 0 && (
          <div className="space-y-4">
            {data.map((ev) => (
              <EvalCard key={ev.id} ev={ev} />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}

function EvalCard({ ev }: { ev: EvaluationRecord }) {
  const [open, setOpen] = useState(false);

  return (
    <Card className="overflow-hidden">
      {/* ── Header ── */}
      <button
        className="w-full text-left"
        onClick={() => setOpen((v) => !v)}
      >
        <CardHeader className="pb-3">
          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
            {/* Info principale */}
            <div className="flex-1 min-w-0 space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="font-semibold text-sm truncate">
                  {ev.model_name || "Modèle inconnu"}
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
                <Database className="h-3 w-3 shrink-0" />
                <span className="truncate">{ev.dataset_name || "Dataset inconnu"}</span>
                <span className="opacity-40">·</span>
                <Calendar className="h-3 w-3 shrink-0" />
                <span>{new Date(ev.created_at).toLocaleString("fr-FR")}</span>
              </div>
            </div>

            {/* Score + badge */}
            <div className="flex items-center gap-3 shrink-0">
              <span className="text-2xl font-bold tabular-nums">{ev.auc.toFixed(3)}</span>
              <RiskBadge level={ev.risk_level} size="md" />
              {open
                ? <ChevronUp className="h-4 w-4 text-muted-foreground" />
                : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
            </div>
          </div>
        </CardHeader>
      </button>

      {/* ── Détail dépliant ── */}
      {open && (
        <CardContent className="border-t pt-4 space-y-5">

          {/* Rapport */}
          <div>
            <h4 className="text-xs uppercase tracking-wide text-muted-foreground mb-1">Rapport</h4>
            <p className="text-sm">{ev.report}</p>
          </div>

          {/* Recommandations */}
          <div>
            <h4 className="text-xs uppercase tracking-wide text-muted-foreground mb-2">Recommandations</h4>
            <ul className="space-y-1.5">
              {ev.recommendations.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <CheckCircle2 className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Paramètres du modèle */}
          <div>
            <h4 className="text-xs uppercase tracking-wide text-muted-foreground mb-2">Paramètres utilisés</h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-6 gap-y-1.5 text-xs">
              {[
                ["Type modèle",   ev.input.model_type],
                ["Modalité",      ev.input.dataset_modality],
                ["depth",         ev.input.depth],
                ["num_heads",     ev.input.num_heads],
                ["embed_dim",     ev.input.embed_dim],
                ["nb_params",     ev.input.nb_params?.toLocaleString() ?? "—"],
                ["epochs",        ev.input.epochs],
                ["learning_rate", ev.input.learning_rate],
                ["batch_size",    ev.input.batch_size],
                ["dropout",       ev.input.dropout],
                ["weight_decay",  ev.input.weight_decay],
                ["data_aug.",     ev.input.data_augmentation ? "oui" : "non"],
                ["nb_samples",    ev.input.nb_train_samples?.toLocaleString() ?? "—"],
                ["nb_classes",    ev.input.nb_classes],
                ["train_acc",     ev.input.train_accuracy != null ? ev.input.train_accuracy.toFixed(2) : "—"],
                ["test_acc",      ev.input.test_accuracy  != null ? ev.input.test_accuracy.toFixed(2)  : "—"],
              ].map(([k, v]) => (
                <div key={String(k)} className="flex justify-between gap-2 border-b border-border/40 py-0.5">
                  <span className="text-muted-foreground">{k}</span>
                  <span className="font-medium tabular-nums">{String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  );
}
