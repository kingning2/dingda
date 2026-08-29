import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { COLORS, FONT_BODY, FONT_DISPLAY, FONT_MONO } from './theme';

/** 场景内局部时间轴工具：以 scene 起始帧为 0，提供入场动画。 */
export function useScene(start: number) {
  const frame = useCurrentFrame();
  const t = frame - start;

  /** 淡入（可延迟）。 */
  const fade = (delay = 0, dur = 12) =>
    interpolate(t, [delay, delay + dur], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });

  /** 上滑淡入，返回 style。 */
  const rise = (delay = 0, dur = 18, dist = 36) => {
    const p = interpolate(t, [delay, delay + dur], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
    const e = Easing.out(Easing.cubic)(p);
    return { opacity: e, transform: `translateY(${(1 - e) * dist}px)` };
  };

  /** 缩放淡入，返回 style。 */
  const pop = (delay = 0, dur = 20, from = 0.9) => {
    const p = interpolate(t, [delay, delay + dur], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
    const e = Easing.out(Easing.back(1.6))(p);
    return { opacity: e, transform: `scale(${from + (1 - from) * e})` };
  };

  return { t, fade, rise, pop };
}

/** 整段场景的淡出（结尾）。 */
export function sceneFadeOut(start: number, duration: number) {
  const frame = useCurrentFrame();
  return interpolate(frame, [start + duration - 14, start + duration], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
}

/** 场景背景：暖色渐变 + 光晕 + 网格纹理。 */
export function SceneBackdrop({ accent }: { accent?: string }) {
  const { width, height } = useVideoConfig();
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(120% 90% at 78% 12%, #FFF7E3 0%, ${COLORS.bg} 46%, #EBDCB6 100%)`,
      }}
    >
      <AbsoluteFill
        style={{
          background: `radial-gradient(46% 34% at 76% 20%, ${
            accent ?? COLORS.accent
          }2e, transparent 70%)`,
        }}
      />
      <AbsoluteFill
        style={{
          opacity: 0.5,
          backgroundImage: `linear-gradient(${COLORS.line}26 1px, transparent 1px), linear-gradient(90deg, ${COLORS.line}26 1px, transparent 1px)`,
          backgroundSize: `${width / 16}px ${height / 9}px`,
          maskImage: 'radial-gradient(90% 90% at 70% 20%, #000 30%, transparent 85%)',
          WebkitMaskImage: 'radial-gradient(90% 90% at 70% 20%, #000 30%, transparent 85%)',
        }}
      />
    </AbsoluteFill>
  );
}

/** 场景文案块（左 60%）。 */
export function TextBlock({
  eyebrow,
  title,
  sub,
  accent,
  start,
  chips,
}: {
  eyebrow: string;
  title: string;
  sub: string;
  accent: string;
  start: number;
  chips?: string[];
}) {
  const { rise, pop } = useScene(start);
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        top: 0,
        width: '62%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        padding: '0 0 0 9vw',
        zIndex: 2,
      }}
    >
      <div
        style={{
          ...rise(0),
          fontFamily: FONT_MONO,
          fontSize: 26,
          letterSpacing: '0.3em',
          textTransform: 'uppercase',
          color: accent,
          fontWeight: 700,
        }}
      >
        {eyebrow}
      </div>
      <div
        style={{
          ...rise(4, 20, 44),
          marginTop: 18,
          fontFamily: FONT_DISPLAY,
          fontWeight: 800,
          fontSize: 76,
          lineHeight: 1.16,
          letterSpacing: '0.01em',
          color: COLORS.ink,
          maxWidth: 900,
        }}
      >
        {title}
      </div>
      <div
        style={{
          ...rise(9, 20, 40),
          marginTop: 26,
          fontFamily: FONT_BODY,
          fontSize: 32,
          lineHeight: 1.6,
          color: COLORS.inkSoft,
          maxWidth: 760,
        }}
      >
        {sub}
      </div>
      {chips ? (
        <div style={{ display: 'flex', gap: 16, marginTop: 40, flexWrap: 'wrap' }}>
          {chips.map((chip, i) => (
            <div
              key={chip}
              style={{
                ...pop(12 + i * 4, 16, 0.92),
                fontFamily: FONT_BODY,
                fontSize: 24,
                fontWeight: 600,
                color: accent,
                background: '#FFFFFFE6',
                border: `2px solid ${accent}40`,
                borderRadius: 999,
                padding: '10px 24px',
              }}
            >
              {chip}
            </div>
          ))}
        </div>
      ) : null}
      {/* 淡出用于衔接 */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          opacity: 0,
          pointerEvents: 'none',
          display: 'none',
        }}
      />
    </div>
  );
}

