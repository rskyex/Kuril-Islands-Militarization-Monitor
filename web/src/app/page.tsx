import { loadMonitorData } from "@/lib/data";
import { ja } from "@/lib/i18n";
import Dashboard from "@/components/Dashboard";

// Prerender the page to static HTML at build (data is bundled, so it never
// needs the filesystem) and refresh periodically via ISR. This keeps the home
// route served as a static asset on serverless hosts — robust against function
// issues — while still picking up live pipeline output on a self-hosted server
// within the revalidate window.
export const revalidate = 300;

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
