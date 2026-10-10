// simplify-ignore —— /code-simplify 的块级保护。
// 职责：标注 /* simplify-ignore-start[: reason] */ ... /* simplify-ignore-end */ 的代码块
// 在 read 前替换成 BLOCK_<hash> 占位符（模型看不到保护块），edit/write 后展开占位符保留
// 模型改动并重新过滤，回合结束/会话退出时兜底展开残留。任何注释风格（// /* # <!--）都支持。
// 移植自 addyosmani/agent-skills hooks/simplify-ignore.sh（MIT，见 .agents/references/LICENSE-agent-skills）。
// 备份目录：.pi/.simplify-ignore-cache/（见 .gitignore）。崩溃后可手动 /simplify-restore 恢复。
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { createHash } from "node:crypto";
import {
	chmodSync,
	copyFileSync,
	existsSync,
	mkdirSync,
	readFileSync,
	readdirSync,
	rmSync,
	statSync,
	writeFileSync,
} from "node:fs";
import path from "node:path";

const START = "simplify-ignore-start";
const END = "simplify-ignore-end";

interface Block {
	hash: string; // sha1(块内容) 前 8 位
	content: string; // 含 START/END 标记行在内的完整原文
	reason?: string;
	prefix: string; // START 行里标记之前的文本（注释前缀）
	suffix: string; // START 行里标记之后的注释闭合（" */" 或 " -->"，# 风格为空）
}

// ── 纯函数：过滤（块 → 占位符）与展开（占位符 → 块）────────────────────────────

/** 过滤：返回隐藏块后的文本与提取到的块列表；unclosed 块原样保留并计入警告。 */
export function filterBlocks(src: string): { filtered: string; blocks: Block[]; warnings: string[] } {
	const lines = src.split("\n");
	const out: string[] = [];
	const blocks: Block[] = [];
	const warnings: string[] = [];
	let inBlock = false;
	let buf = "";
	let reason = "";
	let prefix = "";
	let suffix = "";

	const closeBlock = (): string => {
		const h = createHash("sha1").update(buf).digest("hex").slice(0, 8);
		blocks.push({ hash: h, content: buf, reason: reason || undefined, prefix, suffix });
		return reason ? `${prefix}BLOCK_${h}: ${reason}${suffix}` : `${prefix}BLOCK_${h}${suffix}`;
	};

	for (let i = 0; i < lines.length; i++) {
		const line = lines[i];
		if (!inBlock && line.includes(START)) {
			prefix = line.slice(0, line.indexOf(START));
			suffix = line.includes("*/") ? " */" : line.includes("-->") ? " -->" : "";
			const m = line.match(/simplify-ignore-start:[ \t]*/);
			reason = m
				? line.slice((m.index ?? 0) + m[0].length).replace(/[ \t]*\*\/.*$/, "").replace(/[ \t]*-->.*$/, "").replace(/[ \t]+$/, "")
				: "";
			buf = line;
			if (line.includes(END)) {
				// 单行块：START + END 同一行
				out.push(closeBlock());
				buf = ""; reason = ""; prefix = ""; suffix = "";
				continue;
			}
			inBlock = true;
			continue;
		}
		if (inBlock) buf += `\n${line}`;
		if (inBlock && line.includes(END)) {
			out.push(closeBlock());
			inBlock = false; buf = ""; reason = ""; prefix = ""; suffix = "";
			continue;
		}
		if (!inBlock) out.push(line);
	}
	if (inBlock && buf) {
		warnings.push(`unclosed ${START} (block not hidden)`);
		out.push(buf);
	}

	let filtered = out.join("\n");
	// 保持与源文件一致的行尾换行状态
	if (filtered.length > 0 && src.length > 0 && !src.endsWith("\n")) filtered = filtered.replace(/\n$/, "");
	return { filtered, blocks, warnings };
}

