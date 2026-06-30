import { useState } from "react";
import { AppLayout } from "@/components/AppLayout";
import { LoginPage } from "@/components/LoginPage";
import { ProfilePage } from "@/components/ProfilePage";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { WorkspaceProvider } from "@/context/WorkspaceContext";

function AppInner() {
  const { user, loading } = useAuth();
  const [view, setView] = useState<"workspace" | "profile">("workspace");

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
    return <ProfilePage onBack={() => setView("workspace")} />;
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
