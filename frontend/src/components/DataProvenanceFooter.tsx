import { useHealth } from '../hooks/useMeta';
import { Alert } from './ui/Alert';

export function DataProvenanceFooter() {
  const { data: health } = useHealth();

  if (!health) return null;

  if (!health.has_data) {
    return (
      <div className="absolute bottom-0 left-0 right-0 z-10 p-2">
        <Alert type="warning" title="No data">
          The backend has no processed data yet — run the ingestion pipeline first.
        </Alert>
      </div>
    );
  }

  const importedAt = health.last_import_finished_at?.slice(0, 10) ?? 'unknown';
  const matchRate =
    health.region_join_match_rate != null ? `${(health.region_join_match_rate * 100).toFixed(2)}%` : 'unknown';

  return (
    <div className="absolute bottom-0 left-0 right-0 z-10 flex justify-center pointer-events-none">
      <div className="pointer-events-auto bg-c3-white/90 rounded-t-lg px-4 py-1.5 text-xs text-c3-greydark border border-b-0 border-c3-greylight">
        Data as of {importedAt} · {matchRate} of units matched to a region
      </div>
    </div>
  );
}
