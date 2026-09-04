const BOOT_SPLASH_OUT_CLASS = "boot-splash--out";
const BOOT_CRITICAL_STYLE_ID = "boot-critical";
const FADE_MS = 240;

/** React 首帧绘制后淡出并移除 HTML 启动屏。 */
export function dismissBootSplash(): void {
  const splash = document.getElementById("boot-splash");
  if (!splash || splash.classList.contains(BOOT_SPLASH_OUT_CLASS)) return;

  splash.setAttribute("aria-busy", "false");
  splash.classList.add(BOOT_SPLASH_OUT_CLASS);

  const cleanup = () => {
    splash.remove();
    document.getElementById(BOOT_CRITICAL_STYLE_ID)?.remove();
  };

  splash.addEventListener("transitionend", cleanup, { once: true });
  window.setTimeout(cleanup, FADE_MS + 40);
}

/** 等待 React 提交到 DOM 后再移除启动屏，避免闪白。 */
export function dismissBootSplashAfterPaint(): void {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => dismissBootSplash());
  });
}
