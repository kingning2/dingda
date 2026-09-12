/** 全局 Alert 队列（替代 window.alert）。 */

export type AppAlertVariant = "default" | "destructive";

/** 告警上的操作按钮。`href` 是应用内路由路径（如 `/accounts?platform=xianyu`）。 */
export interface AppAlertAction {
  label: string;
  href: string;
}

export interface AppAlertItem {
  id: string;
  title: string;
  description?: string;
  variant: AppAlertVariant;
  /** 带操作按钮的告警不自动消失，见 pushAppAlert。 */
  action?: AppAlertAction;
  createdAt: number;
}

/**
 * 应用内跳转。由装配层注入（`apps/web`），套路同 http-client 的 `setApiBaseUrl`：
 * 基座包与 UI 包都不该依赖 react-router，路由实例属于应用层。
 */
type AppAlertNavigator = (href: string) => void;

let appAlertNavigator: AppAlertNavigator | null = null;

export function setAppAlertNavigator(navigator: AppAlertNavigator | null): void {
  appAlertNavigator = navigator;
}

/** 供告警宿主调用。未注入时回退整页跳转，避免按钮点了没反应。 */
export function navigateFromAppAlert(href: string): void {
  if (appAlertNavigator) {
    appAlertNavigator(href);
    return;
  }
  window.location.assign(href);
}

type Listener = (items: AppAlertItem[]) => void;

const MAX_VISIBLE = 3;
const AUTO_DISMISS_MS = 6_000;

let items: AppAlertItem[] = [];
const listeners = new Set<Listener>();
const dismissTimers = new Map<string, number>();

function emit() {
  const snapshot = items.slice();
  for (const listener of listeners) {
    listener(snapshot);
  }
}

function scheduleDismiss(id: string) {
  const existing = dismissTimers.get(id);
  if (existing !== undefined) {
    window.clearTimeout(existing);
  }
  const timer = window.setTimeout(() => {
    dismissTimers.delete(id);
    dismissAppAlert(id);
  }, AUTO_DISMISS_MS);
  dismissTimers.set(id, timer);
}

export function subscribeAppAlerts(listener: Listener): () => void {
  listeners.add(listener);
  listener(items.slice());
  return () => {
    listeners.delete(listener);
  };
}

export function getAppAlerts(): AppAlertItem[] {
  return items.slice();
}

export function pushAppAlert(input: {
  title: string;
  description?: string;
  variant?: AppAlertVariant;
  action?: AppAlertAction;
}): string {
  const id = `alert-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const next: AppAlertItem = {
    id,
    title: input.title.trim() || "提示",
    description: input.description?.trim() || undefined,
    variant: input.variant ?? "default",
    action: input.action,
    createdAt: Date.now(),
  };
  items = [next, ...items].slice(0, MAX_VISIBLE);
  // 带操作按钮的告警不自动消失：6 秒内来不及看清再点击，等于没提醒。
  // 数量上限仍由 MAX_VISIBLE 兜住，用户可点按钮或手动关闭。
  if (!next.action) scheduleDismiss(id);
  emit();
  return id;
}

export function dismissAppAlert(id: string) {
  const timer = dismissTimers.get(id);
  if (timer !== undefined) {
    window.clearTimeout(timer);
    dismissTimers.delete(id);
  }
  const before = items.length;
  items = items.filter((item) => item.id !== id);
  if (items.length !== before) emit();
}

export function clearAppAlerts() {
  for (const timer of dismissTimers.values()) {
    window.clearTimeout(timer);
  }
  dismissTimers.clear();
  if (items.length === 0) return;
  items = [];
  emit();
}