/** 展开：把 BLOCK_<hash> 占位符替换回真实代码。精确 → 去reason → 裸hash 三级匹配。 */
export function expandBlocks(src: string, lookup: Map<string, Block>): { expanded: string; warnings: string[] } {
	const warnings: string[] = [];
	const lines = src.split("\n");
	const out: string[] = [];

	for (const line of lines) {
		let cur = line;
		if (cur.includes("BLOCK_")) {
			for (const b of lookup.values()) {
				if (!cur.includes(`BLOCK_${b.hash}`)) continue;
				const exact = b.reason ? `${b.prefix}BLOCK_${b.hash}: ${b.reason}${b.suffix}` : `${b.prefix}BLOCK_${b.hash}${b.suffix}`;
				cur = cur.split(exact).join(b.content);
				if (cur.includes(`BLOCK_${b.hash}`) && !b.content.includes(`BLOCK_${b.hash}`)) {
					// 模型改动了占位符（如 reason 文本）→ 模糊匹配
					warnings.push(`placeholder BLOCK_${b.hash} was modified by model, using fuzzy match`);
					cur = cur.split(`${b.prefix}BLOCK_${b.hash}${b.suffix}`).join(b.content);
					if (cur.includes(`BLOCK_${b.hash}`)) cur = cur.split(`BLOCK_${b.hash}`).join(b.content);
				}
			}
		}
		out.push(cur);
	}

	let expanded = out.join("\n");
	if (expanded.length > 0 && src.length > 0 && !src.endsWith("\n")) expanded = expanded.replace(/\n$/, "");

	// 保护块被整体删除的告警
	for (const b of lookup.values()) {
		if (expanded.includes(`BLOCK_${b.hash}`)) continue;
		const firstLine = b.content.split("\n")[0];
		if (!expanded.includes(firstLine)) warnings.push(`protected block BLOCK_${b.hash} was deleted by model`);
	}
	return { expanded, warnings };
}

// ── 磁盘状态：备份 / 块存储 / 锁，全部在 .pi/.simplify-ignore-cache/ 下 ────────

function cacheRoot(ctx: ExtensionContext): string {
	return path.join(ctx.cwd, ".pi", ".simplify-ignore-cache");
}

function fileId(filePath: string): string {
	return createHash("sha1").update(filePath).digest("hex").slice(0, 16);
}

function loadLookup(ctx: ExtensionContext, fid: string): Map<string, Block> {
	const lookup = new Map<string, Block>();
	const dir = cacheRoot(ctx);
	for (const name of existsSync(dir) ? readdirSync(dir) : []) {
		const m = name.match(new RegExp(`^${fid}\\.block\\.([0-9a-f]{8})$`));
		if (!m) continue;
		const h = m[1];
		const read = (s: string) => (existsSync(path.join(dir, `${fid}.${s}.${h}`)) ? readFileSync(path.join(dir, `${fid}.${s}.${h}`), "utf8") : "");
		lookup.set(h, {
			hash: h,
			content: read("block"),
			reason: read("reason") || undefined,
			prefix: read("prefix"),
			suffix: read("suffix"),
		});
	}
	return lookup;
}

function saveBlocks(ctx: ExtensionContext, fid: string, blocks: Block[]): void {
	const dir = cacheRoot(ctx);
	mkdirSync(dir, { recursive: true });
	// 先清掉本文件旧的块存储，再写新块（与上游语义一致：以最近一次过滤为准）
	for (const name of readdirSync(dir)) {
		if (name.startsWith(`${fid}.block.`) || name.startsWith(`${fid}.reason.`) || name.startsWith(`${fid}.prefix.`) || name.startsWith(`${fid}.suffix.`)) {
			rmSync(path.join(dir, name), { force: true });
		}
	}
	for (const b of blocks) {
		writeFileSync(path.join(dir, `${fid}.block.${b.hash}`), b.content);
		if (b.reason) writeFileSync(path.join(dir, `${fid}.reason.${b.hash}`), b.reason);
		writeFileSync(path.join(dir, `${fid}.prefix.${b.hash}`), b.prefix);
		writeFileSync(path.join(dir, `${fid}.suffix.${b.hash}`), b.suffix);
	}
}

