#!/usr/bin/env node
/**
 * 部署后通知搜索引擎抓取 sitemap。
 *
 * - Bing：无需密钥，ping 即可
 * - Google Search Console：需仓库 Secret `GOOGLE_SERVICE_ACCOUNT_JSON`
 *   且将该服务账号加为 Search Console 属性 Owner
 *
 * 环境变量：
 *   SITEMAP_URL  — 完整 sitemap 地址（默认 GitHub Pages）
 *   GSC_SITE_URL — Search Console 中的站点 URL（须与后台属性一致，带尾斜杠）
 */
import crypto from "node:crypto";

const SITEMAP_URL =
  process.env.SITEMAP_URL ?? "https://kingning2.github.io/dingda/sitemap.xml";
const GSC_SITE_URL =
  process.env.GSC_SITE_URL ?? "https://kingning2.github.io/dingda/";
const SA_JSON = process.env.GOOGLE_SERVICE_ACCOUNT_JSON?.trim();

function base64url(input) {
  return Buffer.from(input)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

async function pingBing() {
  const pingUrl = `https://www.bing.com/ping?sitemap=${encodeURIComponent(SITEMAP_URL)}`;
  const res = await fetch(pingUrl);
  if (res.ok) {
    console.log(`[bing] ping ok — ${SITEMAP_URL}`);
    return;
  }
  // Bing 已逐步停用 ping 接口（常见 410），不阻断后续 Google 提交
  console.warn(`[bing] ping skipped (${res.status}) — use IndexNow or Search Console instead`);
}

async function getGoogleAccessToken(serviceAccount) {
  const now = Math.floor(Date.now() / 1000);
  const header = base64url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const payload = base64url(
    JSON.stringify({
      iss: serviceAccount.client_email,
      scope: "https://www.googleapis.com/auth/webmasters",
      aud: "https://oauth2.googleapis.com/token",
      iat: now,
      exp: now + 3600,
    }),
  );
  const signer = crypto.createSign("RSA-SHA256");
  signer.update(`${header}.${payload}`);
  signer.end();
  const signature = signer
    .sign(serviceAccount.private_key)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
  const jwt = `${header}.${payload}.${signature}`;

  const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
      assertion: jwt,
    }),
  });
  const tokenJson = await tokenRes.json();
  if (!tokenRes.ok || !tokenJson.access_token) {
    throw new Error(
      `Google OAuth failed (${tokenRes.status}): ${JSON.stringify(tokenJson)}`,
    );
  }
  return tokenJson.access_token;
}

async function submitGoogleSearchConsole(accessToken) {
  const site = encodeURIComponent(GSC_SITE_URL);
  const feed = encodeURIComponent(SITEMAP_URL);
  const url = `https://www.googleapis.com/webmasters/v3/sites/${site}/sitemaps/${feed}`;

  const res = await fetch(url, {
    method: "PUT",
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (res.status === 204 || res.status === 200) {
    console.log(`[google] sitemap submitted — ${SITEMAP_URL}`);
    return;
  }

  const body = await res.text();
  throw new Error(`Google Search Console submit failed (${res.status}): ${body.slice(0, 500)}`);
}

async function main() {
  console.log(`Sitemap: ${SITEMAP_URL}`);
  console.log(`GSC site: ${GSC_SITE_URL}`);

  await pingBing();

  if (!SA_JSON) {
    console.log(
      "[google] skipped — set repository secret GOOGLE_SERVICE_ACCOUNT_JSON to enable",
    );
    console.log(
      "[google] also add the service account email as Owner in Search Console",
    );
  } else {
    let serviceAccount;
    try {
      serviceAccount = JSON.parse(SA_JSON);
    } catch {
      throw new Error("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON");
    }

    const token = await getGoogleAccessToken(serviceAccount);
    await submitGoogleSearchConsole(token);
  }

  console.log("[toutiao] manual — verify at https://zhanzhang.toutiao.com/");
  console.log(`[toutiao] then submit sitemap: ${SITEMAP_URL}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
