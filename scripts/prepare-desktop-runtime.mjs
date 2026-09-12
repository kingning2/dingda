#!/usr/bin/env node
/**
 * Cross-platform prepare for GitHub Actions / local:
 *   node scripts/prepare-desktop-runtime.mjs
 * Env:
 *   CAMOUFOX_ZIP          — local zip path (skip download)
 *   CAMOUFOX_RELEASE_TAG  — pin release tag (e.g. v152.0.4-beta.29)
 *   SKIP_CAMOUFOX=1       — skip browser zip (dev only)
 *   SKIP_UV_COPY=1        — skip bundling uv
 *   GITHUB_TOKEN          — raises GitHub API rate limit when fetching Camoufox
 *   REQUIRE_CAMOUFOX=1    — fail if zip missing (default on CI)
 */
import { spawnSync } from "node:child_process";
import {
  copyFileSync,
  cpSync,
  createWriteStream,
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { dirname, basename, join } from "node:path";
import { pipeline } from "node:stream/promises";
import { fileURLToPath } from "node:url";
import { Readable } from "node:stream";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const runtime = join(root, "packages-rs", "client", "resources", "runtime");
const binDir = join(runtime, "bin");
const serverOut = join(runtime, "server");
const foxDir = join(runtime, "camoufox");

// Python uv workspace 根一起进包：壳在 serverOut 里跑
// `uv sync --frozen` → `uv run python -m api`（见 packages-rs/python/src/lifecycle.rs）。
const serverEntries = ["packages-py", "pyproject.toml", "uv.lock"];
const excludedDirs = new Set([
  "__pycache__",
  ".pytest_cache",
  ".venv",
  ".mypy_cache",
  ".ruff_cache",
]);

function copyFilter(src) {
  const name = basename(src);
  if (excludedDirs.has(name)) return false;
  if (name.endsWith(".egg-info")) return false;
  return true;
}

function log(msg) {
  console.log(`[prepare-desktop-runtime] ${msg}`);
}

function camoufoxPlatformTag() {
  const { platform, arch } = process;
  if (platform === "win32" && arch === "x64") return "win.x86_64";
  if (platform === "win32" && arch === "ia32") return "win.i686";
  if (platform === "darwin" && arch === "arm64") return "mac.arm64";
  if (platform === "darwin" && arch === "x64") return "mac.x86_64";
  if (platform === "linux" && arch === "arm64") return "lin.arm64";
  if (platform === "linux" && arch === "x64") return "lin.x86_64";
  throw new Error(`unsupported platform ${platform}/${arch} for Camoufox`);
}

function resolveUvPath() {
  const cmd = process.platform === "win32" ? "where" : "which";
  const r = spawnSync(cmd, ["uv"], { encoding: "utf8" });
  if (r.status !== 0) return null;
  const line = (r.stdout || "").split(/\r?\n/).map((s) => s.trim()).find(Boolean);
  return line || null;
}

function uvBinName() {
  return process.platform === "win32" ? "uv.exe" : "uv";
}

async function download(url, dest, headers = {}) {
  log(`download ${url}`);
  const res = await fetch(url, {
    headers: { "User-Agent": "dingda-prepare-desktop-runtime", ...headers },
    redirect: "follow",
  });
  if (!res.ok || !res.body) {
    throw new Error(`download failed ${res.status} ${url}`);
  }
  mkdirSync(dirname(dest), { recursive: true });
  await pipeline(Readable.fromWeb(res.body), createWriteStream(dest));
}

async function fetchCamoufoxZip(tag, destZip) {
  const local = (process.env.CAMOUFOX_ZIP || "").trim();
  if (local) {
    if (!existsSync(local)) throw new Error(`CAMOUFOX_ZIP not found: ${local}`);
    copyFileSync(local, destZip);
    log(`camoufox from CAMOUFOX_ZIP -> ${destZip}`);
    return;
  }

  const headers = {};
  const token = (process.env.GITHUB_TOKEN || process.env.GH_TOKEN || "").trim();
  if (token) headers.Authorization = `Bearer ${token}`;

  const pin = (process.env.CAMOUFOX_RELEASE_TAG || "").trim();
  const api = pin
    ? `https://api.github.com/repos/daijro/camoufox/releases/tags/${pin}`
    : "https://api.github.com/repos/daijro/camoufox/releases?per_page=15";

  log(`github releases ${pin || "latest list"}`);
  const res = await fetch(api, {
    headers: { Accept: "application/vnd.github+json", "User-Agent": "dingda-prepare", ...headers },
  });
  if (!res.ok) {
    throw new Error(`GitHub API ${res.status} (set GITHUB_TOKEN on CI)`);
  }
  const payload = await res.json();
  const releases = Array.isArray(payload) ? payload : [payload];
  const suffix = `-${tag}.zip`;
  let asset = null;
  for (const rel of releases) {
    const assets = rel.assets || [];
    asset = assets.find((a) => typeof a.name === "string" && a.name.endsWith(suffix));
    if (asset) {
      log(`matched ${rel.tag_name} / ${asset.name}`);
      break;
    }
  }
  if (!asset?.browser_download_url) {
    throw new Error(`no Camoufox asset ending with ${suffix}`);
  }
  await download(asset.browser_download_url, destZip, headers);
  log(`camoufox zip ready ${destZip}`);
}

async function main() {
  log(`root=${root}`);
  mkdirSync(binDir, { recursive: true });
  mkdirSync(serverOut, { recursive: true });
  mkdirSync(foxDir, { recursive: true });

  const tag = camoufoxPlatformTag();
  log(`camoufox platform tag=${tag}`);

  if (process.env.SKIP_UV_COPY !== "1") {
    const uvPath = resolveUvPath();
    if (!uvPath) {
      throw new Error("uv not on PATH (install via astral-sh/setup-uv on CI)");
    }
    const dest = join(binDir, uvBinName());
    copyFileSync(uvPath, dest);
    log(`uv -> ${dest}`);
  }

  for (const name of serverEntries) {
    const src = join(root, name);
    if (!existsSync(src)) {
      throw new Error(
        `missing ${src} (root uv workspace needs pyproject.toml + uv.lock + packages-py/)`,
      );
    }
    const dst = join(serverOut, name);
    rmSync(dst, { recursive: true, force: true });
    cpSync(src, dst, { recursive: true, filter: copyFilter });
    log(`copied ${name}`);
  }

  writeFileSync(
    join(serverOut, "uv.toml"),
    [
      "# desktop packaged mirrors (China); pypi.org as fallback",
      "[[index]]",
      'url = "https://mirrors.aliyun.com/pypi/simple/"',
      "default = true",
      "",
      "[[index]]",
      'url = "https://pypi.org/simple"',
      "",
      "[python]",
      'install-mirror = "https://registry.npmmirror.com/-/binary/python-build-standalone"',
      "",
    ].join("\n"),
    "utf8",
  );
  log("wrote server/uv.toml");

  const destZip = join(foxDir, `camoufox-${tag}.zip`);
  const onCi = process.env.CI === "true" || process.env.GITHUB_ACTIONS === "true";
  const requireFox =
    process.env.REQUIRE_CAMOUFOX === "1" ||
    (onCi && process.env.SKIP_CAMOUFOX !== "1");

  if (process.env.SKIP_CAMOUFOX === "1") {
    writeFileSync(join(foxDir, ".keep"), `place camoufox-${tag}.zip here\n`, "utf8");
    log("SKIP_CAMOUFOX=1");
  } else if (existsSync(destZip) && !process.env.CAMOUFOX_ZIP && !process.env.FORCE_CAMOUFOX_FETCH) {
    log(`keep existing ${destZip}`);
  } else {
    try {
      await fetchCamoufoxZip(tag, destZip);
    } catch (err) {
      if (requireFox) throw err;
      log(`WARN camoufox: ${err instanceof Error ? err.message : err}`);
      writeFileSync(join(foxDir, ".keep"), `place camoufox-${tag}.zip here\n`, "utf8");
    }
  }

  writeFileSync(
    join(runtime, "README.md"),
    [
      "# desktop runtime",
      "",
      "- bin/uv(.exe)",
      "- server/ (packages-py + pyproject.toml + uv.lock + China uv.toml)",
      "- camoufox/camoufox-{platform}.zip",
      "",
      "Prepared on GitHub Actions; shell extracts zip with the `zip` crate.",
      "",
    ].join("\n"),
    "utf8",
  );
  log("done");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
