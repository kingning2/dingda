import {
  AlphabetIcon,
  HomeIcon,
  PieChartIcon,
  TableIcon,
  TaskIcon,
  UserIcon,
  Widget4Icon,
} from "./icon";
import { WORKSPACE_NAV } from "@/content/business";

const iconFor = (title: string) => {
  if (title.includes("工作台")) return <HomeIcon />;
  if (title.includes("选品")) return <PieChartIcon />;
  if (title.includes("商品")) return <Widget4Icon />;
  if (title.includes("利润")) return <PieChartIcon />;
  if (title.includes("监控")) return <TableIcon />;
  if (title.includes("任务")) return <TaskIcon />;
  if (title.includes("设置")) return <UserIcon />;
  if (title.includes("官网")) return <HomeIcon />;
  return <AlphabetIcon />;
};

export const NAV_DATA = WORKSPACE_NAV.map((section) => ({
  label: section.label,
  items: section.items.map((item) => ({
    title: item.title,
    icon: iconFor(item.title),
    url: "url" in item ? item.url : undefined,
    items:
      "children" in item
        ? item.children.map((child) => ({
            title: child.title,
            url: child.url,
          }))
        : [],
  })),
}));
