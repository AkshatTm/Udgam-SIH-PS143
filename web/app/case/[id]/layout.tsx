// The persistent layout for a case. It stays mounted while the [stage] child route changes,
// so the workspace — and MapView inside it — is never torn down on stage navigation.

import CaseWorkspace from "@/components/CaseWorkspace";

export default function CaseLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="h-full">
      <CaseWorkspace />
      {children}
    </div>
  );
}
