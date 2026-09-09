import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { AppErrorBoundary } from "./components/app-error-boundary";
import { installGlobalErrorReporting } from "./lib/error-reporting";
import "./styles/index.css";

installGlobalErrorReporting();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <AppErrorBoundary>
      <App />
    </AppErrorBoundary>
  </React.StrictMode>,
);

// 启动屏由 ServerProvider 在首页数据预加载完成后 dismiss
