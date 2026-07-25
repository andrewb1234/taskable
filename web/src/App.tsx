import { useState } from "react";
import { AppLayout } from "@/components/AppLayout";
import { LoginPage } from "@/components/LoginPage";
import { ProfilePage } from "@/components/ProfilePage";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { WorkspaceProvider } from "@/context/WorkspaceContext";

const INVITATION_STORAGE_KEY = "mouvadah.pending-invitation";

function readPendingInvitation(): string | null {
  const fragment = new URLSearchParams(window.location.hash.slice(1));
  const token = fragment.get("invite");
  if (token) {
    window.sessionStorage.setItem(INVITATION_STORAGE_KEY, token);
    window.history.replaceState(
      {},
      "",
      `${window.location.pathname}${window.location.search}`,
    );
  }
  return token ?? window.sessionStorage.getItem(INVITATION_STORAGE_KEY);
}

function AppInner() {
  const { user, loading, logout } = useAuth();
  const [invitationToken, setInvitationToken] = useState<string | null>(
    readPendingInvitation,
  );
  const [view, setView] = useState<"workspace" | "profile">(
    invitationToken ? "profile" : "workspace",
  );

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
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
