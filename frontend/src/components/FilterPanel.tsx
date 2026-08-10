import { useSizeClasses } from '../hooks/useMeta';
import { useExplorerStore } from '../state/explorerStore';
import { Toggle } from './ui/Toggle';

export function FilterPanel() {
  const tab = useExplorerStore((s) => s.tab);
  const filters = useExplorerStore((s) => s.filters);
  const setMetric = useExplorerStore((s) => s.setMetric);
  const setTimeMode = useExplorerStore((s) => s.setTimeMode);
  const setSizeClasses = useExplorerStore((s) => s.setSizeClasses);
  const { data: sizeClassMeta } = useSizeClasses();

  const generationSizeClasses = sizeClassMeta?.find((m) => m.category === 'generation')?.size_classes ?? [];

  function toggleSizeClass(sizeClass: string, checked: boolean) {
    setSizeClasses(
      checked ? [...filters.sizeClasses, sizeClass] : filters.sizeClasses.filter((existing) => existing !== sizeClass),
    );
  }

  return (
    <div className="space-y-6">
      <Toggle
        enabled={filters.metric === 'capacity'}
        onChange={(enabled) => setMetric(enabled ? 'capacity' : 'count')}
        label="Count / Capacity"
        description="Switch how generation totals are measured"
      />
      <Toggle
        enabled={filters.timeMode === 'period'}
        onChange={(enabled) => setTimeMode(enabled ? 'period' : 'total')}
        label="Total / Period additions"
      />
      {tab === 'generation' && (
        <div className="space-y-2">
          <span id="size-class-label" className="block text-sm font-medium text-c3-text">
            Size class
          </span>
          <div role="group" aria-labelledby="size-class-label" className="space-y-2">
            {generationSizeClasses.map((sizeClass) => (
              <label key={sizeClass} className="flex items-center gap-2 text-sm text-c3-text">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-c3-greylight accent-c3-bluegreen focus:outline-none focus:ring-2 focus:ring-c3-bluegreen"
                  checked={filters.sizeClasses.includes(sizeClass)}
                  onChange={(e) => toggleSizeClass(sizeClass, e.target.checked)}
                />
                {sizeClass}
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
