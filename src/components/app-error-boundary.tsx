import { Component, type ErrorInfo, type ReactNode } from "react";
import { reportReactError } from "../lib/error-reporting";

type Props = {
  children: ReactNode;
};

type State = {
  hasError: boolean;
};

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  override componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    void reportReactError(error, errorInfo.componentStack ?? undefined);
  }

  override render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="page">
          <h1>页面发生错误</h1>
          <p>前端异常已转发到桌面端日志，请查看终端输出。</p>
        </div>
      );
    }

    return this.props.children;
  }
}
