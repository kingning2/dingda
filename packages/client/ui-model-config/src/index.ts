/**
 * 模型配置域：模型凭据列表、供应商选择与连通性检测。
 *
 * 包入口只暴露 `ModelConfigHub`（页面级装配）。
 * 纯函数（掩码展示、表单取值）走子路径 `@v2/ui-model-config/model-credential-view`
 * 给测试用，不从这里转发 —— 按仓库约定，不为跨域调用留转发壳。
 */
export { ModelConfigHub } from "./model-config-hub";
