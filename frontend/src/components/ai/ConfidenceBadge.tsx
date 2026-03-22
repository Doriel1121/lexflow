interface ConfidenceBadgeProps {
  score: number; // 0.0 – 1.0
  showLabel?: boolean;
  size?: 'sm' | 'md';
}

export function ConfidenceBadge({ score, showLabel = true, size = 'sm' }: ConfidenceBadgeProps) {
  const pct = Math.round(score * 100);

  let label: string;
  let colorClass: string;
  let barColor: string;

  if (score >= 0.7) {
    label = 'High';
    colorClass = 'text-emerald-600 bg-emerald-50';
    barColor = 'bg-emerald-400';
  } else if (score >= 0.4) {
    label = 'Medium';
    colorClass = 'text-amber-600 bg-amber-50';
    barColor = 'bg-amber-400';
  } else {
    label = 'Low';
    colorClass = 'text-red-600 bg-red-50';
    barColor = 'bg-red-400';
  }

  const textSize = size === 'sm' ? 'text-[10px]' : 'text-xs';
  const padding = size === 'sm' ? 'px-1.5 py-0.5' : 'px-2 py-1';

  return (
    <div className={`inline-flex items-center gap-1.5 ${padding} rounded-full ${colorClass} ${textSize} font-bold`} title={`AI Confidence: ${pct}%`}>
      {/* Mini progress bar */}
      <div className="w-8 h-1.5 bg-white/50 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${barColor} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && <span>{label}</span>}
      <span className="opacity-60">{pct}%</span>
    </div>
  );
}
