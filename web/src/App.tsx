import { AppLayout } from "@/components/AppLayout";
import { LoginPage } from "@/components/LoginPage";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { WorkspaceProvider } from "@/context/WorkspaceContext";

function AppInner() {
  const { user, loading } = useAuth();

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

  return (
    <WorkspaceProvider>
      <AppLayout />
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
