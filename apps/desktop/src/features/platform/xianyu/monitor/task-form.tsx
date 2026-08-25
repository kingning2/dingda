import { type Dispatch, type SetStateAction } from "react";
import { AsyncButton, Button, Input, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Switch, Textarea } from "@desk/ui";
import { ChevronDown, ChevronUp, Trash2 } from "@desk/ui/icons";

export interface MonitorForm {
  name: string;
  intent: string;
  keywords: string;
  accountId: string;
  aiAccountId: string;
  aiFailoverEnabled: boolean;
  aiAccountOrder: string[];
  intervalMinutes: string;
  aiCriteria: string;
  enabled: boolean;
}

export const EMPTY_FORM: MonitorForm = {
  name: "",
  intent: "",
  keywords: "",
  accountId: "",
  aiAccountId: "",
  aiFailoverEnabled: true,
  aiAccountOrder: [],
  intervalMinutes: "5",
  aiCriteria: "",
  enabled: true,
};

export interface AiAccountOption {
  id: string;
  label: string;
}

function sanitizeAiAccountOrder(order: string[], primaryId: string): string[] {
  const seen = new Set<string>();
  return order.filter((id) => {
    if (!id || id === primaryId || seen.has(id)) {
      return false;
    }
    seen.add(id);
    return true;
  });
}

function moveAiAccountOrder(order: string[], index: number, delta: -1 | 1): string[] {
  const nextIndex = index + delta;
  if (nextIndex < 0 || nextIndex >= order.length) {
    return order;
  }
  const next = [...order];
  const [item] = next.splice(index, 1);
  next.splice(nextIndex, 0, item!);
  return next;
}

export interface TaskFormProps {
  form: MonitorForm;
  /** 是否编辑已有任务（显示收起按钮）。 */
  editingExisting: boolean;
  accountOptions: { id: string; label: string }[];
  aiAccountOptions: AiAccountOption[];
  aiAccountLabelMap: Map<string, string>;
  saving: boolean;
  generating: boolean;
  setForm: Dispatch<SetStateAction<MonitorForm>>;
  onSave: () => void;
  onGenerateKeywords: () => void;
  onCancel: () => void;
}

