interface ToggleProps {
  enabled: boolean;
  onChange: (next: boolean) => void;
  label?: string;
  description?: string;
}

export function Toggle({ enabled, onChange, label, description }: ToggleProps) {
  return (
    <div className="flex items-start space-x-3">
      <button
        type="button"
        role="button"
        aria-pressed={enabled}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-c3-bluegreen focus:ring-offset-2 ${enabled ? 'bg-c3-bluegreen' : 'bg-c3-greylight'}`}
        onClick={() => onChange(!enabled)}
      >
        <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${enabled ? 'translate-x-6' : 'translate-x-1'}`} />
      </button>
      {(label || description) && (
        <div className="flex-1">
          {label && <label className="block text-sm font-medium text-c3-text">{label}</label>}
          {description && <p className="text-xs text-c3-greydark mt-1">{description}</p>}
        </div>
      )}
    </div>
  );
}
