/**
 * 503 服务不可用 — 后端中断或授权状态拉取失败，内联渲染在工作区内容区。
 */

import { Button } from "@desk/ui";
import { useLicenseGateContext } from "@license";
import { useErrorStore } from "../../lifecycle";
import { ErrorPage } from "./error-page";

/**
 * 后端不可用或授权校验失败时的恢复视图；由 WorkspaceOutlet 内联挂载。
 */
export function ServiceUnavailablePage() {
  const { error, refresh } = useLicenseGateContext();
  const backendUnavailable = useErrorStore((state) => state.backendUnavailable);
  const setBackendUnavailable = useErrorStore((state) => state.setBackendUnavailable);

  if (!backendUnavailable && !error) {
    return null;
  }

  return (
    <ErrorPage
      code="503"
      title="服务暂不可用"
      description={error ?? "连接中断或后台服务正在恢复，请稍后重试。"}
      action={
        <Button
          onClick={() => {
            setBackendUnavailable(false);
            refresh();
          }}
        >
          重试
        </Button>
      }
    />
  );
}
