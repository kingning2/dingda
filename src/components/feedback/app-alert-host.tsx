import { useEffect, useState } from "react";
import { AlertCircleIcon, InfoIcon, XIcon } from "lucide-react";
import {
  Alert,
  AlertAction,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  dismissAppAlert,
  subscribeAppAlerts,
  type AppAlertItem,
} from "@/lib/app-alert";

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
      {items.map((item) => (
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
      ))}
    </div>
  );
}
