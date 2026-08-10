import { useExplorerStore } from '../state/explorerStore';

interface BreadcrumbProps {
  landName?: string;
  kreisName?: string;
}

export function Breadcrumb({ landName, kreisName }: BreadcrumbProps) {
  const selection = useExplorerStore((s) => s.selection);
  const selectNational = useExplorerStore((s) => s.selectNational);
  const selectLand = useExplorerStore((s) => s.selectLand);

  const segments: { label: string; onClick?: () => void }[] = [
    { label: 'Germany', onClick: selection.level !== 'national' ? selectNational : undefined },
  ];
  if (selection.landAgs && landName) {
    segments.push({
      label: landName,
      onClick: selection.level === 'kreis' ? () => selectLand(selection.landAgs!) : undefined,
    });
  }
  if (selection.kreisAgs && kreisName) {
    segments.push({ label: kreisName });
  }

  return (
    <nav className="flex items-center gap-3 text-sm">
      {segments.map((segment, i) => (
        <span key={segment.label} className="flex items-center gap-3">
          {i > 0 && <span className="text-c3-grey">{'>'}</span>}
          {segment.onClick ? (
            <button onClick={segment.onClick} className="text-c3-bluegreen hover:underline">
              {segment.label}
            </button>
          ) : (
            <span className="font-medium text-c3-text">{segment.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
