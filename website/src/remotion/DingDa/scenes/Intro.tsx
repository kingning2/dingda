import { AbsoluteFill } from 'remotion';
import { Scene, SceneBackdrop, useScene } from '../helpers';
import { COLORS, FONT_BODY, FONT_DISPLAY, FONT_MONO } from '../theme';

export function Intro({ start, duration }: { start: number; duration: number }) {
  const { rise, pop } = useScene(start);
  return (
    <Scene start={start} duration={duration}>
      <SceneBackdrop accent={COLORS.accent} />
      <AbsoluteFill
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {/* 品牌印章 */}
        <div style={{ ...pop(8, 26, 0.7) }}>
          <div
            style={{
              width: 184,
              height: 184,
              borderRadius: 40,
              background: COLORS.accent,
              display: 'grid',
              placeItems: 'center',
              boxShadow: '0 34px 70px -22px rgba(200,55,42,0.6)',
            }}
          >
            <div
              style={{
                width: 148,
                height: 148,
                borderRadius: 30,
                border: `6px solid ${COLORS.cream}90`,
                display: 'grid',
                placeItems: 'center',
              }}
            >
              <span
                style={{
                  fontFamily: FONT_DISPLAY,
                  fontSize: 108,
                  fontWeight: 800,
                  color: COLORS.cream,
                  lineHeight: 1,
                }}
              >
                答
              </span>
            </div>
          </div>
        </div>

        <div
          style={{
            ...rise(14, 20, 30),
            marginTop: 34,
            fontFamily: FONT_MONO,
            fontSize: 30,
            letterSpacing: '0.5em',
            color: COLORS.accent,
            fontWeight: 700,
          }}
        >
          DINGDA
        </div>

        <div
          style={{
            ...rise(18, 22, 46),
            marginTop: 14,
            fontFamily: FONT_DISPLAY,
            fontWeight: 800,
            fontSize: 132,
            letterSpacing: '0.06em',
            color: COLORS.ink,
            lineHeight: 1,
          }}
        >
          叮答
        </div>

        <div
          style={{
            ...rise(26, 22, 38),
            marginTop: 28,
            fontFamily: FONT_BODY,
            fontSize: 44,
            color: COLORS.inkSoft,
            letterSpacing: '0.04em',
          }}
        >
          本地优先的 AI 智能客服平台
        </div>

        <div style={{ display: 'flex', gap: 22, marginTop: 56 }}>
          {['AI 智能客服', '多账号 · 多平台', '数据本地'].map((c, i) => (
            <div
              key={c}
              style={{
                ...pop(34 + i * 5, 18, 0.9),
                fontFamily: FONT_MONO,
                fontSize: 22,
                letterSpacing: '0.1em',
                color: COLORS.accent,
                border: `2px solid ${COLORS.accent}40`,
                background: '#FFFFFFE6',
                borderRadius: 999,
                padding: '12px 28px',
                fontWeight: 700,
              }}
            >
              {c}
            </div>
          ))}
        </div>
      </AbsoluteFill>
    </Scene>
  );
}