/** 监控任务编辑表单（新建 / 编辑）。 */
export function TaskForm({
  form,
  editingExisting,
  accountOptions,
  aiAccountOptions,
  aiAccountLabelMap,
  saving,
  generating,
  setForm,
  onSave,
  onGenerateKeywords,
  onCancel,
}: TaskFormProps) {
  const addableAiAccounts = aiAccountOptions.filter(
    (option) => option.id !== form.aiAccountId && !form.aiAccountOrder.includes(option.id),
  );

  return (
    <div className="space-y-3 rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium">{editingExisting ? "编辑任务" : "新建任务"}</h2>
        {editingExisting ? (
          <Button size="sm" variant="ghost" onClick={onCancel}>
            收起
          </Button>
        ) : null}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5 sm:col-span-2">
          <label className="text-xs text-muted-foreground">任务名称</label>
          <Input
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            placeholder="例如：MacBook Air M1 捡漏"
          />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <label className="text-xs text-muted-foreground">购买意图（AI 生成关键词）</label>
          <Textarea
            value={form.intent}
            onChange={(event) => setForm({ ...form, intent: event.target.value })}
            placeholder="描述你想买什么、预算、成色要求等"
            rows={3}
          />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <label className="text-xs text-muted-foreground">AI 筛选标准（决策用）</label>
          <Textarea
            value={form.aiCriteria}
            onChange={(event) => setForm({ ...form, aiCriteria: event.target.value })}
            placeholder="例如：M1 芯片、16G 内存、价格低于 3500、个人闲置优先"
            rows={3}
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs text-muted-foreground">闲鱼账号</label>
          <Select value={form.accountId} onValueChange={(value) => setForm({ ...form, accountId: value })}>
            <SelectTrigger>
              <SelectValue placeholder="选择账号" />
            </SelectTrigger>
            <SelectContent>
              {accountOptions.map((account) => (
                <SelectItem key={account.id} value={account.id}>
                  {account.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <label className="text-xs text-muted-foreground">AI 账号（关键词 + 决策）</label>
          <Select
            value={form.aiAccountId}
            onValueChange={(value) =>
              setForm((current) => ({
                ...current,
                aiAccountId: value,
                aiAccountOrder: sanitizeAiAccountOrder(current.aiAccountOrder, value),
              }))
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="选择 AI 账号" />
            </SelectTrigger>
            <SelectContent>
              {aiAccountOptions.map((option) => (
                <SelectItem key={option.id} value={option.id}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {aiAccountOptions.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              请先在「AI 配置」中添加 DeepSeek / 豆包账号，或使用本地 AI。
            </p>
          ) : null}
        </div>
        <div className="flex items-center gap-2 sm:col-span-2">
          <Switch
            checked={form.aiFailoverEnabled}
            onCheckedChange={(checked) => setForm({ ...form, aiFailoverEnabled: checked })}
          />
          <span className="text-sm">余额不足时自动切换备用 AI</span>
        </div>
        {form.aiFailoverEnabled ? (
          <div className="space-y-2 sm:col-span-2">
            <label className="text-xs text-muted-foreground">
              备用账号顺序（首选失败后依次尝试；留空则自动使用其余 AI 账号）
            </label>
            {form.aiAccountOrder.length > 0 ? (
              <ul className="space-y-2">
                {form.aiAccountOrder.map((id, index) => (
                  <li
                    key={id}
                    className="flex items-center gap-2 rounded-lg border border-border bg-muted/20 px-2 py-1.5"
                  >
                    <span className="min-w-0 flex-1 truncate text-sm">
                      {index + 1}. {aiAccountLabelMap.get(id) ?? id}
                    </span>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={index === 0}
                      aria-label="上移"
                      onClick={() =>
                        setForm({
                          ...form,
                          aiAccountOrder: moveAiAccountOrder(form.aiAccountOrder, index, -1),
                        })
                      }
                    >
                      <ChevronUp className="size-4" />
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={index === form.aiAccountOrder.length - 1}
                      aria-label="下移"
                      onClick={() =>
                        setForm({
                          ...form,
                          aiAccountOrder: moveAiAccountOrder(form.aiAccountOrder, index, 1),
                        })
                      }
                    >
                      <ChevronDown className="size-4" />
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      aria-label="移除"
                      onClick={() =>
                        setForm({
                          ...form,
                          aiAccountOrder: form.aiAccountOrder.filter((item) => item !== id),
                        })
                      }
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted-foreground">未配置时将按 AI 配置中的账号自动尝试。</p>
            )}
            {addableAiAccounts.length > 0 ? (
              <Select
                key={form.aiAccountOrder.join(",")}
                onValueChange={(value) => {
                  setForm({ ...form, aiAccountOrder: [...form.aiAccountOrder, value] });
                }}
              >
                <SelectTrigger className="max-w-xs">
                  <SelectValue placeholder="添加备用账号" />
                </SelectTrigger>
                <SelectContent>
                  {addableAiAccounts.map((option) => (
                    <SelectItem key={option.id} value={option.id}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : null}
          </div>
        ) : null}
        <div className="space-y-1.5">
          <label className="text-xs text-muted-foreground">定时间隔（分钟）</label>
          <Input
            type="number"
            min={1}
            value={form.intervalMinutes}
            onChange={(event) => setForm({ ...form, intervalMinutes: event.target.value })}
          />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <div className="flex items-center justify-between gap-2">
            <label className="text-xs text-muted-foreground">搜索关键词（可 AI 生成）</label>
            <Button size="sm" variant="outline" disabled={generating} onClick={onGenerateKeywords}>
              {generating ? "生成中…" : "AI 生成关键词"}
            </Button>
          </div>
          <Textarea
            value={form.keywords}
            onChange={(event) => setForm({ ...form, keywords: event.target.value })}
            placeholder="每行一个关键词；留空则运行时自动生成"
            rows={3}
          />
        </div>
        <div className="flex items-center gap-2 sm:col-span-2">
          <Switch
            checked={form.enabled}
            onCheckedChange={(checked) => setForm({ ...form, enabled: checked })}
          />
          <span className="text-sm">启用定时爬取（按间隔自动运行）</span>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <AsyncButton loading={saving} onClick={onSave}>
          保存任务
        </AsyncButton>
      </div>
    </div>
  );
}
