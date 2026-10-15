/**
 * 商品监控页。
 *
 * 职责：
 *     页面壳。内容与数据全部交给 `@v2/ui-watch` 的 `WatchHub`，本层不加逻辑。
 */

import { WatchHub } from "@v2/ui-watch";

export function WatchPage() {
  return (
    <section>
      <WatchHub />
    </section>
  );
}
