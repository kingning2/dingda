import { AbsoluteFill } from 'remotion';
import { Bubble, Scene, SceneBackdrop, Tag, TextBlock, UiWindow, useScene } from '../helpers';
import { COLORS, FONT_MONO } from '../theme';

export function Messages({ start, duration }: { start: number; duration: number }) {
  const { rise, pop } = useScene(start);
  return (
    <Scene start={start} duration={duration}>
      <SceneBackdrop accent={COLORS.blue} />
      <TextBlock
        start={start}
        accent={COLORS.blue}
        eyebrow="监听消息"
        title="每一单消息都不错过"
        sub="实时监听闲鱼、WhatsApp 会话，入站、出站与 AI 建议一条不漏；过滤骚扰，多渠道提醒。"
        chips={['实时监听', '消息过滤', '多渠道通知']}
      />

      {/* Mockup：会话窗口 + 新消息提醒 */}
      <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', zIndex: 1 }}>
        <div style={{ position: 'relative' }}>
          <UiWindow title="闲鱼 · 店铺 A" width={600} accent={COLORS.blue} style={{ ...rise(14, 28, 60) }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 30 }}>
              <Bubble text="在吗？这个还有货吗？" start={start} delay={20} align="left" />
              <Bubble text="今天能发货吗？" start={start} delay={30} align="left" />
              <Bubble
                text="您好，有货，今天 18:00 前安排发货，单号会同步给您 ~"
                start={start}
                delay={40}
                align="right"
                ai
                accent={COLORS.blue}
              />
              <div style={{ ...pop(50, 16, 0.92), display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
                <Tag text="AI 建议" accent={COLORS.blue} start={start} delay={50} />
                <span style={{ fontFamily: FONT_MONO, fontSize: 17, color: COLORS.inkSoft }}>采纳</span>
              </div>
            </div>
          </UiWindow>

          {/* 新消息提醒浮层 */}
          <div
            style={{
              ...pop(56, 20, 0.9),
              position: 'absolute',
              right: -40,
              top: 60,
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              background: '#FFFFFF',
              border: `2px solid ${COLORS.blue}55`,
              borderRadius: 16,
              padding: '14px 18px',
              boxShadow: '0 24px 50px -18px rgba(36,29,43,0.4)',
            }}
          >
            <span
              style={{
                width: 12,
                height: 12,
                borderRadius: 999,
                background: COLORS.blue,
                boxShadow: `0 0 0 6px ${COLORS.blue}2e`,
              }}
            />
            <div>
              <div style={{ fontFamily: FONT_MONO, fontSize: 19, color: COLORS.ink, fontWeight: 700 }}>
                新消息
              </div>
              <div style={{ fontFamily: FONT_MONO, fontSize: 16, color: COLORS.inkSoft }}>
                WhatsApp · 客服
              </div>
            </div>
          </div>
        </div>
      </AbsoluteFill>
    </Scene>
  );
}
