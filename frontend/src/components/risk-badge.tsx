import type { RiskLevel } from "@/api/client";

export function RiskBadge({ level, size = "md" }: { level: RiskLevel; size?: "sm" | "md" | "lg" }) {
  const map: Record<RiskLevel, { bg: string; label: string }> = {
    Faible: { bg: "bg-[color:var(--risk-low)]", label: "Risque Faible" },
    Moyen: { bg: "bg-[color:var(--risk-medium)]", label: "Risque Moyen" },
    "Élevé": { bg: "bg-[color:var(--risk-high)]", label: "Risque Élevé" },
  };
  const sizes = {
    sm: "px-2 py-0.5 text-xs",
    md: "px-3 py-1 text-sm",
    lg: "px-4 py-2 text-base",
  };
  const { bg, label } = map[level];
  return (
    <span className={`inline-flex items-center gap-2 rounded-full font-medium text-white ${bg} ${sizes[size]}`}>
      <span className="h-2 w-2 rounded-full bg-white/90" />
      {label}
    </span>
  );
}