function backupFile(ctx: ExtensionContext, filePath: string, fid: string): void {
	const dir = cacheRoot(ctx);
	mkdirSync(dir, { recursive: true });
	const bak = path.join(dir, `${fid}.bak`);
	copyFileSync(filePath, bak);
	try {
		chmodSync(bak, statSync(filePath).mode & 0o777);
	} catch {
		/* 权限复制失败不影响保护逻辑 */
	}
	writeFileSync(path.join(dir, `${fid}.path`), filePath);
}

/** mkdir 原子锁：另一会话持锁时跳过；陈锁（>60s 且无备份 = 崩溃残留）回收。 */
function acquireLock(ctx: ExtensionContext, fid: string): boolean {
	const lock = path.join(cacheRoot(ctx), `${fid}.lock`);
	mkdirSync(cacheRoot(ctx), { recursive: true });
	try {
		mkdirSync(lock);
		return true;
	} catch {
		try {
			const stale = Date.now() - statSync(lock).mtimeMs > 60_000 && !existsSync(path.join(cacheRoot(ctx), `${fid}.bak`));
			if (stale) {
				rmSync(lock, { recursive: true, force: true });
				mkdirSync(lock);
				return true;
			}
		} catch {
			/* 竞态丢失则放弃本次过滤 */
		}
		return false;
	}
}

function releaseLock(ctx: ExtensionContext, fid: string): void {
	try {
		rmSync(path.join(cacheRoot(ctx), `${fid}.lock`), { recursive: true, force: true });
	} catch {
		/* 忽略 */
	}
}

function hasPlaceholders(ctx: ExtensionContext, filePath: string, fid: string): boolean {
	try {
		const content = readFileSync(filePath, "utf8");
		for (const h of loadLookup(ctx, fid).keys()) if (content.includes(`BLOCK_${h}`)) return true;
	} catch {
		/* 读不到视为无占位符 */
	}
	return false;
}

function notify(ctx: ExtensionContext, msg: string): void {
	try {
		ctx.ui.notify(`[simplify-ignore] ${msg}`, "warning");
	} catch {
		console.error(`[simplify-ignore] ${msg}`);
	}
}

function toolPath(input: unknown): string | undefined {
	const p = (input as { path?: unknown; file_path?: unknown } | undefined);
	const v = p?.path ?? p?.file_path;
	return typeof v === "string" && v.length > 0 ? v : undefined;
}

/** 兜底展开（agent_settled / session_shutdown / /simplify-restore 共用），幂等。 */
export function expandAllTracked(ctx: ExtensionContext): void {
	const dir = cacheRoot(ctx);
	if (!existsSync(dir)) return;
	for (const name of readdirSync(dir)) {
		if (!name.endsWith(".bak")) continue;
		const fid = name.slice(0, -4);
		const pathFile = path.join(dir, `${fid}.path`);
		if (!existsSync(pathFile)) {
			rmSync(path.join(dir, name), { force: true });
			continue;
		}
		const orig = readFileSync(pathFile, "utf8");
		const bak = path.join(dir, name);
		if (existsSync(orig)) {
			if (hasPlaceholders(ctx, orig, fid)) {
				// 磁盘上还有占位符（改动可能绕过 edit/write 事件，如 bash/格式化器）→ 就地展开
				const { expanded, warnings } = expandBlocks(readFileSync(orig, "utf8"), loadLookup(ctx, fid));
				for (const w of warnings) notify(ctx, `${orig}: ${w}`);
				writeFileSync(orig, expanded);
			} else {
				// 占位符全没了 = 文件被整体重写；保留重写稿再回滚备份，两者都不丢
				const recovered = path.join(dir, `${fid}.recovered`);
				copyFileSync(orig, recovered);
				copyFileSync(bak, orig);
				notify(ctx, `no BLOCK_ placeholder left in ${orig}, restored from backup. Rewrite kept at ${recovered}`);
			}
		} else {
			// 文件被移动/删除：备份转 .recovered，不销毁
			const recovered = `${orig}.recovered`;
			mkdirSync(path.dirname(recovered), { recursive: true });
			copyFileSync(bak, recovered);
			notify(ctx, `${orig} was moved/deleted. Recovered original to ${recovered}`);
		}
		for (const n of readdirSync(dir)) {
			if (n.startsWith(`${fid}.`)) rmSync(path.join(dir, n), { force: true, recursive: true });
		}
	}
	// 清理孤儿锁
	for (const name of readdirSync(dir)) {
		if (name.endsWith(".lock")) rmSync(path.join(dir, name), { recursive: true, force: true });
	}
}

