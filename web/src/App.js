import { jsx as _jsx } from "react/jsx-runtime";
import { AppLayout } from "@/components/AppLayout";
import { WorkspaceProvider } from "@/context/WorkspaceContext";
export default function App() {
    return (_jsx(WorkspaceProvider, { children: _jsx(AppLayout, {}) }));
}
