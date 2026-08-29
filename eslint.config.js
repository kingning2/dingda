import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "**/dist/**",
      "**/target/**",
      "**/node_modules/**",
      "**/.venv/**",
      "**/.tools/**",
      "**/pnpm-lock.yaml",
      ".tmp/**",
      "python/browser_data/**",
      "python/src/dingda_sidecar/crawlers/vendor/**", // vendored 第三方爬虫（同 ruff exclude），不参与 lint
      "tooling/strawberry-perl/**",
      "plugins/**", // 第三方参照项目（xianyu-auto-reply），非本仓库代码，不参与 lint
      "site/**", // 独立 Next.js 应用（自带 next build 类型检查与 lint），不参与根 lint
      "website/**", // 独立 Next.js 应用（自带 eslint.config.mjs），不参与根 lint
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["tooling/scripts/**/*.mjs"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.node,
    },
  },
  {
    files: ["apps/**/*.{ts,tsx}", "packages/**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // react-hooks v7 新增的 React Compiler 规则偏激进，与现有派生 state / effect
      // 数据拉取写法冲突；关闭以免阻断 lint（见 lint:frontend --max-warnings 0）。
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/purity": "off",
      "react-refresh/only-export-components": "off",
    },
  },
  {
    files: ["apps/desktop/src/features/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "@tauri-apps/api",
              message:
                "Feature UI must call Rust via @desk/platform/ipc, not direct Tauri API.",
            },
            {
              name: "@tauri-apps/api/core",
              message:
                "Feature UI must call Rust via @desk/platform/ipc, not direct invoke().",
            },
          ],
        },
      ],
    },
  },
);
