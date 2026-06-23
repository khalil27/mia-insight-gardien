import { Link, useRouterState } from "@tanstack/react-router";
import { Shield, Home, FlaskConical, LineChart, BookOpen, LogOut, History } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";

const items = [
  { title: "Accueil",        url: "/",            icon: Home },
  { title: "Évaluation",    url: "/evaluate",    icon: FlaskConical },
  { title: "Historique",    url: "/evaluations", icon: History },
  { title: "Résultats",     url: "/results",     icon: LineChart },
  { title: "Documentation", url: "/docs",        icon: BookOpen },
] as const;

export function AppSidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { user, logout } = useAuth();

  return (
    <aside className="hidden md:flex w-64 shrink-0 flex-col bg-sidebar text-sidebar-foreground border-r border-sidebar-border">
      <div className="px-6 py-6 flex items-center gap-2 border-b border-sidebar-border">
        <div className="h-9 w-9 rounded-lg bg-primary/15 flex items-center justify-center">
          <Shield className="h-5 w-5 text-primary" />
        </div>
        <div>
          <div className="font-semibold tracking-tight">MIA Insight Gardien</div>
          <div className="text-xs text-sidebar-foreground/60">Vulnerability AI</div>
        </div>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {items.map((it) => {
          const active = pathname === it.url;
          return (
            <Link
              key={it.url}
              to={it.url}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
              }`}
            >
              <it.icon className="h-4 w-4" />
              {it.title}
            </Link>
          );
        })}
      </nav>
      <div className="p-3 border-t border-sidebar-border space-y-2">
        {user && (
          <div className="px-3 py-2 text-xs text-sidebar-foreground/70 truncate">
            {user.email}
          </div>
        )}
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-foreground"
          onClick={logout}
        >
          <LogOut className="h-4 w-4 mr-2" /> Se déconnecter
        </Button>
      </div>
    </aside>
  );
}