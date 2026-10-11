import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";

const frontendRoot = process.cwd();
const projectRoot = resolve(frontendRoot, "..");
const python = join(projectRoot, ".venv", "bin", "python");
const temporaryData = mkdtempSync(join(tmpdir(), "subscriptions-web-e2e-"));
const databaseUrl = `sqlite:///${join(temporaryData, "test.db")}`;
const environment = {
  ...process.env,
  SUBSCRIPTIONS_DATABASE_URL: databaseUrl,
  SUBSCRIPTIONS_ENV: "test",
};

const migration = spawnSync(python, ["-m", "alembic", "upgrade", "head"], {
  cwd: projectRoot,
  env: environment,
  stdio: "inherit",
});

if (migration.status !== 0) {
  rmSync(temporaryData, { recursive: true, force: true });
  process.exit(migration.status ?? 1);
}

const server = spawn(python, [
  "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8010",
], { cwd: projectRoot, env: environment, stdio: "inherit" });

async function waitForServer() {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (server.exitCode !== null) throw new Error("FastAPI stopped before the E2E test started.");
    try {
      const response = await fetch("http://127.0.0.1:8010/openapi.json");
      if (response.ok) return;
    } catch {
      // The server is still starting.
    }
    await delay(200);
  }
  throw new Error("FastAPI did not start in time.");
}

let testExit = 1;
try {
  await waitForServer();
  const playwright = join(frontendRoot, "node_modules", ".bin", "playwright");
  const testRun = spawnSync(playwright, ["test"], {
    cwd: frontendRoot,
    env: process.env,
    stdio: "inherit",
  });
  testExit = testRun.status ?? 1;
} catch (error) {
  console.error(error);
} finally {
  server.kill("SIGTERM");
  await delay(250);
  if (server.exitCode === null) server.kill("SIGKILL");
  rmSync(temporaryData, { recursive: true, force: true });
}

process.exit(testExit);