/** 场景包装：首尾淡入淡出实现平滑切换。 */
export function Scene({
  start,
  duration,
  children,
}: {
  start: number;
  duration: number;
  children: React.ReactNode;
}) {
  const frame = useCurrentFrame();
  const opacity = interpolate(
    frame,
    [start, start + 12, start + duration - 14, start + duration],
    [0, 1, 1, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  );
  return <AbsoluteFill style={{ opacity }}>{children}</AbsoluteFill>;
}

/** 装饰性淡出遮罩，用于场景过渡。 */
export function Fade({ start: _start, duration: _duration, opacity }: { start: number; duration: number; opacity: number }) {
  return (
    <AbsoluteFill
      style={{
        background: COLORS.bg,
        opacity,
        zIndex: 50,
        pointerEvents: 'none',
      }}
    />
  );
}

/** 窗口 chrome（圆点 + 标题）。 */
export function UiWindow({
  title,
  width,
  children,
  accent,
  style,
}: {
  title: string;
  width: number;
  children: React.ReactNode;
  accent?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      style={{
        width,
        background: COLORS.cream,
        borderRadius: 26,
        boxShadow: '0 40px 80px -30px rgba(36,29,43,0.45)',
        border: `2px solid ${COLORS.line}`,
        overflow: 'hidden',
        fontFamily: FONT_BODY,
        ...style,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '18px 24px',
          background: '#EDE2C6',
          borderBottom: `2px solid ${COLORS.line}`,
        }}
      >
        <span style={{ width: 14, height: 14, borderRadius: 999, background: accent ?? COLORS.accent }} />
        <span style={{ width: 14, height: 14, borderRadius: 999, background: COLORS.line }} />
        <span style={{ width: 14, height: 14, borderRadius: 999, background: COLORS.line }} />
        <span
          style={{
            marginLeft: 12,
            fontFamily: FONT_MONO,
            fontSize: 18,
            color: COLORS.inkSoft,
            letterSpacing: '0.04em',
          }}
        >
          {title}
        </span>
      </div>
      {children}
    </div>
  );
}

/** 聊天气泡。 */
export function Bubble({
  text,
  start,
  delay,
  align,
  accent,
  style,
  ai,
}: {
  text: string;
  start: number;
  delay: number;
  align: 'left' | 'right';
  accent?: string;
  style?: React.CSSProperties;
  ai?: boolean;
}) {
  const { pop } = useScene(start);
  return (
    <div
      style={{
        ...pop(delay, 18, 0.94),
        alignSelf: align === 'right' ? 'flex-end' : 'flex-start',
        background: ai ? `${accent}22` : COLORS.card,
        border: `2px solid ${ai ? `${accent}55` : COLORS.line}`,
        borderRadius: 18,
        padding: '14px 20px',
        fontSize: 24,
        color: COLORS.ink,
        maxWidth: '80%',
        lineHeight: 1.5,
        ...style,
      }}
    >
      {text}
    </div>
  );
}

/** 徽章（AI 建议 / 状态标签）。 */
export function Tag({
  text,
  accent,
  start,
  delay,
  style,
}: {
  text: string;
  accent: string;
  start: number;
  delay: number;
  style?: React.CSSProperties;
}) {
  const { pop } = useScene(start);
  return (
    <div
      style={{
        ...pop(delay, 16, 0.9),
        fontFamily: FONT_MONO,
        fontSize: 18,
        letterSpacing: '0.08em',
        color: COLORS.cream,
        background: accent,
        borderRadius: 999,
        padding: '6px 16px',
        fontWeight: 700,
        ...style,
      }}
    >
      {text}
    </div>
  );
}

/** 行（用于列表 mockup）。 */
export function Row({
  label,
  value,
  color,
  start,
  delay,
  style,
  sub,
}: {
  label: string;
  value: string;
  color: string;
  start: number;
  delay: number;
  style?: React.CSSProperties;
  sub?: string;
}) {
  const { rise } = useScene(start);
  return (
    <div
      style={{
        ...rise(delay, 16, 22),
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        background: '#FFFFFF',
        border: `2px solid ${COLORS.line}`,
        borderRadius: 16,
        padding: '12px 18px',
        ...style,
      }}
    >
      <span
        style={{
          width: 14,
          height: 14,
          borderRadius: 999,
          background: color,
          flex: 'none',
        }}
      />
      <span style={{ fontFamily: FONT_BODY, fontSize: 24, color: COLORS.ink, fontWeight: 600 }}>
        {label}
      </span>
      <span style={{ flex: 1 }} />
      <span style={{ fontFamily: FONT_MONO, fontSize: 20, color: COLORS.inkSoft }}>{value}</span>
      {sub ? (
        <span
          style={{
            fontFamily: FONT_MONO,
            fontSize: 17,
            color: COLORS.cream,
            background: color,
            borderRadius: 999,
            padding: '3px 12px',
          }}
        >
          {sub}
        </span>
      ) : null}
    </div>
  );
}
