// sdd-cache —— source-driven-development 技能的跨会话文档缓存。
// 职责：带 url 的工具调用前，用 HTTP 304 语义（ETag / If-Modified-Since）复验本地缓存，
// 命中则拦截调用并返回缓存正文；工具返回后抓取校验头落盘。无校验头的站点永不缓存。
// 移植自 addyosmani/agent-skills hooks/sdd-cache-{pre,post}.sh（MIT，见 .agents/references/LICENSE-agent-skills）。
// 缓存目录：.pi/sdd-cache/（见 .gitignore）。
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";

interface CacheEntry {
	url: string;
	prompt?: string;
	etag?: string;
	last_modified?: string;
	content: string;
	fetched_at: number; // epoch ms
}

/** 缓存键：sha256(url) 前 32 个十六进制字符（与上游一致，128 bit）。 */
export function cacheKey(url: string): string {
	return createHash("sha256").update(url).digest("hex").slice(0, 32);
}

function cacheDir(ctx: ExtensionContext): string {
	return path.join(ctx.cwd, ".pi", "sdd-cache");
}

/** 调试开关：SDD_CACHE_DEBUG=1 或哨兵文件 .pi/sdd-cache/.debug。 */
function dbg(ctx: ExtensionContext, msg: string): void {
	try {
		const dir = cacheDir(ctx);
		if (process.env.SDD_CACHE_DEBUG !== "1" && !existsSync(path.join(dir, ".debug"))) return;
		mkdirSync(dir, { recursive: true });
		writeFileSync(path.join(dir, ".debug.log"), `${new Date().toISOString()} ${msg}\n`, { flag: "a" });
	} catch {
		/* 调试日志永不影响主流程 */
	}
}

function loadEntry(ctx: ExtensionContext, url: string): CacheEntry | undefined {
	const file = path.join(cacheDir(ctx), `${cacheKey(url)}.json`);
	if (!existsSync(file)) return undefined;
	try {
		return JSON.parse(readFileSync(file, "utf8")) as CacheEntry;
	} catch {
		return undefined;
	}
}

/** HEAD 复验：返回 304 才视为新鲜。5s 超时，网络失败一律放行。 */
async function revalidate(url: string, entry: CacheEntry, signal?: AbortSignal): Promise<boolean> {
	const headers: Record<string, string> = {};
	if (entry.etag) headers["If-None-Match"] = entry.etag;
	if (entry.last_modified) headers["If-Modified-Since"] = entry.last_modified;
	try {
		const res = await fetch(url, {
			method: "HEAD",
			redirect: "follow",
			headers,
			signal: signal ?? AbortSignal.timeout(5000),
		});
		return res.status === 304;
	} catch {
		return false;
	}
}

/** HEAD 抓取当前校验头（跟随重定向，fetch 默认 follow）。 */
async function fetchValidators(url: string, signal?: AbortSignal): Promise<{ etag?: string; lastModified?: string }> {
	try {
		const res = await fetch(url, {
			method: "HEAD",
			redirect: "follow",
			signal: signal ?? AbortSignal.timeout(5000),
		});
		return { etag: res.headers.get("etag") ?? undefined, lastModified: res.headers.get("last-modified") ?? undefined };
	} catch {
		return {};
	}
}

/** 命中时回给模型的正文（拦截 reason）。 */
export function hitPayload(url: string, entry: CacheEntry): string {
	const verifiedAt = new Date(entry.fetched_at).toISOString();
	const lines = [
		`[sdd-cache] Cache hit for ${url}`,
		"",
		`Revalidated via HTTP 304; unchanged since ${verifiedAt}. Use the cached`,
		"content below as if the fetch had just returned it.",
		"",
	];
	if (entry.prompt) {
		lines.push(`Original fetch prompt: "${entry.prompt}". If your angle differs, judge`, "whether this reading still covers it.", "");
	}
	lines.push("----- BEGIN CACHED CONTENT -----", entry.content, "----- END CACHED CONTENT -----");
	return lines.join("\n");
}

/** 从工具结果 content 块里抽取正文文本。 */
function extractText(content: unknown): string {
	if (!Array.isArray(content)) return "";
	return content
		.map((b) => (b && typeof b === "object" && (b as { type?: string }).type === "text" ? String((b as { text?: unknown }).text ?? "") : ""))
		.join("\n")
		.trim();
}

function inputUrl(input: unknown): string | undefined {
	const url = (input as { url?: unknown } | undefined)?.url;
	return typeof url === "string" && /^https?:\/\//.test(url) ? url : undefined;
}

export default function sddCache(pi: ExtensionAPI): void {
	// Pre：任何带 http(s) url 的工具调用（fetch_content / 将来的内置 fetch 都覆盖）
	pi.on("tool_call", async (event, ctx) => {
		try {
			const url = inputUrl((event as { input?: unknown }).input);
			if (!url) return;
			dbg(ctx, `[pre] url=${url}`);
			const entry = loadEntry(ctx, url);
			if (!entry) return;
			if (!entry.etag && !entry.last_modified) {
				dbg(ctx, "[pre] entry has no validator, cannot revalidate, bypass");
				return;
			}
			if (!(await revalidate(url, entry, ctx.getSignal()))) {
				dbg(ctx, "[pre] not 304, letting fetch proceed");
				return;
			}
			if (!entry.content) return;
			dbg(ctx, `[pre] cache HIT, blocking with ${entry.content.length} bytes`);
			return { block: true, reason: hitPayload(url, entry) };
		} catch {
			return; // 任何异常都放行，缓存绝不阻塞正常抓取
		}
	});

	// Post：抓取完成后落盘（正文来自工具结果，校验头来自额外一次 HEAD）
	pi.on("tool_result", async (event, ctx) => {
		try {
			const input = (event as { input?: unknown }).input as { url?: unknown; prompt?: unknown } | undefined;
			const url = inputUrl(input);
			if (!url) return;
			const prompt = typeof input?.prompt === "string" ? input.prompt : undefined;
			const content = extractText((event as { content?: unknown }).content);
			dbg(ctx, `[post] url=${url} bytes=${content.length}`);
			const file = path.join(cacheDir(ctx), `${cacheKey(url)}.json`);
			if (!content) {
				dbg(ctx, "[post] no text content in result, skip");
				return;
			}
			const { etag, lastModified } = await fetchValidators(url, ctx.getSignal());
			if (!etag && !lastModified) {
				rmSync(file, { force: true }); // 无校验头：不可复验，清掉旧条目
				dbg(ctx, "[post] no validator from origin, removed stale entry");
				return;
			}
			mkdirSync(cacheDir(ctx), { recursive: true });
			const entry: CacheEntry = { url, prompt, etag, last_modified: lastModified, content, fetched_at: Date.now() };
			const tmp = `${file}.${process.pid}.tmp`;
			writeFileSync(tmp, JSON.stringify(entry, null, 2));
			rmSync(file, { force: true });
			const { renameSync } = await import("node:fs");
			renameSync(tmp, file);
			dbg(ctx, `[post] wrote ${file}`);
		} catch {
			return; // 存缓存失败不影响本次结果
		}
	});
}