// ── 事件接线 ──────────────────────────────────────────────────────────────────

export default function simplifyIgnore(pi: ExtensionAPI): void {
	// Pre:read —— 备份 + 就地过滤（占位符落盘，read 看到的是隐藏后的内容）
	pi.on("tool_call", async (event, ctx) => {
		try {
			if ((event as { toolName?: string }).toolName !== "read") return;
			const filePath = toolPath((event as { input?: unknown }).input);
			if (!filePath || !existsSync(filePath) || !statSync(filePath).isFile()) return;
			const base = path.basename(filePath);
			if (base.startsWith("simplify-ignore")) return; // 文档自身不处理
			const fid = fileId(filePath);
			if (existsSync(path.join(cacheRoot(ctx), `${fid}.bak`))) return; // 已过滤
			if (!readFileSync(filePath, "utf8").includes(START)) return;
			if (!acquireLock(ctx, fid)) return;
			try {
				backupFile(ctx, filePath, fid);
				const { filtered, blocks, warnings } = filterBlocks(readFileSync(filePath, "utf8"));
				for (const w of warnings) notify(ctx, `${filePath}: ${w}`);
				if (blocks.length === 0) {
					// 无实际块（只有 unclosed 残段）→ 不进入保护状态
					rmSync(path.join(cacheRoot(ctx), `${fid}.bak`), { force: true });
					rmSync(path.join(cacheRoot(ctx), `${fid}.path`), { force: true });
					return;
				}
				saveBlocks(ctx, fid, blocks);
				writeFileSync(filePath, filtered); // 同路径覆写，inode 与权限保持
			} finally {
				releaseLock(ctx, fid);
			}
		} catch {
			return; // 过滤失败让 read 正常进行
		}
	});

	// Post:edit|write —— 展开占位符（保留模型改动）→ 更新备份 → 重新过滤
	pi.on("tool_result", async (event, ctx) => {
		try {
			const toolName = (event as { toolName?: string }).toolName;
			if (toolName !== "edit" && toolName !== "write") return;
			const filePath = toolPath((event as { input?: unknown }).input);
			if (!filePath) return;
			const fid = fileId(filePath);
			const dir = cacheRoot(ctx);
			if (!existsSync(path.join(dir, `${fid}.bak`))) return;
			const lookup = loadLookup(ctx, fid);
			if (lookup.size === 0) return;

			const { expanded, warnings } = expandBlocks(readFileSync(filePath, "utf8"), lookup);
			for (const w of warnings) notify(ctx, `${filePath}: ${w}`);
			writeFileSync(filePath, expanded);
			backupFile(ctx, filePath, fid); // 展开态 = 真实态，作为新备份

			const { filtered, blocks, warnings: fw } = filterBlocks(expanded);
			for (const w of fw) notify(ctx, `${filePath}: ${w}`);
			if (blocks.length > 0) {
				saveBlocks(ctx, fid, blocks);
				writeFileSync(filePath, filtered);
			}
			// 无块时保持展开态；备份已在，回合结束兜底统一清理
		} catch {
			return; // 展开/重过滤失败不影响工具结果
		}
	});

	// Stop 等价：回合落定 + 会话退出都兜底展开（幂等）
	pi.on("agent_settled", async (_event, ctx) => {
		expandAllTracked(ctx);
	});
	pi.on("session_shutdown", async (_event, ctx) => {
		expandAllTracked(ctx);
	});

	// 手动恢复（等价上游 `echo '{}' | bash hooks/simplify-ignore.sh`）
	pi.registerCommand("simplify-restore", {
		description: "Expand all simplify-ignore placeholders and restore protected blocks",
		handler: async (_args, ctx) => {
			expandAllTracked(ctx);
			ctx.ui.notify("[simplify-ignore] restore pass complete", "info");
		},
	});
}
