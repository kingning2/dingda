/**
 * 当前使用中的模型凭据。
 *
 * 职责：
 *     给其他聊天界面读取「服务端下一次调用会用哪把凭据」，不让用户切完模型后看不到生效结果。
 */

import type { LlmCredentialItem } from "@v2/contracts/model";
import { useEffect, useState } from "react";
import { listLlmCredentials } from "./model-config-api";

/**
 * 读取使用中的模型凭据。
 *
 * # Arguments
 *
 * * `serverReady` - 本地服务是否就绪；未就绪时不发请求
 *
 * # Returns
 *
 * 使用中的凭据；服务未就绪、无凭据或请求失败时为 `null`
 */
export function useActiveLlmCredential(serverReady: boolean): LlmCredentialItem | null {
  const [credential, setCredential] = useState<LlmCredentialItem | null>(null);

  useEffect(() => {
    if (!serverReady) {
      setCredential(null);
      return;
    }

    const controller = new AbortController();
    let mounted = true;
    listLlmCredentials({ signal: controller.signal })
      .then((result) => {
        if (!mounted) return;
        setCredential(result.items.find((item) => item.is_active) ?? null);
      })
      .catch(() => {
        if (mounted) setCredential(null);
      });

    return () => {
      mounted = false;
      controller.abort();
    };
  }, [serverReady]);

  return credential;
}
