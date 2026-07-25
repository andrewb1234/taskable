import { useCallback, useEffect, useState } from "react";
import { AppLayout } from "@/components/AppLayout";
import { LoginPage } from "@/components/LoginPage";
import { LandingPage } from "@/components/marketing/LandingPage";
import { ProfilePage } from "@/components/ProfilePage";
import { MouvadahLockup } from "@/components/brand/mouvadah-brand";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { WorkspaceProvider } from "@/context/WorkspaceContext";

const INVITATION_STORAGE_KEY = "mouvadah.pending-invitation";
type AppPath = "/" | "/app";

function readPendingInvitation(): string | null {
  const fragment = new URLSearchParams(window.location.hash.slice(1));
  const token = fragment.get("invite");

  if (token) {
    window.sessionStorage.setItem(INVITATION_STORAGE_KEY, token);
  }

  const pendingInvitation =
    token ?? window.sessionStorage.getItem(INVITATION_STORAGE_KEY);

  if (pendingInvitation && window.location.pathname !== "/app") {
    window.history.replaceState({}, "", `/app${window.location.search}`);
  } else if (token) {
    window.history.replaceState({}, "", `/app${window.location.search}`);
  }

  return pendingInvitation;
}

function readAppPath(): AppPath {
  return window.location.pathname === "/app" ? "/app" : "/";
}

function RouteLoading() {
  return (
    <main
      data-surface="marketing"
      className="flex min-h-screen items-center justify-center bg-background px-6 text-foreground"
    >
      <div className="motion-enter flex flex-col items-center gap-5 text-center">
        <MouvadahLockup size="lg" />
        <div className="space-y-2">
          <p className="technical-label">Resolving workspace state</p>
          <p className="text-sm text-muted-foreground">
            Checking the current browser session…
          </p>
        </div>
        <div
          className="h-px w-40 overflow-hidden bg-border"
          aria-hidden="true"
        >
          <span className="motion-continuous block h-full w-1/2 animate-shimmer bg-brand-brass" />
        </div>
      </div>
    </main>
  );
}

function AppInner() {
  const { user, loading, logout } = useAuth();
  const [invitationToken, setInvitationToken] = useState<string | null>(
    readPendingInvitation,
  );
  const [path, setPath] = useState<AppPath>(readAppPath);
  const [view, setView] = useState<"workspace" | "profile">(
    invitationToken ? "profile" : "workspace",
  );

  const navigate = useCallback((nextPath: AppPath, replace = false) => {
    const target = `${nextPath}${window.location.search}`;
    if (replace) {
      window.history.replaceState({}, "", target);
    } else {
      window.history.pushState({}, "", target);
    }
    setPath(nextPath);
  }, []);

  useEffect(() => {
    const onPopState = () => setPath(readAppPath());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    if (!loading && user && path !== "/app") {
      navigate("/app", true);
    }
  }, [loading, navigate, path, user]);

  if (loading) {
    return <RouteLoading />;
  }

  if (user && path !== "/app") {
    return <RouteLoading />;
  }

  if (!user) {
    if (path === "/") {
      return <LandingPage onOpenApp={() => navigate("/app")} />;
    }
    return <LoginPage onBackToLanding={() => navigate("/")} />;
  }

  if (view === "profile") {
    return (
      <ProfilePage
        onBack={() => setView("workspace")}
        pendingInvitationToken={invitationToken}
        onInvitationHandled={() => {
          window.sessionStorage.removeItem(INVITATION_STORAGE_KEY);
          setInvitationToken(null);
        }}
        onInvitationTerminalFailure={() => {
          window.sessionStorage.removeItem(INVITATION_STORAGE_KEY);
        }}
        onInvitationSwitchAccount={async () => {
          if (invitationToken) {
            window.sessionStorage.setItem(
              INVITATION_STORAGE_KEY,
              invitationToken,
            );
          }
          await logout();
        }}
      />
    );
  }

  return (
    <WorkspaceProvider>
      <AppLayout onNavigateProfile={() => setView("profile")} />
    </WorkspaceProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}
