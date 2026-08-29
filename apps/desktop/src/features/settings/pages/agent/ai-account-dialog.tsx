/**
 * AI 账号添加 / 编辑对话框 — 选平台、填密钥、拉取模型列表后选择。
 */

import { useState } from "react";
import {
  Button,
  Dialog,
  DialogContent,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@desk/ui";
import type { AiAccount, AiProvider } from "@desk/contracts";
import { aiListModels } from "@desk/platform/ipc/ai";
import {
  providerRequiresApiKey,
  useAiConfigStore,
  type AiAccountInput,
} from "./use-ai-config";

function toError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function AiAccountDialog({
  open,
  catalog,
  account,
  onClose,
}: {
  open: boolean;
  catalog: AiProvider[];
  account: AiAccount | null;
  onClose: () => void;
}) {
  const addAccount = useAiConfigStore((state) => state.addAccount);
  const updateAccount = useAiConfigStore((state) => state.updateAccount);
  const resolveProvider = useAiConfigStore((state) => state.resolveProvider);

  const [providerId, setProviderId] = useState(
    account?.provider_id ?? catalog[0]?.id ?? "",
  );
  const [name, setName] = useState(account?.name ?? "");
  const [apiKey, setApiKey] = useState(account?.api_key ?? "");
  const [defaultModel, setDefaultModel] = useState(account?.default_model ?? "");
  const [modelOptions, setModelOptions] = useState<string[]>(
    account?.default_model ? [account.default_model] : [],
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listingModels, setListingModels] = useState(false);
  const [listOkHint, setListOkHint] = useState<string | null>(null);

  const provider =
    (account
      ? resolveProvider(account.provider_id)
      : catalog.find((item) => item.id === providerId)) ??
    resolveProvider(providerId);
  const needsKey = providerRequiresApiKey(provider);
  const editing = account !== null;
  const canFetchModels = Boolean(provider?.base_url) && (!needsKey || Boolean(apiKey.trim()));

  async function handleFetchModels() {
    if (!provider?.base_url) {
      setError("当前平台缺少 base_url");
      return;
    }
    if (needsKey && !apiKey.trim()) {
      setError("请先填写访问密钥");
      return;
    }
    setListingModels(true);
    setError(null);
    setListOkHint(null);
    try {
      const result = await aiListModels(
        provider.base_url,
        apiKey.trim(),
        provider.kind,
      );
      if (!result.ok) {
        setModelOptions([]);
        setError(result.message || "拉取模型失败");
        return;
      }
      setModelOptions(result.models);
      if (result.models.length === 0) {
        setError("未获取到可用模型");
        return;
      }
      setListOkHint(`密钥有效，已获取 ${result.models.length} 个模型`);
      if (!defaultModel || !result.models.includes(defaultModel)) {
        const preferred =
          (provider.default_model && result.models.includes(provider.default_model)
            ? provider.default_model
            : null) ?? result.models[0];
        setDefaultModel(preferred ?? "");
      }
    } catch (caught) {
      setModelOptions([]);
      setError(toError(caught));
    } finally {
      setListingModels(false);
    }
  }

  async function handleSubmit() {
    const trimmedName = name.trim();
    const trimmedKey = apiKey.trim();
    const trimmedModel = defaultModel.trim();
    const selectedProviderId = editing ? account.provider_id : providerId;
    if (!selectedProviderId) {
      setError("请选择平台");
      return;
    }
    if (!trimmedName) {
      setError("请输入名称");
      return;
    }
    if (needsKey && !trimmedKey) {
      setError("请输入访问密钥");
      return;
    }
    if (!trimmedModel) {
      setError("请先获取并选择模型");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const input: AiAccountInput = {
        provider_id: selectedProviderId,
        name: trimmedName,
        api_key: needsKey ? trimmedKey : trimmedKey || "local",
        default_model: trimmedModel,
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
        title={editing ? `编辑${provider?.name ?? ""}账号` : "添加 AI 账号"}
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
            <Label htmlFor="ai-account-provider" className="font-medium text-foreground">
              平台
            </Label>
            {editing ? (
              <Input
                id="ai-account-provider"
                value={provider?.name ?? account.provider_id}
                disabled
              />
            ) : (
              <Select
                value={providerId}
                onValueChange={(value) => {
                  setProviderId(value);
                  setListOkHint(null);
                  setModelOptions([]);
                  setDefaultModel("");
                  const next = catalog.find((item) => item.id === value);
                  if (next?.default_model) {
                    setDefaultModel(next.default_model);
                    setModelOptions([next.default_model]);
                  }
                }}
              >
                <SelectTrigger id="ai-account-provider" aria-label="选择平台">
                  <SelectValue placeholder="选择平台" />
                </SelectTrigger>
                <SelectContent>
                  {catalog.map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {item.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="ai-account-name" className="font-medium text-foreground">
              账号名称
            </Label>
            <Input
              id="ai-account-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="如：工作号"
            />
          </div>

          {needsKey ? (
            <div className="flex flex-col gap-2">
              <Label htmlFor="ai-account-key" className="font-medium text-foreground">
                访问密钥
              </Label>
              <Input
                id="ai-account-key"
                type="password"
                value={apiKey}
                onChange={(event) => {
                  setApiKey(event.target.value);
                  setListOkHint(null);
                  setModelOptions([]);
                }}
                placeholder="粘贴从平台复制的密钥"
              />
            </div>
          ) : null}

          <div className="flex flex-col gap-2">
            <Label className="font-medium text-foreground">常用模型</Label>
            <div className="flex items-center gap-2">
              <Select
                value={defaultModel || undefined}
                onValueChange={setDefaultModel}
                disabled={modelOptions.length === 0}
              >
                <SelectTrigger className="min-w-0 flex-1" aria-label="选择模型">
                  <SelectValue
                    placeholder={
                      modelOptions.length > 0 ? "选择模型" : "先获取模型列表"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {modelOptions.map((modelId) => (
                    <SelectItem key={modelId} value={modelId}>
                      {modelId}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={!canFetchModels || listingModels}
                onClick={() => void handleFetchModels()}
              >
                {listingModels ? "获取中…" : "获取列表"}
              </Button>
            </div>
            {listOkHint ? (
              <p className="text-[length:var(--text-sm)] text-green-600 dark:text-green-400">
                {listOkHint}
              </p>
            ) : (
              <p className="text-[length:var(--text-xs)] text-muted-foreground">
                {needsKey
                  ? "填写密钥后获取列表；成功即表示密钥有效"
                  : "获取列表成功后选择本机可用模型"}
              </p>
            )}
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
