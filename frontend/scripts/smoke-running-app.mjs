import assert from "node:assert/strict";

const apiUrl = process.env.API_URL ?? "http://127.0.0.1:8000";
const webUrl = process.env.WEB_URL ?? "http://127.0.0.1:3000";

async function json(path, init) {
  const response = await fetch(`${apiUrl}${path}`, init);
  assert.equal(response.ok, true, `${path} returned HTTP ${response.status}`);
  return response.json();
}

const health = await json("/api/health");
assert.equal(health.status, "ok");
assert.equal(health.database.ready, true);

const state = await json("/api/state");
assert.equal(typeof state.version, "number");
assert.equal(typeof state.environment.co2_ppm, "number");
assert.equal(typeof state.devices.ac.power, "boolean");

const invalidCommand = await fetch(`${apiUrl}/api/devices/fan/commands`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ values: { speed: 99 }, source: "manual" }),
});
assert.equal(invalidCommand.status, 422);
assert.equal((await invalidCommand.json()).error.code, "invalid_device_value");

for (const route of ["/", "/dashboard", "/history"]) {
  const response = await fetch(`${webUrl}${route}`);
  assert.equal(response.ok, true, `${route} returned HTTP ${response.status}`);
  const html = await response.text();
  assert.match(html, /<html[^>]+lang="vi"/);
  assert.match(html, /FlatMate Comfort/);
}

const removedPreferencesPage = await fetch(`${webUrl}/preferences`);
assert.equal(removedPreferencesPage.status, 404, "/preferences must stay removed");

const controller = new AbortController();
const timeout = setTimeout(() => controller.abort(), 5_000);
try {
  const response = await fetch(`${apiUrl}/api/events`, { signal: controller.signal });
  assert.equal(response.ok, true);
  const firstChunk = await response.body.getReader().read();
  assert.equal(firstChunk.done, false);
  assert.match(new TextDecoder().decode(firstChunk.value), /event: (snapshot|heartbeat)/);
} finally {
  clearTimeout(timeout);
  controller.abort();
}

console.log("Running-app smoke checks passed: API, guardrail, SSE, and three web routes.");
