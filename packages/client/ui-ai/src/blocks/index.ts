/**
 * 聊天块的装配点。
 *
 * 职责：
 *   副作用导入全部块文件，让它们在模块加载时完成自注册；并转发注册表接口。
 *
 * 设计说明：
 *   - 注册发生在**模块加载时**，所以下面这些 import 不能省。少写哪个块，
 *     Chat 就会为那个 kind 渲染「未知块类型」占位 —— 这是有意的可见降级。
 *   - 加一个块 = 新建块文件（末尾 registerBlock）+ 这里加一行 import。
 *     Chat 与 registry 都不用改。
 *   - 不 re-export 块组件本身：要渲染块就走注册表（`resolveBlock`）。
 *     直接 import 具体块会把「谁认识哪个块」重新散出去，注册表就白做了。
 */

import "./user";
import "./thinking";
import "./step";
import "./text";

export { registerBlock, resolveBlock } from "../chat/registry";
