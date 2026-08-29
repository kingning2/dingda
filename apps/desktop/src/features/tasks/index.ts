/**
 * 任务中心 Feature。
 */

import { ListTodo } from "@desk/ui/icons";

export { TasksPage } from "./tasks-page";
export { TaskDetailPage } from "./task-detail-page";
export { TaskCopilotRoute } from "./copilot/task-copilot-page";

export const TASKS_PATH = "/tasks" as const;

export const tasksFeature = {
  id: "tasks",
  path: TASKS_PATH,
  navItem: {
    id: "tasks",
    path: TASKS_PATH,
    label: "任务中心",
    icon: ListTodo,
  },
};
