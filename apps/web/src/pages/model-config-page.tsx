/**
 * 模型配置页（供应商与 API Key）。
 *
 * 职责：
 *     页面壳。内容与数据全部交给 `@v2/ui-model-config` 的 `ModelConfigHub`，本层不加逻辑。
 */
import { ModelConfigHub } from "@v2/ui-model-config";

/** 模型配置页。 */
export function ModelConfigPage() {
  return (
    <section>
      <ModelConfigHub />
    </section>
  );
}
