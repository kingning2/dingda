import { AbsoluteFill } from 'remotion';
import { Bubble, Scene, SceneBackdrop, Tag, TextBlock, UiWindow, useScene } from '../helpers';
import { COLORS, FONT_BODY, FONT_MONO } from '../theme';

export function Ai({ start, duration }: { start: number; duration: number }) {
  const { rise, pop } = useScene(start);
  return (
    <Scene start={start} duration={duration}>
      <SceneBackdrop accent={COLORS.sage} />
      <TextBlock
        start={start}
        accent={COLORS.sage}
        eyebrow="AI 智能"
        title="AI 先替你开口"
        sub="AI 智能分析对话上下文与买家意图，生成贴合语境的回复建议；命中关键词自动回复，拍板权始终在你。"
        chips={['AI 智能分析', '回复建议', '自动回复']}
      />

      {/* Mockup：AI 分析 + 建议回复 */}
      <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', zIndex: 1 }}>
        <div style={{ position: 'relative' }}>
          <UiWindow title="AI 客服" width={620} accent={COLORS.sage} style={{ ...rise(14, 28, 60) }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 30 }}>
              <Bubble text="老板，收到货有点问题怎么退？" start={start} delay={20} align="left" />

              {/* AI 分析卡 */}
              <div
                style={{
                  ...pop(30, 20, 0.94),
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  background: `${COLORS.sage}14`,
                  border: `2px solid ${COLORS.sage}50`,
                  borderRadius: 14,
                  padding: '12px 16px',
                }}
              >
                <Tag text="AI 分析" accent={COLORS.sage} start={start} delay={30} />
                <span style={{ fontFamily: FONT_BODY, fontSize: 21, color: COLORS.ink, fontWeight: 600 }}>
                  买家关注退货流程
                </span>
              </div>

              {/* AI 建议回复 */}
              <Bubble
                text="您好，支持 7 天无理由退货，我发您退货地址和流程，您按步骤操作即可。"
                start={start}
                delay={42}
                align="right"
                ai
                accent={COLORS.sage}
              />
              <div style={{ ...pop(54, 16, 0.92), display: 'flex', alignItems: 'center', gap: 10 }}>
                <Tag text="采纳" accent={COLORS.sage} start={start} delay={54} />
                <Tag text="忽略" accent="#B9A88A" start={start} delay={58} />
                <span style={{ fontFamily: FONT_MONO, fontSize: 17, color: COLORS.inkSoft }}>
                  关键词命中自动回复
                </span>
              </div>
            </div>
          </UiWindow>
        </div>
      </AbsoluteFill>
    </Scene>
  );
}
