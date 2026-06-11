// web/app/page.tsx
import { fetchDashboardSnapshot } from "../lib/api";
import DisplayShell from "../components/DisplayShell";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function HomePage() {
  const result = await fetchDashboardSnapshot();
  return (
    <main>
      <DisplayShell snapshot={result.data} />
    </main>
  );
}
