// web/components/Sparkline.tsx
import { sparkPath } from "../lib/sparkline";
import { stateColor } from "../lib/state-colors";

export default function Sparkline({
  ticker,
  state,
  w = 120,
  h = 36,
  color,
}: {
  ticker: string;
  state: string;
  w?: number;
  h?: number;
  color?: string;
}) {
  const strokeColor = color ?? stateColor(state);
  const path = sparkPath(ticker, state, w, h);
  const gradientId = `sg-${ticker}-${state.slice(0, 4)}-${w}`;
  const areaPath = `${path} L${w},${h} L0,${h} Z`;

  return (
    <svg
      className="sparkline"
      viewBox={`0 0 ${w} ${h}`}
      width={w}
      height={h}
      preserveAspectRatio="none"
      aria-label={`${ticker} price trend, ${state.replaceAll("_", " ")}`}
      role="img"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity={0.28} />
          <stop offset="100%" stopColor={strokeColor} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${gradientId})`} />
      <path d={path} stroke={strokeColor} strokeWidth={1.4} fill="none" />
    </svg>
  );
}
