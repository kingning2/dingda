import { AbsoluteFill } from 'remotion';
import { Scene, SceneBackdrop, Tag, TextBlock, UiWindow, useScene } from '../helpers';
import { COLORS, FONT_BODY, FONT_DISPLAY, FONT_MONO } from '../theme';

const TILES: { name: string; sub: string; color: string }[] = [
  { name: '闲鱼 · 店铺 A', sub: '在线', color: '#E8A33D' },
  { name: '闲鱼 · 店铺 B', sub: '在线', color: '#E8A33D' },
  { name: 'WhatsApp · 客服', sub: '在线', color: '#5E9C6D' },
  { name: '新渠道', sub: '接入', color: COLORS.line },
];

export function Accounts({ start, duration }: { start: number; duration: number }) {
  const { rise, pop } = useScene(start);
  return (
    <Scene start={start} duration={duration}>
      <SceneBackdrop accent={COLORS.amber} />
      <TextBlock
        start={start}
        accent={COLORS.amber}
        eyebrow="多账号 · 多平台"
        title="所有店铺，一个入口"
        sub="闲鱼、WhatsApp 多账号集中管理，商品与素材一处维护、多平台发布复用。"
        chips={['多账号管理', '多平台商品互通', '渠道扩展']}
      />

      {/* Mockup：账号网格 + 商品互通卡 */}
      <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', zIndex: 1 }}>
        <UiWindow title="叮答 · 账号" width={620} accent={COLORS.amber} style={{ ...rise(14, 28, 60) }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18, padding: 28 }}>
            {TILES.map((tile, i) => (
              <div
                key={tile.name}
                style={{
                  ...pop(18 + i * 8, 18, 0.92),
                  display: 'flex',
                  alignItems: 'center',
                  gap: 14,
                  background: '#FFFFFF',
                  border: `2px solid ${COLORS.line}`,
                  borderRadius: 16,
                  padding: '16px 18px',
                }}
              >
                <span
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: 12,
                    background: tile.color,
                    display: 'grid',
                    placeItems: 'center',
                    color: '#fff',
                    fontWeight: 800,
                    fontFamily: FONT_DISPLAY,
                    fontSize: 18,
                  }}
                >
                  {tile.name.slice(0, 1)}
                </span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontFamily: FONT_BODY, fontSize: 23, color: COLORS.ink, fontWeight: 600 }}>
                    {tile.name}
                  </div>
                  <div style={{ fontFamily: FONT_MONO, fontSize: 16, color: COLORS.inkSoft, marginTop: 2 }}>
                    {tile.sub}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div
            style={{
              ...pop(52, 18, 0.95),
              margin: '0 28px 28px',
              display: 'flex',
              alignItems: 'center',
              gap: 14,
              background: `${COLORS.amber}14`,
              border: `2px solid ${COLORS.amber}50`,
              borderRadius: 16,
              padding: '14px 18px',
            }}
          >
            <span style={{ fontSize: 26 }}>📦</span>
            <span style={{ fontFamily: FONT_BODY, fontSize: 22, color: COLORS.ink, fontWeight: 600, flex: 1 }}>
              商品素材一处维护，多平台复用
            </span>
            <Tag text="互通" accent={COLORS.amber} start={start} delay={56} />
          </div>
        </UiWindow>
      </AbsoluteFill>
    </Scene>
  );
}
