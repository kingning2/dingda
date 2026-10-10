// simplify-ignore + sdd-cache 纯函数与扩展加载验证（bun 直接运行：bun .pi/tests/_test.ts）
import { mkdtempSync, writeFileSync, readFileSync, existsSync, readdirSync, rmSync } from "node:fs";
import { join } from "node:path";
import { filterBlocks, expandBlocks } from "../extensions/simplify-ignore.ts";
import { cacheKey, hitPayload } from "../extensions/sdd-cache.ts";

let pass = 0, fail = 0;
function eq(name: string, actual: unknown, expected: unknown): void {
	const a = JSON.stringify(actual), e = JSON.stringify(expected);
	if (a === e) { pass++; console.log(`  ok  ${name}`); }
	else { fail++; console.log(`FAIL  ${name}\n      expected: ${e}\n      actual:   ${a}`); }
}

// ── filterBlocks ──────────────────────────────────────────────────────────────
{
	const src = [
		"before",
		"/* simplify-ignore-start: perf-critical */",
		"result[0] = buf[0] ^ key[0];",
		"/* simplify-ignore-end */",
		"middle",
		"# simplify-ignore-start",
		"secret = 1",
		"# simplify-ignore-end",
		"after",
		"",
	].join("\n");
	const { filtered, blocks, warnings } = filterBlocks(src);
	eq("filter: 块数", blocks.length, 2);
	eq("filter: 第一个块保留 reason", blocks[0].reason, "perf-critical");
	eq("filter: js 风格前缀/后缀", [blocks[0].prefix, blocks[0].suffix], ["/* ", " */"]);
	eq("filter: py 风格前缀/后缀", [blocks[1].prefix, blocks[1].suffix], ["# ", ""]);
	eq("filter: 块内容含首尾标记行", blocks[0].content.split("\n").length, 3);
	eq(
		"filter: 占位符形状",
		filtered.split("\n").filter((l) => l.includes("BLOCK_")).map((l) => l.trim()),
		["/* BLOCK_" + blocks[0].hash + ": perf-critical */", "# BLOCK_" + blocks[1].hash],
	);
	// 块折叠：每个 n 行块变 1 行占位符，行数 = 源行数 - 2×(块行数-1)，这里 3+3 → 1+1
	eq("filter: 行数守恒", filtered.split("\n").length, src.split("\n").length - 4);
	eq("filter: 无警告", warnings, []);
}

// 单行块 + unclosed 块
{
	const src = "a\n/* simplify-ignore-start */ x = 1 /* simplify-ignore-end */\nb";
	const { filtered, blocks, warnings } = filterBlocks(src);
	eq("single-line: 块数", blocks.length, 1);
	eq("single-line: 整行隐藏", filtered, `a\n/* BLOCK_${blocks[0].hash} */\nb`);
	eq("single-line: 无警告", warnings, []);
}
{
	const src = "a\n/* simplify-ignore-start */\nnever closed";
	const { filtered, blocks, warnings } = filterBlocks(src);
	eq("unclosed: 不隐藏", blocks.length, 0);
	eq("unclosed: 原样保留", filtered, src);
	eq("unclosed: 有警告", warnings.length, 1);
}

// 行尾换行状态保持
{
	const src = "x\n/* simplify-ignore-start */\ny\n/* simplify-ignore-end */"; // 无末尾换行
	const { filtered } = filterBlocks(src);
	eq("trailing-newline: 不引入末尾换行", filtered.endsWith("\n"), false);
}

// ── expandBlocks（用 filter 产出的 blocks 做 lookup）──────────────────────────
{
	const src = [
		"before",
		"/* simplify-ignore-start: perf-critical */",
		"result[0] = buf[0] ^ key[0];",
		"/* simplify-ignore-end */",
		"middle",
	].join("\n") + "\n";
	const { filtered, blocks } = filterBlocks(src);
	const lookup = new Map(blocks.map((b) => [b.hash, b]));
	const { expanded, warnings } = expandBlocks(filtered, lookup);
	eq("expand: 精确往返还原", expanded, src);
	eq("expand: 无警告", warnings, []);

	// 模型改动 reason 文本 → 模糊匹配兜底；上游语义：渐进还原非精确，可能残留装饰性碎片，但块内容必须回来
	const altered = filtered.replace(`BLOCK_${blocks[0].hash}: perf-critical`, `BLOCK_${blocks[0].hash}: reworded`);
	const r2 = expandBlocks(altered, lookup);
	eq("expand: 模糊匹配块内容还原", r2.expanded.includes("result[0] = buf[0] ^ key[0];"), true);
	eq("expand: 模糊匹配不再含占位符", r2.expanded.includes(`BLOCK_${blocks[0].hash}`), false);
	eq("expand: 模糊匹配有警告", r2.warnings.length, 1);

	// 保护块被整体删除 → 警告
	const emptied = filtered.replace(`/* BLOCK_${blocks[0].hash}: perf-critical */`, "/* gone */");
	const r3 = expandBlocks(emptied, lookup);
	eq("expand: 删除有警告", r3.warnings.some((w) => w.includes("deleted")), true);
}

