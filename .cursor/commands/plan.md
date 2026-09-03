---
description: OpenDesk 变更前计划模板，强制先做边界与契约检查。
---

先输出一个最小计划，不直接改代码。计划必须包含：

1. **边界定位**
   - 改动属于 React / Rust / Python 哪一层
   - 是否会跨层，是否符合 React -> Rust -> Python

2. **契约检查**
   - 是否需要先改 `contracts/`
   - 若需要，明确顺序：Contract -> Rust -> Python -> React

3. **最小改动范围**
   - 只列要改的目录与文件类型
   - 说明不改哪些无关区域

4. **验证计划**
   - `pnpm lint`
   - `python skills/opendesk/scripts/check_architecture.py`
   - `python skills/opendesk/scripts/check_boundary.py`
   - `python skills/opendesk/scripts/check_contracts.py`
