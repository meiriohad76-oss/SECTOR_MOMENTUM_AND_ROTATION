// web/app/page.tsx
import { fetchDashboardSnapshot, fetchBacktestArtifacts, fetchDebrief } from "../lib/api";
import DisplayShell from "../components/DisplayShell";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function HomePage() {
  const [snapshotResult, backtestResult, debriefResult] = await Promise.all([
    fetchDashboardSnapshot(),
    fetchBacktestArtifacts(),
    fetchDebrief(),
  ]);
  return (
    <main>
      <DisplayShell
        snapshot={snapshotResult.data}
        backtestArtifacts={backtestResult.data}
        backtestError={backtestResult.error}
        debriefData={debriefResult.data}
      />
    </main>
  );
}
