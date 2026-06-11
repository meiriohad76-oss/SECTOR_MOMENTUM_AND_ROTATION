// web/lib/sparkline.ts

/**
 * Generates a deterministic SVG path string for a sparkline.
 * Shape encodes the state — no real price data needed.
 * Seeded from the ticker symbol so it's stable across renders.
 */
export function sparkPath(ticker: string, state: string, w: number, h: number): string {
  const N = 60;
  const seed = ticker.split("").reduce((a, c) => a * 31 + c.charCodeAt(0), 7);

  function rnd(i: number): number {
    return ((Math.sin(seed * 9301 + i * 49297) * 233280) % 1 + 1) % 1;
  }

  function shapeY(i: number): number {
    const t = i / (N - 1);
    const s = state.toUpperCase();

    if (s.includes("STAGE_2_BULLISH") || s === "BUY") {
      return 0.15 + 0.7 * t + 0.08 * rnd(i);
    }
    if (s === "HOLD") {
      return 0.30 + 0.4 * t + 0.10 * rnd(i);
    }
    if (s.includes("WARNING") || s === "WARN") {
      if (t < 0.7) return 0.15 + 0.7 * (t / 0.7) + 0.08 * rnd(i);
      return 0.85 - 0.18 * ((t - 0.7) / 0.3) + 0.08 * rnd(i);
    }
    if (s.includes("EXIT")) {
      if (t < 0.55) return 0.15 + 0.7 * (t / 0.55) + 0.08 * rnd(i);
      return 0.85 - 0.45 * ((t - 0.55) / 0.45) + 0.08 * rnd(i);
    }
    if (s.includes("BEARISH") || s === "BEAR") {
      return 0.85 - 0.7 * t + 0.08 * rnd(i);
    }
    // STAGE_1_BASING / default: flat noisy
    return 0.4 + 0.2 * rnd(i);
  }

  const points = Array.from({ length: N }, (_, i) => {
    const x = (i / (N - 1)) * w;
    const y = h - (shapeY(i) * (h - 4) + 2);
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return points.join(" ");
}
