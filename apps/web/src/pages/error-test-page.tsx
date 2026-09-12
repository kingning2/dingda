import { useState, type ReactNode } from "react";
import { Button } from "@v2/ui-primitives/button";

function CrashOnRender(): ReactNode {
  throw new Error("React 渲染错误测试");
}

type ErrorTestPageProps = {
  onBack: () => void;
};

export function ErrorTestPage({ onBack }: ErrorTestPageProps) {
  const [crash, setCrash] = useState(false);

  if (crash) {
    return <CrashOnRender />;
  }

  function triggerWindowError() {
    setTimeout(() => {
      throw new Error("window.onerror 测试");
    }, 0);
  }

  function triggerUnhandledRejection() {
    void Promise.reject(new Error("unhandledrejection 测试"));
  }

  return (
    <div className="max-w-2xl p-8">
      <h1 className="text-2xl font-semibold text-foreground">错误测试页</h1>
      <p className="mt-2 text-muted-foreground">
        点击下方按钮触发异常，终端应出现紫色 `[frontend]` 日志。
      </p>

      <div className="mt-6 flex flex-wrap gap-3">
        <Button onClick={triggerWindowError}>运行时错误</Button>
        <Button onClick={triggerUnhandledRejection}>Promise 未捕获</Button>
        <Button onClick={() => setCrash(true)}>React 渲染错误</Button>
        <Button variant="outline" onClick={onBack}>
          返回首页
        </Button>
      </div>

      <p className="mt-6 text-sm text-muted-foreground">
        也可直接访问 <code className="rounded bg-muted px-1.5 py-0.5">#/error-test</code>
      </p>
    </div>
  );
}
