/** 模拟后端返回的页面最后一帧截图（SVG data URL）。 */

const PALETTES = [
  { bg: "#f0f9ff", accent: "#0ea5e9", muted: "#bae6fd" },
  { bg: "#fff7ed", accent: "#f97316", muted: "#fed7aa" },
  { bg: "#f0fdf4", accent: "#22c55e", muted: "#bbf7d0" },
  { bg: "#faf5ff", accent: "#a855f7", muted: "#e9d5ff" },
  { bg: "#fef2f2", accent: "#ef4444", muted: "#fecaca" },
];

function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

export function mockBrowserScreenshot(title: string, focusLabel?: string | null): string {
  const palette = PALETTES[hashString(title) % PALETTES.length];
  const focus = focusLabel ? ` · ${focusLabel}` : "";
  const svg = `
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="560" viewBox="0 0 800 560">
  <rect width="800" height="560" fill="${palette.bg}"/>
  <rect x="48" y="40" width="220" height="28" rx="8" fill="${palette.muted}"/>
  <rect x="48" y="96" width="320" height="18" rx="6" fill="${palette.muted}"/>
  <rect x="48" y="132" width="704" height="360" rx="16" fill="white" stroke="${palette.muted}" stroke-width="2"/>
  <rect x="72" y="156" width="200" height="140" rx="12" fill="${palette.muted}" opacity="0.55"/>
  <rect x="296" y="156" width="200" height="140" rx="12" fill="${palette.muted}" opacity="0.55"/>
  <rect x="520" y="156" width="200" height="140" rx="12" fill="${palette.accent}" opacity="0.18" stroke="${palette.accent}" stroke-width="3"/>
  <rect x="72" y="320" width="200" height="140" rx="12" fill="${palette.muted}" opacity="0.55"/>
  <rect x="296" y="320" width="200" height="140" rx="12" fill="${palette.muted}" opacity="0.55"/>
  <text x="48" y="520" fill="${palette.accent}" font-family="system-ui,sans-serif" font-size="22" font-weight="600">${title}</text>
  <text x="48" y="548" fill="#64748b" font-family="system-ui,sans-serif" font-size="14">${focus}</text>
</svg>`.trim();

  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}
