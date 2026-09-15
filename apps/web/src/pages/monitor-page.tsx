/**
 * 商品监控页。
 *
 * 职责：
 *     页面壳。内容与数据全部交给 `@v2/ui-monitor` 的 `MonitorHub`，本层不加逻辑。
 */

import { MonitorHub } from "@v2/ui-monitor";

export function MonitorPage() {
  return (
    <section>
      <MonitorHub />
    </section>
  );
}
