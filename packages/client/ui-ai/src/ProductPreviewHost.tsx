/**
 * 商品预览 Host：按平台打开闲鱼 / 小红书各自的预览卡。
 */

import { useEffect, useState } from "react";
import { subscribeProductPreview, type ProductPreviewTarget } from "@v2/ui-crawler/product-preview";
import { XianyuPreviewDialog } from "./XianyuPreviewDialog";
import { XiaohongshuPreviewDialog } from "./XiaohongshuPreviewDialog";

/** 挂在 AI 工作 Layout：订阅 openProductPreview 并分流。 */
export function ProductPreviewHost() {
  const [item, setItem] = useState<ProductPreviewTarget | null>(null);

  useEffect(() => subscribeProductPreview(setItem), []);

  const open = Boolean(item);
  const isXhs = item?.platform === "xiaohongshu";

  return (
    <>
      <XianyuPreviewDialog
        open={open && !isXhs}
        item={!isXhs ? item : null}
        onOpenChange={(next) => {
          if (!next) setItem(null);
        }}
      />
      <XiaohongshuPreviewDialog
        open={open && isXhs}
        item={isXhs ? item : null}
        onOpenChange={(next) => {
          if (!next) setItem(null);
        }}
      />
    </>
  );
}
