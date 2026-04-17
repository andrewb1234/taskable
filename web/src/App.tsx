import { AppLayout } from "@/components/AppLayout";
import { WorkspaceProvider } from "@/context/WorkspaceContext";

export default function App() {
  return (
    <WorkspaceProvider>
      <AppLayout />
    </WorkspaceProvider>
  );
}
