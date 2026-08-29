import { AbsoluteFill } from 'remotion';
import { Row, Scene, SceneBackdrop, Tag, TextBlock, UiWindow, useScene } from '../helpers';
import { COLORS } from '../theme';

export function Orders({ start, duration }: { start: number; duration: number }) {
  const { rise, pop } = useScene(start);
  return (
    <Scene start={start} duration={duration}>
      <SceneBackdrop accent={COLORS.terracotta} />
      <TextBlock
        start={start}
        accent={COLORS.terracotta}
        eyebrow="订单与发货"
        title="从下单到归档"
        sub="订单跟进、卡券自动发货、内容变量填充，重复动作交给模板与规则。"
        chips={['订单管理', '卡券自动发货', '发货延时']}
      />

      {/* Mockup：订单列表 + 自动发货 */}
      <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', zIndex: 1 }}>
        <UiWindow title="叮答 · 订单" width={620} accent={COLORS.terracotta} style={{ ...rise(14, 28, 60) }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 28 }}>
            <Row label="订单 #10231" value="¥128.00" color={COLORS.terracotta} start={start} delay={18} sub="已付款" />
            <Row label="订单 #10232" value="¥66.00" color={COLORS.amber} start={start} delay={28} sub="已付款" />
            <Row label="订单 #10233" value="¥259.00" color={COLORS.terracotta} start={start} delay={38} sub="待发货" />
          </div>

          {/* 卡券自动发货 */}
          <div
            style={{
              ...pop(48, 18, 0.94),
              margin: '0 28px 28px',
              display: 'flex',
              alignItems: 'center',
              gap: 14,
              background: `${COLORS.terracotta}14`,
              border: `2px solid ${COLORS.terracotta}50`,
              borderRadius: 16,
              padding: '14px 18px',
            }}
          >
            <span style={{ fontSize: 26 }}>🎫</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: 'system-ui, sans-serif', fontSize: 22, color: COLORS.ink, fontWeight: 600 }}>
                卡券已自动发货
              </div>
              <div
                style={{
                  fontFamily: 'ui-monospace, Menlo, monospace',
                  fontSize: 16,
                  color: COLORS.inkSoft,
                  marginTop: 2,
                }}
              >
                自有卡券 · 来源优先级匹配
              </div>
            </div>
            <Tag text="自动" accent={COLORS.terracotta} start={start} delay={52} />
          </div>
        </UiWindow>
      </AbsoluteFill>
    </Scene>
  );
}
