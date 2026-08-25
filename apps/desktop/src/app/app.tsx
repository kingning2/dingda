/**
 * 应用根组件：主题、授权闸门、错误生命周期与路由。
 *
 * @author coisini
 * @created 2026-07-20
 */

import { RouterProvider } from "react-router";
import { QueryProvider, ThemeProvider, Toaster } from "@desk/ui";
import { LicenseGateProvider, useLicenseGate } from "@license";
import { appRouter } from "../route";
import { useErrorLifecycle } from "../lifecycle";
import "./globals.css";

/**
 * 授权状态 Provider 与路由壳。
 *
 * @author coisini
 * @created 2026-07-20
 *
 * @returns 壳节点
 */
function AppChrome() {
  const gate = useLicenseGate();
  useErrorLifecycle();

  return (
    <ThemeProvider defaultTheme="dark">
      <LicenseGateProvider value={gate}>
        <div className="relative h-screen w-full overflow-hidden">
          <RouterProvider router={appRouter} />
          <Toaster position="top-center" richColors closeButton />
        </div>
      </LicenseGateProvider>
    </ThemeProvider>
  );
}

/**
 * 应用根组件。
 *
 * @author coisini
 * @created 2026-07-20
 *
 * @returns 根节点
 */
export function App() {
  return (
    <QueryProvider>
      <AppChrome />
    </QueryProvider>
  );
}
