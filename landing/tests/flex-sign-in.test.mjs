import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { createInterface } from "node:readline";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { chromium, webkit } from "playwright";

const fixturePath = fileURLToPath(new URL("./flex_oidc_fixture.py", import.meta.url));

test("LinkedIn sign-in through the Flex HTTP adapter", { timeout: 60_000 }, async (t) => {
  const fixture = spawn("python3", [fixturePath], { stdio: ["ignore", "pipe", "inherit"] });
  t.after(() => fixture.kill());
  const lines = createInterface({ input: fixture.stdout });
  const [port] = await Promise.race([
    once(lines, "line"),
    once(fixture, "exit").then(([code]) => { throw new Error(`Flex fixture exited with status ${code}`); }),
  ]);
  assert.match(port, /^\d+$/);
  const desk = `https://127.0.0.1:${port}`;
  const issuer = `https://localhost:${port}`;

  for (const engine of [chromium, webkit]) {
    await t.test(engine.name(), async (browserTest) => {
      const browser = await engine.launch();
      browserTest.after(() => browser.close());

      const scenarios = [
        { name: "approved", callback: 200 },
        { name: "last-cookie", callback: 200 },
        { name: "unmatched", callback: 403, message: /couldn’t match this address/ },
        { name: "expired", callback: 401, message: /sign-in attempt is no longer active/ },
        { name: "timeout", callback: 503, message: /sign-in service is temporarily unavailable/ },
      ];

      for (const scenario of scenarios) {
        await browserTest.test(scenario.name, async () => {
          const context = await browser.newContext({ ignoreHTTPSErrors: true });
          try {
            await context.addCookies([{ name: "fixture-scenario", value: scenario.name, url: issuer }]);
            const page = await context.newPage();
            page.setDefaultTimeout(12_000);
            await page.goto(issuer, { waitUntil: "domcontentloaded" });
            const [callback] = await Promise.all([
              page.waitForResponse((response) => new URL(response.url()).pathname === "/api/callback/linkedin"),
              page.getByRole("link", { name: "Continue with LinkedIn" }).click(),
            ]);
            assert.equal(callback.status(), scenario.callback);
            assert.equal((await callback.allHeaders())["cache-control"], "no-store");

            if (scenario.callback === 200) {
              const callbackCookies = await callback.headerValues("set-cookie");
              assert.ok(callbackCookies.some((cookie) => cookie.startsWith("__Host-gmg-flex-desk=")));
              const target = `${desk}/api/desk?from=linkedin`;
              await page.waitForURL(target);
              await page.getByRole("button", { name: "Find member" }).waitFor();
              const cookies = await context.cookies(desk);
              const session = cookies.find((cookie) => cookie.name === "__Host-gmg-flex-desk");
              assert.ok(session?.secure && session.httpOnly && session.sameSite === "Lax");
              assert.ok(!cookies.some((cookie) => cookie.name === "__Host-gmg-flex-oauth"));
              await context.clearCookies({ name: "__Host-gmg-flex-desk" });
              assert.equal((await page.reload({ waitUntil: "domcontentloaded" })).status(), 401);
              await page.getByText(/couldn’t open your session after sign-in/).waitFor();
            } else {
              await page.getByText(scenario.message).waitFor();
              assert.ok(!((await context.cookies(desk)).some((cookie) => cookie.name === "__Host-gmg-flex-desk")));
            }
            assert.equal(await page.getByRole("link", { name: "Try LinkedIn sign-in again" }).count(), 1);
            assert.equal(await page.getByRole("button", { name: "Find member" }).count(), 0);
          } finally {
            await context.close();
          }
        });
      }
    });
  }
});
