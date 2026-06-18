import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Shield, ShieldAlert, ShieldCheck, ShieldQuestion, ArrowRight, Brain, Lock, History } from "lucide-react";
import { AppShell, PageHeader } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RiskBadge } from "@/components/risk-badge";
import { api } from "@/api/client";
import { useAuth } from "@/lib/auth-context";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "MIA Vulnerability Predictor" },
      { name: "description", content: "Outil IA qui prédit la vulnérabilité d'un Transformer aux attaques MIA." },
    ],
  }),
  component: Home,
});

function Home() {
  const { user } = useAuth();
  const { data: evals } = useQuery({
    queryKey: ["evaluations-home"],
    queryFn: () => api.evaluations(),
    enabled: !!user,
  });

  const recent = evals?.slice(0, 5) ?? [];

  return (
    <AppShell>
      <div className="p-8 lg:p-12 max-w-6xl">
        <PageHeader
          title="MIA Vulnerability Predictor"
          description="Estimez le risque qu'un modèle Transformer soit vulnérable à une attaque par inférence d'appartenance, sans lancer la moindre attaque."
        />

        {/* ── Niveaux de risque ── */}
        <div className="grid md:grid-cols-3 gap-4 mb-10">
          <RiskCard
            color="bg-[color:var(--risk-low)]"
            icon={<ShieldCheck className="h-5 w-5" />}
            label="Risque Faible"
            auc="AUC < 0.55"
            text="Le modèle expose peu d'informations d'appartenance."
          />
          <RiskCard
            color="bg-[color:var(--risk-medium)]"
            icon={<ShieldQuestion className="h-5 w-5" />}
            label="Risque Moyen"
            auc="0.55 ≤ AUC < 0.65"
            text="Vulnérabilité notable, des défenses sont recommandées."
          />
          <RiskCard
            color="bg-[color:var(--risk-high)]"
            icon={<ShieldAlert className="h-5 w-5" />}
            label="Risque Élevé"
            auc="AUC ≥ 0.65"
            text="Le modèle fuit sensiblement l'appartenance d'exemples."
          />
        </div>

        {/* ── Méthode ── */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="h-5 w-5 text-primary" /> Méthode
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground leading-relaxed">
            <p>
              MIA Predictor s'appuie sur un <strong className="text-foreground">méta-modèle</strong> entraîné sur des centaines de
              configurations Transformer (ViT, tabular, text) dont la vulnérabilité MIA réelle a été mesurée. À partir des
              hyperparamètres et des performances de votre modèle, il estime une AUC d'attaque prédite — sans jamais exécuter
              l'attaque.
            </p>
            <p className="flex items-center gap-2">
              <Lock className="h-4 w-4 text-primary" />
              Aucune donnée d'entraînement n'est requise : seuls les méta-paramètres du modèle sont analysés.
            </p>
          </CardContent>
        </Card>

        {/* ── Dernières évaluations ── */}
        {user && (
          <Card className="mb-8">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <History className="h-5 w-5 text-primary" /> Dernières évaluations
              </CardTitle>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/evaluations">Voir tout →</Link>
              </Button>
            </CardHeader>
            <CardContent>
              {recent.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucune évaluation pour l'instant.</p>
              ) : (
                <div className="divide-y">
                  {recent.map((ev) => (
                    <div key={ev.id} className="py-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">
                          {ev.model_name || "Modèle inconnu"}
                        </p>
                        <p className="text-xs text-muted-foreground truncate">
                          {ev.dataset_name || "Dataset inconnu"} · {new Date(ev.created_at).toLocaleString("fr-FR")}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="text-lg font-bold tabular-nums">{ev.auc.toFixed(3)}</span>
                        <RiskBadge level={ev.risk_level} size="sm" />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        <div className="mt-4">
          <Button asChild size="lg">
            <Link to="/evaluate">
              Lancer une évaluation <ArrowRight className="h-4 w-4 ml-2" />
            </Link>
          </Button>
        </div>
      </div>
    </AppShell>
  );
}

function RiskCard({ color, icon, label, auc, text }: {
  color: string; icon: React.ReactNode; label: string; auc: string; text: string;
}) {
  return (
    <Card className="overflow-hidden">
      <div className={`h-1.5 ${color}`} />
      <CardContent className="pt-5">
        <div className={`inline-flex items-center gap-2 text-white px-2.5 py-1 rounded-md text-xs font-medium ${color}`}>
          {icon} {label}
        </div>
        <div className="mt-3 text-sm font-mono text-foreground">{auc}</div>
        <p className="mt-1 text-sm text-muted-foreground">{text}</p>
      </CardContent>
    </Card>
  );
}
