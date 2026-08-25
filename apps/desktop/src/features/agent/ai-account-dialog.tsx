/**
 * AI 账号添加 / 编辑对话框。
 *
 * @author coisini
 * @created 2026-08-11
 */

import { useState } from "react";
import { Button, Dialog, DialogContent, Input } from "@desk/ui";
import type { AiAccount } from "@desk/contracts";
import { aiTestApiKey } from "@desk/platform/ipc/ai";
import type { BuiltInProvider } from "./builtin-providers";
import { useAiConfigStore, type AiAccountInput } from "./use-ai-config";

function toError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * 添加 / 编辑 AI 账号对话框。
 *
 * @author coisini
 * @created 2026-08-11
 */
export function AiAccountDialog({
  open,
  provider,
  account,
  onClose,
}: {
  open: boolean;
  provider: BuiltInProvider | null;
  account: AiAccount | null;
  onClose: () => void;
}) {
  const addAccount = useAiConfigStore((state) => state.addAccount);
  const updateAccount = useAiConfigStore((state) => state.updateAccount);

  const [name, setName] = useState(account?.name ?? "");
  const [apiKey, setApiKey] = useState(account?.api_key ?? "");
  const [defaultModel, setDefaultModel] = useState(account?.default_model ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);

  async function handleTest() {
    const trimmedKey = apiKey.trim();
    if (!trimmedKey) {
      setError("请输入访问密钥");
      return;
    }
    setTesting(true);
    setTestResult(null);
    setError(null);
    try {
      setTestResult(
        await aiTestApiKey(provider?.base_url ?? "", trimmedKey, provider?.kind),
      );
    } catch (caught) {
      setError(toError(caught));
    } finally {
      setTesting(false);
    }
  }

  async function handleSubmit() {
    const trimmedName = name.trim();
    const trimmedKey = apiKey.trim();
    const trimmedModel = defaultModel.trim();
    if (!trimmedName) {
      setError("请输入名称");
      return;
    }
    if (!trimmedKey) {
      setError("请输入访问密钥");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const input: AiAccountInput = {
        provider_id: provider?.id ?? "",
        name: trimmedName,
        api_key: trimmedKey,
        default_model: trimmedModel || undefined,
      };
      if (account) {
        await updateAccount(account.id, input);
      } else {
        await addAccount(input);
      }
      onClose();
    } catch (caught) {
      setError(toError(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent
        title={
          account
            ? `编辑${provider?.name ?? ""}账号`
            : `添加${provider?.name ?? ""}账号`
        }
        footer={
          <>
            <Button variant="ghost" disabled={saving} onClick={onClose}>
              取消
            </Button>
            <Button disabled={saving} onClick={() => void handleSubmit()}>
              保存
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label
              htmlFor="ai-account-name"
              className="text-[length:var(--text-sm)] font-medium text-foreground"
            >
              账号名称
            </label>
            <Input
              id="ai-account-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="如：工作号"
            />
          </div>
          <div className="flex flex-col gap-2">
            <label
              htmlFor="ai-account-key"
              className="text-[length:var(--text-sm)] font-medium text-foreground"
            >
              访问密钥
            </label>
            <div className="flex items-center gap-2">
              <Input
                id="ai-account-key"
                type="password"
                value={apiKey}
                onChange={(event) => {
                  setApiKey(event.target.value);
                  setTestResult(null);
                }}
                placeholder="粘贴从平台复制的密钥"
                className="min-w-0 flex-1"
              />
              {provider && !provider.authless ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={testing}
                  onClick={() => void handleTest()}
                >
                  {testing ? "测试中…" : "测试"}
                </Button>
              ) : null}
            </div>
            {testResult ? (
              <p
                className={
                  testResult.ok
                    ? "text-[length:var(--text-sm)] text-green-600 dark:text-green-400"
                    : "text-[length:var(--text-sm)] text-red-600 dark:text-red-400"
                }
              >
                {testResult.ok ? "密钥有效，可以保存" : "密钥无效，请检查后重试"}
              </p>
            ) : null}
          </div>
          <div className="flex flex-col gap-2">
            <label
              htmlFor="ai-account-model"
              className="text-[length:var(--text-sm)] font-medium text-foreground"
            >
              常用模型
            </label>
            <Input
              id="ai-account-model"
              value={defaultModel}
              onChange={(event) => setDefaultModel(event.target.value)}
              placeholder={provider?.modelPlaceholder ?? "可选"}
            />
            {provider?.hint ? (
              <p className="text-[length:var(--text-xs)] text-muted-foreground">{provider.hint}</p>
            ) : null}
          </div>
          {error ? (
            <p className="text-[length:var(--text-sm)] text-red-600 dark:text-red-400">
              {error}
            </p>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
