export interface Project {
  id: string;
  name: string;
  updatedAt: string;
  kind: "prototype" | "slides" | "dashboard" | "app";
  status?: "draft" | "published";
}

export const HOME_TYPE_CHIPS = [
  { id: "prototype", label: "原型", icon: "layout" as const },
  { id: "dashboard", label: "看板", icon: "bar-chart-3" as const },
  { id: "app", label: "应用", icon: "smartphone" as const },
  { id: "document", label: "文档", icon: "file-text" as const },
  { id: "more", label: "更多", icon: "plus" as const },
] as const;

export type HomeTypeChipId = (typeof HOME_TYPE_CHIPS)[number]["id"];

export const NAV_ITEMS = [
  { id: "home" as const, label: "首页", icon: "home" as const },
  { id: "projects" as const, label: "全部项目", icon: "folder" as const },
  { id: "accounts" as const, label: "账号", icon: "user-round" as const },
  { id: "monitor" as const, label: "监控", icon: "radar" as const },
] as const;
