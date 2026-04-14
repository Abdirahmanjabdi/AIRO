import { useId } from "react";

interface Props {
  score: number;
  threshold: number;
}

export default function RiskGauge({ score, threshold }: Props) {
  const glowId = useId();
  const size = 340;
  const cx = size / 2;
  const cy = size / 2 + 10;
  const outerR = 145;
  const innerR = 120;
  const arcR = 128;
  const startAngle = 225;
  const endAngle = -45;
  const totalSweep = 270;

  function polarToCartesian(centerX: number, centerY: number, r: number, angleDeg: number) {
    const rad = ((angleDeg - 90) * Math.PI) / 180;
    return { x: centerX + r * Math.cos(rad), y: centerY + r * Math.sin(rad) };
  }

  function describeArc(r: number, startA: number, sweepDeg: number) {
    const start = polarToCartesian(cx, cy, r, startA);
    const end = polarToCartesian(cx, cy, r, startA - sweepDeg);
    const largeArc = sweepDeg > 180 ? 1 : 0;
    return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`;
  }

  const scoreSweep = Math.min(score, 1) * totalSweep;
  const thresholdAngle = startAngle - threshold * totalSweep;
  const isAlert = score > threshold;
  const fillColor = isAlert ? '#E63946' : score > 0.4 ? '#F5A623' : '#4ECDC4';

  // Tick marks every 0.05 (20 ticks)
  const ticks = [];
  for (let i = 0; i <= 20; i++) {
    const angle = startAngle - (i / 20) * totalSweep;
    const isMajor = i % 4 === 0;
    const inner = polarToCartesian(cx, cy, outerR - (isMajor ? 10 : 5), angle);
    const outer = polarToCartesian(cx, cy, outerR, angle);
    ticks.push(
      <line
        key={`tick-${i}`}
        x1={inner.x} y1={inner.y}
        x2={outer.x} y2={outer.y}
        stroke={isMajor ? 'hsl(220 8% 28%)' : 'hsl(220 8% 18%)'}
        strokeWidth={isMajor ? 1.5 : 0.5}
      />
    );
    // Labels at major ticks
    if (isMajor) {
      const label = polarToCartesian(cx, cy, outerR + 14, angle);
      ticks.push(
        <text
          key={`label-${i}`}
          x={label.x} y={label.y}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="hsl(220 8% 32%)"
          fontSize="8"
          fontFamily="Space Mono, monospace"
        >
          {(i * 0.05).toFixed(2)}
        </text>
      );
    }
  }

  // Threshold marker
  const threshP1 = polarToCartesian(cx, cy, innerR - 8, thresholdAngle);
  const threshP2 = polarToCartesian(cx, cy, outerR - 2, thresholdAngle);

  return (
    <div className="relative flex items-center justify-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="select-none">
        <defs>
          <filter id={glowId}>
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          <linearGradient id={`${glowId}-ring`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#111827" />
            <stop offset="100%" stopColor="#0b1220" />
          </linearGradient>
        </defs>

        <circle cx={cx} cy={cy} r={innerR - 16} fill={`url(#${glowId}-ring)`} opacity={0.92} />
        <circle cx={cx} cy={cy} r={innerR - 2} fill="none" stroke="rgba(255,255,255,0.05)" />

        {/* Outer ring ticks */}
        {ticks}

        {/* Background arc */}
        <path
          d={describeArc(arcR, startAngle, totalSweep)}
          fill="none"
          stroke="hsl(224 14% 10%)"
          strokeWidth={8}
          strokeLinecap="round"
        />

        {/* Score arc with glow */}
        <path
          d={describeArc(arcR, startAngle, scoreSweep)}
          fill="none"
          stroke={fillColor}
          strokeWidth={8}
          strokeLinecap="round"
          filter={`url(#${glowId})`}
          className="transition-all duration-700 ease-out"
          style={{ filter: `drop-shadow(0 0 6px ${fillColor}40)` }}
        />

        {/* Threshold line */}
        <line
          x1={threshP1.x} y1={threshP1.y}
          x2={threshP2.x} y2={threshP2.y}
          stroke="#F5A623"
          strokeWidth={2}
          strokeDasharray="3 2"
        />

        {/* Center score */}
        <text
          x={cx} y={cy - 12}
          textAnchor="middle"
          dominantBaseline="middle"
          fill={fillColor}
          fontSize="56"
          fontFamily="Space Mono, monospace"
          fontWeight="bold"
          style={{ filter: `drop-shadow(0 0 12px ${fillColor}30)` }}
        >
          {score.toFixed(2)}
        </text>

        {/* Sub-label */}
        <text
          x={cx} y={cy + 28}
          textAnchor="middle"
          fill="hsl(220 8% 32%)"
          fontSize="10"
          fontFamily="Space Mono, monospace"
          letterSpacing="0.15em"
        >
          RISK INDEX
        </text>

        {/* Threshold label */}
        <text
          x={cx} y={cy + 48}
          textAnchor="middle"
          fill="#F5A623"
          fontSize="9"
          fontFamily="Space Mono, monospace"
          letterSpacing="0.12em"
          opacity={0.8}
        >
          THRESHOLD: {threshold.toFixed(4)}
        </text>

        <text
          x={cx}
          y={cy + 70}
          textAnchor="middle"
          fill="hsl(220 8% 44%)"
          fontSize="8"
          fontFamily="Space Mono, monospace"
          letterSpacing="0.22em"
        >
          PERSONALIZED MODEL
        </text>
      </svg>
    </div>
  );
}
