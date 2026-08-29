import { AbsoluteFill } from 'remotion';
import { Scene, SceneBackdrop, TextBlock, UiWindow, useScene } from '../helpers';
import { COLORS, FONT_BODY, FONT_MONO } from '../theme';

export function Local({ start, duration }: { start: number; duration: number }) {
  const { rise, pop } = useScene(start);
  return (
    <Scene start={start} duration={duration}>
      <SceneBackdrop accent={COLORS.plum} />
      <TextBlock
        start={start}
        accent={COLORS.plum}
        eyebrow="本地优先 · 开源"
        title="数据留在你的桌面"
        sub="聊天、账号、订单全部存在本机。AI 只读，写库与发送由你操作。源码开源，欢迎参与。"
      />

      {/* CTA 按钮 */}
      <AbsoluteFill style={{ zIndex: 2, pointerEvents: 'none' }}>
        <div
          style={{
            position: 'absolute',
            left: '9vw',
            bottom: '12vh',
            display: 'flex',
            gap: 20,
          }}
        >
          <a
            href="https://github.com/kingning2/dingda"
            target="_blank"
            rel="noreferrer"
            style={{
              ...pop(16, 20, 0.94),
              fontFamily: FONT_BODY,
              fontSize: 28,
              fontWeight: 700,
              color: COLORS.cream,
              background: COLORS.ink,
              borderRadius: 16,
              padding: '18px 36px',
              textDecoration: 'none',
              boxShadow: '0 24px 50px -18px rgba(36,29,43,0.5)',
            }}
          >
            在 GitHub 查看
          </a>
          <a
            href="https://github.com/kingning2/dingda/releases"
            target="_blank"
            rel="noreferrer"
            style={{
              ...pop(24, 20, 0.94),
              fontFamily: FONT_BODY,
              fontSize: 28,
              fontWeight: 700,
              color: COLORS.ink,
              border: `3px solid ${COLORS.ink}33`,
              borderRadius: 16,
              padding: '18px 36px',
              textDecoration: 'none',
            }}
          >
            下载桌面版
          </a>
        </div>
      </AbsoluteFill>

      {/* Mockup：本地设备 + 盾牌锁 */}
      <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', zIndex: 1 }}>
        <UiWindow title="叮答 · 本地存储" width={560} accent={COLORS.plum} style={{ ...rise(12, 26, 60) }}>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 22,
              padding: '40px 32px',
            }}
          >
            {/* 盾牌锁 */}
            <div style={{ ...pop(20, 22, 0.86) }}>
              <div
                style={{
                  width: 150,
                  height: 150,
                  borderRadius: 40,
                  background: COLORS.plum,
                  display: 'grid',
                  placeItems: 'center',
                  boxShadow: '0 28px 60px -22px rgba(142,110,156,0.6)',
                }}
              >
                <svg width="84" height="96" viewBox="0 0 24 28">
                  <path
                    d="M12 1 L22 5 V13 C22 20 18 24 12 27 C6 24 2 20 2 13 V5 Z"
                    fill="#F5EDE0"
                  />
                  <rect x="8.5" y="11" width="7" height="5" rx="1.5" fill="#8E6E9C" />
                  <path d="M10.5 14 h3 v5 h-3 Z" fill="#8E6E9C" />
                </svg>
              </div>
            </div>
            <div
              style={{
                ...pop(30, 18, 0.94),
                fontFamily: FONT_MONO,
                fontSize: 20,
                color: COLORS.inkSoft,
                textAlign: 'center',
              }}
            >
              聊天 · 账号 · 订单，全部只存在本机
            </div>
            <div
              style={{
                ...pop(38, 18, 0.94),
                fontFamily: FONT_BODY,
                fontSize: 24,
                color: COLORS.ink,
                fontWeight: 700,
                background: `${COLORS.plum}14`,
                border: `2px solid ${COLORS.plum}50`,
                borderRadius: 16,
                padding: '14px 26px',
              }}
            >
              AI 只读 · 写库与发送由你操作
            </div>
          </div>
        </UiWindow>
      </AbsoluteFill>
    </Scene>
  );
}
