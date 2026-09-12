import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { AppErrorBoundary } from "@v2/ui-feedback/app-error-boundary";
import { installGlobalErrorReporting } from "@v2/runtime/error-reporting";
import { installAppAlertNavigator } from "@web/boot/alert-navigator";
import "@v2/ui-theme/index.css";

installGlobalErrorReporting();
// 告警里的操作按钮要能走 SPA 路由，路由实例只在应用层，故在此注入
installAppAlertNavigator();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <AppErrorBoundary>
      <App />
    </AppErrorBoundary>
  </React.StrictMode>,
);

// 启动屏由 BootGate 在首页数据预加载完成后 dismiss
