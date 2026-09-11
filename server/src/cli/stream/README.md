# cli/stream

把 CLI stdout 解析成 AgentEvent。

## 本目录文件

- `parse.py` — `parse_lines(format_id, line, state=...)`：Codex JSON / Claude stream-json /
  OpenCode JSON / plain → AgentEvent dict。OpenCode 的 `part.text` 是整段快照不是增量，
  靠 `state` 里的游标切片。

## 子目录

无。
