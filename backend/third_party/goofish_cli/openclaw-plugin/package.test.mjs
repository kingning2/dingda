import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

const packageJson = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
const bundleManifest = JSON.parse(
  readFileSync(new URL("../.codex-plugin/plugin.json", import.meta.url), "utf8"),
);
const mcpConfig = JSON.parse(
  readFileSync(new URL("../.mcp.json", import.meta.url), "utf8"),
);
const openClawManifest = JSON.parse(
  readFileSync(new URL("../openclaw.plugin.json", import.meta.url), "utf8"),
);
const pyproject = readFileSync(new URL("../pyproject.toml", import.meta.url), "utf8");
const overviewSkill = readFileSync(
  new URL("../skills/goofish-overview/SKILL.md", import.meta.url),
  "utf8",
);

test("keeps the OpenClaw package aligned with goofish-cli", () => {
  const pythonVersion = pyproject.match(/^version = "([^"]+)"$/m)?.[1];
  assert.equal(packageJson.version, pythonVersion);
  assert.equal(bundleManifest.version, pythonVersion);
  assert.equal(openClawManifest.version, pythonVersion);
  assert.equal(openClawManifest.id, "goofish");
  assert.deepEqual(openClawManifest.configSchema, {
    type: "object",
    additionalProperties: false,
    properties: {},
  });
  assert.equal(bundleManifest.name, "goofish");
  assert.equal(bundleManifest.skills, "./skills/");
  assert.equal(bundleManifest.mcpServers, "./.mcp.json");
  assert.equal(bundleManifest.author.name, "fancy");
  assert.equal(bundleManifest.interface.displayName, "Goofish");
  assert.ok(Array.isArray(bundleManifest.interface.defaultPrompt));
  assert.ok(bundleManifest.interface.defaultPrompt.length > 0);
  assert.equal(packageJson.openclaw.extensions, undefined);
  assert.equal(packageJson.openclaw.install.clawhubSpec, "clawhub:openclaw-goofish");
  assert.equal(packageJson.openclaw.install.defaultChoice, "clawhub");
  assert.equal(packageJson.openclaw.install.minHostVersion, ">=2026.6.1");
  assert.equal(packageJson.openclaw.compat.pluginApi, ">=2026.6.1");
  assert.equal(packageJson.peerDependenciesMeta.openclaw.optional, true);
  assert.ok(packageJson.openclaw.release.publishToClawHub);

  const server = mcpConfig.mcpServers.goofish;
  assert.equal(server.command, "uvx");
  assert.deepEqual(server.args, ["--from", `goofish-cli==${pythonVersion}`, "goofish-cli"]);
  assert.equal(server.supportsParallelToolCalls, false);
  assert.deepEqual(server.toolFilter.exclude.toSorted(), [
    "auth_login",
    "auth_reset_guard",
    "message_watch",
    "skills_install",
  ]);
});

test("documents host-specific MCP tool names", () => {
  assert.match(overviewSkill, /goofish__auth_status/);
  assert.match(overviewSkill, /mcp__goofish__auth_status/);
});

test("packs only the OpenClaw bundle metadata, docs, and skills", () => {
  const packDirectory = mkdtempSync(join(tmpdir(), "openclaw-goofish-pack-"));
  const repository = new URL("..", import.meta.url);

  try {
    const output = execFileSync(
      "npm",
      ["pack", "--json", "--pack-destination", packDirectory],
      { cwd: repository, encoding: "utf8" },
    );
    const packed = JSON.parse(output)[0];
    const archive = join(packDirectory, packed.filename);
    const files = new Set(packed.files.map((entry) => entry.path));

    for (const required of [
      "package.json",
      ".codex-plugin/plugin.json",
      ".mcp.json",
      "openclaw.plugin.json",
      "docs/mcp-setup.md",
      "skills/goofish-overview/SKILL.md",
    ]) {
      assert.ok(files.has(required), `missing packed file: ${required}`);
    }

    const sensitiveValue =
      /["'](?:unb|tracknick|cid|toid|send_user_id|mid|msg_id)["']\s*:\s*["'](?!<masked-)[^"']{6,}["']/;
    const rawMessageId = /\b\d{10,}\.PNM\b/;

    for (const entry of files) {
      assert.ok(!entry.startsWith("src/"), `Python source leaked into plugin package: ${entry}`);
      assert.ok(!entry.startsWith("tests/"), `Python tests leaked into plugin package: ${entry}`);
      assert.ok(!entry.includes("cookie"), `cookie-bearing path leaked into package: ${entry}`);

      const content = execFileSync("tar", ["-xOf", archive, `package/${entry}`], {
        encoding: "utf8",
      });
      assert.doesNotMatch(content, sensitiveValue, `account identifier leaked in ${entry}`);
      assert.doesNotMatch(content, rawMessageId, `message identifier leaked in ${entry}`);
    }
  } finally {
    rmSync(packDirectory, { recursive: true, force: true });
  }
});
