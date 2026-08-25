/**
 * 设置弹窗 — 免责声明与使用条款。
 */

import { AlertTriangle } from "@desk/ui/icons";

const DISCLAIMER_CONTENT =
  "数据存储说明\n" +
  "1. 本软件为本地桌面应用，运行数据（含登录凭证、账号信息、商品与订单等业务数据）默认存储在您设备本机。\n" +
  "2. 上述数据仅用于本软件功能运行与业务管理，不会主动上传至第三方（连接电商平台接口所必需的网络请求除外）。\n" +
  "3. 请您妥善保管设备与系统账户，避免未授权访问。\n\n" +
  "用户须知\n" +
  "1. 您应确保使用本软件的行为符合相关电商平台规则及法律法规。\n" +
  "2. 因账号共享、登录信息泄露、违规操作或本地环境安全问题导致的损失，由您自行承担。\n" +
  "3. 建议定期备份重要数据。因软件故障、第三方平台接口变更、网络异常或不可抗力导致的损失，本软件不承担赔偿责任。\n" +
  "隐私与风险提示\n" +
  "1. 连接电商平台账号前，请充分评估风险，勿在未评估的情况下用于生产或敏感账号。\n" +
  "2. 触发平台风控时，验证操作需通过真实浏览器环境完成；相关记录可在「设置 → 风控日志」中查看。\n" +
  "3. 使用本软件即表示您已阅读并同意上述条款，并愿意自行承担相应责任。";

/** 免责声明面板。 */
export function DisclaimerPanel() {
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 flex items-center gap-2 text-amber-600">
        <AlertTriangle className="size-5 shrink-0" aria-hidden />
        <p className="text-[length:var(--text-sm)] font-medium">请仔细阅读以下条款</p>
      </div>
      <div className="rounded-xl border border-border bg-muted/20 p-5">
        <pre className="whitespace-pre-wrap font-sans text-[length:var(--text-sm)] leading-relaxed text-foreground/90">
          {DISCLAIMER_CONTENT}
        </pre>
      </div>
    </div>
  );
}
