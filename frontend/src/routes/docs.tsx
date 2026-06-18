import { createFileRoute } from "@tanstack/react-router";
import { AppShell, PageHeader } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const Route = createFileRoute("/docs")({
  component: DocsPage,
});

function DocsPage() {
  return (
    <AppShell>
      <div className="p-8 lg:p-12 max-w-3xl space-y-6">
        <PageHeader title="Documentation" description="Comprendre le score, les attaques et les défenses." />

        <Card>
          <CardHeader><CardTitle className="text-base">Le score AUC d'attaque</CardTitle></CardHeader>
          <CardContent className="prose prose-sm text-sm leading-relaxed text-muted-foreground space-y-3">
            <p>
              L'AUC mesure la capacité d'un attaquant à distinguer un exemple <em>membre</em> du jeu d'entraînement
              d'un exemple <em>non-membre</em>. 0.5 = aléatoire (aucune fuite), 1.0 = attaquant parfait.
            </p>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong className="text-foreground">AUC &lt; 0.60</strong> — risque faible.</li>
              <li><strong className="text-foreground">0.60 ≤ AUC &lt; 0.70</strong> — risque moyen.</li>
              <li><strong className="text-foreground">AUC ≥ 0.70</strong> — risque élevé, défense recommandée.</li>
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Les attaques par inférence d'appartenance (MIA)</CardTitle></CardHeader>
          <CardContent className="text-sm leading-relaxed text-muted-foreground space-y-3">
            <p>
              Une attaque MIA cherche à déterminer si un exemple donné a été utilisé pour entraîner le modèle.
              Les principales familles : <strong className="text-foreground">shadow-models</strong> (Shokri et al.),
              <strong className="text-foreground"> LiRA</strong> (Likelihood Ratio Attack, Carlini et al.) et les
              attaques par seuil sur la <strong className="text-foreground">loss</strong> ou la confiance.
            </p>
            <p>
              Plus le modèle <em>mémorise</em> ses exemples (gap train/test élevé, faible régularisation,
              petit dataset), plus l'attaque devient efficace.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Les défenses</CardTitle></CardHeader>
          <CardContent className="text-sm leading-relaxed text-muted-foreground space-y-3">
            <ul className="list-disc pl-5 space-y-2">
              <li><strong className="text-foreground">Régularisation</strong> : dropout, weight decay, early stopping.</li>
              <li><strong className="text-foreground">Data augmentation</strong> : casse la signature par-exemple.</li>
              <li><strong className="text-foreground">DP-SGD</strong> : entraînement à confidentialité différentielle (ε contrôlé).</li>
              <li><strong className="text-foreground">Knowledge distillation</strong> : entraîner un student sur des soft labels.</li>
              <li><strong className="text-foreground">MemGuard</strong> : perturbation des sorties pour brouiller l'attaquant.</li>
              <li><strong className="text-foreground">Plus de données</strong> : effet le plus simple et le plus efficace.</li>
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">À propos de MIA Predictor</CardTitle></CardHeader>
          <CardContent className="text-sm leading-relaxed text-muted-foreground">
            L'outil utilise un méta-modèle entraîné sur un grand nombre de configurations Transformer dont la
            vulnérabilité MIA réelle a été mesurée. Il prédit l'AUC d'attaque sans jamais exécuter d'attaque
            réelle, à partir de vos seuls méta-paramètres.
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}