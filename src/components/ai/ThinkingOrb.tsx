/**
 * 等待态 Orb（对齐 OpenDesign ThinkingOrb 观感，精简版）。
 */

import { useEffect, useRef } from "react";

const SIZE = 18;

/** Composer / 时间线底：Agent 工作时的旋转点球。 */
export function ThinkingOrb({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.round(SIZE * dpr);
    canvas.height = Math.round(SIZE * dpr);
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduce =
      typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

    const draw = (t: number) => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, SIZE, SIZE);
      const cx = SIZE / 2;
      const cy = SIZE / 2;
      const r = SIZE * 0.32;
      const n = 10;
      for (let i = 0; i < n; i++) {
        const a = t * 2.2 + (i / n) * Math.PI * 2;
        const x = cx + Math.cos(a) * r;
        const y = cy + Math.sin(a) * r * 0.72;
        const depth = (Math.sin(a + t) + 1) / 2;
        const ink = Math.round(90 + depth * 140);
        ctx.fillStyle = `rgba(${ink},${ink},${ink},${0.35 + depth * 0.55})`;
        ctx.beginPath();
        ctx.arc(x, y, 1.1 + depth * 1.4, 0, Math.PI * 2);
        ctx.fill();
      }
    };

    if (reduce) {
      draw(0.6);
      return;
    }

    let raf = 0;
    let running = true;
    const loop = () => {
      draw(performance.now() / 1000);
      if (running) raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      running = false;
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      role="img"
      aria-label="工作中"
      className={className}
      style={{ width: SIZE, height: SIZE, display: "block" }}
    />
  );
}
