import { useEffect, useState } from "react";
import { AlertCircleIcon, InfoIcon, XIcon } from "lucide-react";
import {
  Alert,
  AlertAction,
  AlertDescription,
  AlertTitle,
} from "@v2/ui-primitives/alert";
import { Button } from "@v2/ui-primitives/button";
import {
  dismissAppAlert,
  navigateFromAppAlert,
  subscribeAppAlerts,
  type AppAlertItem,
} from "@v2/runtime/app-alert";

/** 全局 shadcn Alert 宿主：右上角堆叠展示，替代 window.alert。 */
export function AppAlertHost() {
  const [items, setItems] = useState<AppAlertItem[]>([]);

  useEffect(() => subscribeAppAlerts(setItems), []);

  if (items.length === 0) return null;

  return (
    <div
      className="pointer-events-none fixed top-3 right-3 z-[100] flex w-[min(100%-1.5rem,22rem)] flex-col gap-2"
      aria-live="polite"
    >
      {items.map((item) => {
        // 先取出再判空：放进 onClick 闭包里 TS 不做属性收窄。
        const action = item.action;
        return (
          <Alert
            key={item.id}
            variant={item.variant}
            className="pointer-events-auto border-border/80 shadow-lg"
          >
            {item.variant === "destructive" ? <AlertCircleIcon /> : <InfoIcon />}
            <AlertTitle>{item.title}</AlertTitle>
            {item.description ? (
              <AlertDescription>{item.description}</AlertDescription>
            ) : null}
            {action ? (
              <Button
                type="button"
                variant="outline"
                size="xs"
                className="col-start-2 mt-1.5 w-fit"
                onClick={() => {
                  dismissAppAlert(item.id);
                  navigateFromAppAlert(action.href);
                }}
              >
                {action.label}
              </Button>
            ) : null}
            <AlertAction>
              <Button
                type="button"
                variant="ghost"
                size="icon-xs"
                aria-label="关闭"
                onClick={() => dismissAppAlert(item.id)}
              >
                <XIcon className="size-3.5" />
              </Button>
            </AlertAction>
          </Alert>
        );
      })}
    </div>
  );
}
