/** 输入框附件（由服务端上传后返回，或 mock 阶段使用 data URL 预览）。 */
export interface ComposerAttachmentView {
  id: string;
  name: string;
  mime_type: string;
  preview_url: string;
  size_bytes?: number | null;
}

/** 输入框可选 Agent（来自 daemon 已探测、available=true 的执行引擎）。 */
export interface ComposerAgentOption {
  id: string;
  name: string;
  is_default?: boolean;
  /** 资产页为该 Agent 持久化的默认模型。 */
  preferred_model_id?: string | null;
  models?: ComposerModelOption[];
}

export interface ComposerModelOption {
  id: string;
  label: string;
}

export interface ComposerSubmitPayload {
  message: string;
  agent_id: string;
  /** 为空时由 Agent CLI 使用自身默认模型。 */
  model_id?: string | null;
  attachments: ComposerAttachmentView[];
}
