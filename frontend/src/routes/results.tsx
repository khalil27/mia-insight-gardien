import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { AppShell, PageHeader } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/api/client";
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  BarChart, Bar, Cell,
} from "recharts";

export const Route = createFileRoute("/results")({
  component: ResultsPage,
});

const MOD_COLORS: Record<string, string> = {
  image: "var(--primary)",
  tabular: "oklch(0.55 0.18 280)",
  text: "oklch(0.7 0.17 50)",
};

function ResultsPage() {
  const { data, isLoading } = useQuery({ queryKey: ["results-summary"], queryFn: () => api.resultsSummary() });

  return (
    <AppShell>
      <div className="p-8 lg:p-12 max-w-6xl space-y-6">
        <PageHeader
          title="Résultats"
          description={data ? `${data.runs} runs d'entraînement analysés.` : "Vue d'ensemble des runs."}
        />

        <Card>
          <CardHeader><CardTitle className="text-base">Gap train/test vs AUC d'attaque</CardTitle></CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-80 flex items-center justify-center text-sm text-muted-foreground">Chargement…</div>
            ) : (
              <div className="h-[400px]">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ left: 12, right: 24, top: 12, bottom: 24 }}>
                    <CartesianGrid stroke="var(--border)" />
                    <XAxis type="number" dataKey="gap" name="Gap" stroke="var(--muted-foreground)" fontSize={12}
                      label={{ value: "train_test_gap", position: "insideBottom", offset: -10, fontSize: 12 }} />
                    <YAxis type="number" dataKey="auc" name="AUC" stroke="var(--muted-foreground)" fontSize={12}
                      domain={[0.5, 1]}
                      label={{ value: "AUC", angle: -90, position: "insideLeft", fontSize: 12 }} />
                    <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }} />
                    <Legend />
                    {(["image", "tabular", "text"] as const).map((m) => (
                      <Scatter
                        key={m} name={m}
                        data={data?.gap_vs_auc.filter((p) => p.modality === m) || []}
                        fill={MOD_COLORS[m]}
                      />
                    ))}
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Distribution des AUC observées</CardTitle></CardHeader>
          <CardContent>
            {data && (
              <div className="h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={data.auc_histogram.map((c, i) => ({
                      bin: `${(0.5 + i * 0.05).toFixed(2)}`,
                      count: c,
                    }))}
                    margin={{ left: 12, right: 24, top: 12, bottom: 12 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="bin" stroke="var(--muted-foreground)" fontSize={12} />
                    <YAxis stroke="var(--muted-foreground)" fontSize={12} />
                    <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }} />
                    <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                      {data.auc_histogram.map((_, i) => (
                        <Cell key={i} fill={i < 2 ? "var(--risk-low)" : i < 4 ? "var(--risk-medium)" : "var(--risk-high)"} />
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