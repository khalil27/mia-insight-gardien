import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { AppShell, PageHeader } from "@/components/app-shell";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/api/client";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";

export const Route = createFileRoute("/insights")({
  component: InsightsPage,
});

function InsightsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["feature-importance"],
    queryFn: () => api.featureImportance(),
  });

  return (
    <AppShell>
      <div className="p-8 lg:p-12 max-w-5xl">
        <PageHeader
          title="Model Insights"
          description="Importance des features dans le méta-modèle qui prédit l'AUC d'attaque MIA."
        />
        <Card>
          <CardContent className="pt-6">
            {isLoading && <div className="h-80 flex items-center justify-center text-sm text-muted-foreground">Chargement…</div>}
            {error && <div className="text-sm text-destructive">Erreur de chargement.</div>}
            {data && (
              <div className="h-[420px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data} layout="vertical" margin={{ left: 40, right: 24, top: 8, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis type="number" stroke="var(--muted-foreground)" fontSize={12} />
                    <YAxis type="category" dataKey="feature" stroke="var(--muted-foreground)" fontSize={12} width={140} />
                    <Tooltip
                      contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
                      formatter={(v: number) => v.toFixed(3)}
                    />
                    <Bar dataKey="importance" radius={[0, 6, 6, 0]}>
                      {data.map((_, i) => (
                        <Cell key={i} fill="var(--primary)" />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}