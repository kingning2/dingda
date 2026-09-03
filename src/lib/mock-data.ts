export interface Project {
  id: string;
  name: string;
  updatedAt: string;
  kind: "prototype" | "slides" | "dashboard" | "app";
  status?: "draft" | "published";
}

export const MOCK_PROJECTS: Project[] = [
  {
    id: "1",
    name: "电商落地页原型",
    updatedAt: "2026-08-30",
    kind: "prototype",
    status: "draft",
  },
  {
    id: "2",
    name: "产品发布会幻灯片",
    updatedAt: "2026-08-29",
    kind: "slides",
    status: "published",
  },
  {
    id: "3",
    name: "数据看板 Dashboard",
    updatedAt: "2026-08-28",
    kind: "dashboard",
    status: "draft",
  },
  {
    id: "4",
    name: "移动端 App 流程",
    updatedAt: "2026-08-27",
    kind: "app",
    status: "draft",
  },
];

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
  { id: "community" as const, label: "社区", icon: "users" as const },
  { id: "projects" as const, label: "全部项目", icon: "folder" as const },
  { id: "design-systems" as const, label: "设计系统", icon: "palette" as const },
  { id: "assets" as const, label: "资产", icon: "wallet" as const },
  { id: "crawler" as const, label: "爬虫", icon: "spider" as const },
] as const;