// ── sdd-cache 纯函数 ──────────────────────────────────────────────────────────
{
	eq("cacheKey: 稳定 32 hex", /^[0-9a-f]{32}$/.test(cacheKey("https://react.dev/x")), true);
	eq("cacheKey: 不同 url 键不同", cacheKey("https://a.com") !== cacheKey("https://b.com"), true);
	const entry = { url: "https://a.com", prompt: "extract signature", etag: 'W/"v1"', last_modified: undefined, content: "hello docs", fetched_at: 1730000000000 };
	const payload = hitPayload("https://a.com", entry);
	eq("hitPayload: 含标记对", payload.includes("BEGIN CACHED CONTENT") && payload.includes("END CACHED CONTENT"), true);
	eq("hitPayload: 含原 prompt", payload.includes("extract signature"), true);
	eq("hitPayload: 含 304 语义", payload.includes("HTTP 304"), true);
}

// ── 扩展加载冒烟（mock pi，验证事件注册形状）──────────────────────────────────
type Handler = (event: any, ctx: any) => Promise<unknown>;
function mockPi() {
	const handlers = new Map<string, Handler[]>();
	const commands: string[] = [];
	return {
		handlers, commands,
		on(name: string, h: Handler) { (handlers.get(name) ?? handlers.set(name, []).get(name)!).push(h); },
		registerCommand(name: string) { commands.push(name); },
	};
}
{
	const pi = mockPi();
	const mod = await import("../extensions/simplify-ignore.ts");
	mod.default(pi as any);
	eq("simplify-ignore: 事件集", [...pi.handlers.keys()].sort(), ["agent_settled", "session_shutdown", "tool_call", "tool_result"]);
	eq("simplify-ignore: 命令", pi.commands, ["simplify-restore"]);
}
{
	const pi = mockPi();
	const mod = await import("../extensions/sdd-cache.ts");
	mod.default(pi as any);
	eq("sdd-cache: 事件集", [...pi.handlers.keys()].sort(), ["tool_call", "tool_result"]);
}

// ── 端到端：真实磁盘上的完整生命周期（read 过滤 → 模型编辑 → 落定恢复）─────
{
	const tmp = mkdtempSync(join(process.env.TEMP ?? "/tmp", "simplify-e2e-"));
	const file = join(tmp, "code.ts");
	const original = "const a = 1;\n/* simplify-ignore-start: perf */\nconst magic = 0x5f3759df;\n/* simplify-ignore-end */\nconst b = 2;\n";
	writeFileSync(file, original);

	const mod = await import("../extensions/simplify-ignore.ts");
	const pi = mockPi();
	mod.default(pi as any);
	const ctx = { cwd: tmp, ui: { notify() {} }, getSignal: () => undefined };
	const call = async (ev: string, event: any) => { for (const h of pi.handlers.get(ev) ?? []) await h(event, ctx); };

	// 1) read 前过滤
	await call("tool_call", { toolName: "read", input: { path: file } });
	const onDisk1 = readFileSync(file, "utf8");
	eq("e2e: read 后磁盘是占位符", onDisk1.includes("BLOCK_"), true);
	eq("e2e: read 后磁盘无保护内容", onDisk1.includes("0x5f3759df"), false);
	eq("e2e: 备份目录存在", existsSync(join(tmp, ".pi", ".simplify-ignore-cache")), true);

	// 2) 模拟模型 edit：改了占位符外面的代码，占位符原样保留
	const edited = onDisk1.replace("const a = 1;", "const a = 10;");
	writeFileSync(file, edited);
	await call("tool_result", { toolName: "edit", input: { path: file } });
	const onDisk2 = readFileSync(file, "utf8");
	eq("e2e: edit 后模型改动保留", onDisk2.includes("const a = 10;"), true);
	eq("e2e: edit 后重新过滤", onDisk2.includes("0x5f3759df"), false);

	// 3) 回合落定 → 兑底展开，磁盘恢复真实内容
	await call("agent_settled", {});
	const onDisk3 = readFileSync(file, "utf8");
	eq("e2e: 落定后还原", onDisk3, original.replace("const a = 1;", "const a = 10;"));
	eq("e2e: 落定后缓存清空", readdirSync(join(tmp, ".pi", ".simplify-ignore-cache")).length, 0);

	// 4) read 一个无标注的文件 → 不碰
	const plain = join(tmp, "plain.ts");
	writeFileSync(plain, "const x = 1;\n");
	await call("tool_call", { toolName: "read", input: { path: plain } });
	eq("e2e: 无标注文件不碰", readFileSync(plain, "utf8"), "const x = 1;\n");
	rmSync(tmp, { recursive: true, force: true });
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail > 0 ? 1 : 0);
