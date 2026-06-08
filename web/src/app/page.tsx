import { loadMonitorData } from "@/lib/data";
import { ja } from "@/lib/i18n";
import Dashboard from "@/components/Dashboard";

// Read the event store on every request so a fresh pipeline run shows up
// without a rebuild.
export const dynamic = "force-dynamic";

export default async function Page() {
  const data = await loadMonitorData();

  return (
    <div className="app">
      <header className="app__header">
        <h1 className="app__title">{ja.appTitle}</h1>
        <p className="app__subtitle">{ja.appSubtitle}</p>
      </header>
      <Dashboard data={data} />
      <footer className="app__footer">
        {ja.dataSources}: {ja.dataSourcesList}
      </footer>
    </div>
  );
}
