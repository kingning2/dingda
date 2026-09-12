import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { AppErrorBoundary } from "@v2/ui-feedback/app-error-boundary";
import { installGlobalErrorReporting } from "@v2/runtime/error-reporting";
import "@v2/ui-theme/index.css";

installGlobalErrorReporting();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <AppErrorBoundary>
      <App />
    </AppErrorBoundary>
  </React.StrictMode>,
);

// 启动屏由 ServerProvider 在首页数据预加载完成后 dismiss
