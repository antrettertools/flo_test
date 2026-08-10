import { DataProvenanceFooter } from './components/DataProvenanceFooter';
import { MapView } from './components/MapView/MapView';
import { SidePanel } from './components/SidePanel';
import { useExplorerStore } from './state/explorerStore';
import type { Tab } from './state/explorerStore';

const TABS: { id: Tab; label: string }[] = [
  { id: 'generation', label: 'Generation' },
  { id: 'storage', label: 'Storage' },
];

function App() {
  const tab = useExplorerStore((s) => s.tab);
  const setTab = useExplorerStore((s) => s.setTab);

  return (
    <div className="relative h-screen w-screen overflow-hidden">
      <header className="absolute top-0 left-0 right-0 z-10 flex items-center gap-4 bg-c3-white/90 px-4 py-2 shadow-sm">
        <h1 className="text-lg font-semibold">Renewable Capacity Explorer</h1>
        <div role="tablist" className="ml-auto flex gap-1 rounded-lg border border-c3-greylight p-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => setTab(t.id)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                tab === t.id ? 'bg-c3-bluegreen text-c3-white' : 'text-c3-greydark hover:bg-c3-greylight'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </header>

      <div className="absolute inset-0 z-0">
        <MapView />
      </div>

      <div className="pointer-events-none absolute top-16 right-4 bottom-16 z-10">
        <SidePanel />
      </div>

      <DataProvenanceFooter />
    </div>
  );
}

export default App;
