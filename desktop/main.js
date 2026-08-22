/**
 * Sentinel desktop shell (Phase 1, v1.17.18.6).
 *
 * One job: put the dashboard in a real window with no console. On launch it
 * attaches to a backend already serving on 127.0.0.1:8420; when none is
 * running it spawns `run.py` through the project venv python (hidden window
 * — the old Task-Scheduler console-pop problem can't happen here) and waits
 * for /health before opening. Quitting kills ONLY a backend we spawned — an
 * externally started server is left alone.
 *
 * The repo is located by walking up from this app's location (or the
 * SENTINEL_ROOT env var) until run.py is found, so the packaged exe works
 * from desktop/dist/win-unpacked inside a checkout.
 */

const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");

const PORT = process.env.SENTINEL_PORT || "8420";
const BASE_URL = `http://127.0.0.1:${PORT}`;
const HEALTH_TIMEOUT_MS = 1500;
const STARTUP_TIMEOUT_MS = 90_000;

let backendChild = null; // set only when THIS shell spawned the backend

function findRepoRoot() {
  const candidates = [];
  if (process.env.SENTINEL_ROOT) candidates.push(process.env.SENTINEL_ROOT);
  if (app.isPackaged) {
    // <root>/desktop/dist/win-unpacked/Sentinel.exe -> three levels up
    candidates.push(path.resolve(path.dirname(app.getPath("exe")), "..", "..", ".."));
  }
  candidates.push(path.resolve(__dirname, ".."));
  for (const dir of candidates) {
    if (dir && fs.existsSync(path.join(dir, "run.py"))) return path.resolve(dir);
  }
  return null;
}

function venvPython(repoRoot) {
  const candidates = [
    path.join(repoRoot, "backend", ".venv", "Scripts", "python.exe"),
    path.join(repoRoot, ".venv", "Scripts", "python.exe"),
  ];
  return candidates.find((p) => fs.existsSync(p)) || null;
}

function backendHealthy() {
  return new Promise((resolve) => {
    const req = http.get(`${BASE_URL}/health`, { timeout: HEALTH_TIMEOUT_MS }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
    req.on("error", () => resolve(false));
  });
}

async function waitForBackend(timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await backendHealthy()) return true;
    await new Promise((r) => setTimeout(r, 750));
  }
  return false;
}

function startBackend(repoRoot) {
  const python = venvPython(repoRoot);
  if (!python) {
    dialog.showErrorBox(
      "Sentinel — venv not found",
      `No backend virtualenv was found under:\n${repoRoot}\n\n` +
        "Create it once per machine (docs/desktop.md):\n" +
        "  backend\\.venv\\Scripts\\python.exe -m venv .venv\n" +
        "(or point SENTINEL_ROOT at your checkout)."
    );
    return null;
  }
  // windowsHide: the whole point of the shell — no console ever appears.
  const child = spawn(python, ["run.py"], {
    cwd: repoRoot,
    windowsHide: true,
    stdio: "ignore",
  });
  child.on("error", (err) => {
    dialog.showErrorBox("Sentinel — backend failed to start", String(err));
  });
  return child;
}

function stopSpawnedBackend() {
  if (!backendChild || backendChild.exitCode !== null) return;
  if (process.platform === "win32") {
    // /T takes the whole tree: uvicorn + its workers die with the shell.
    spawn("taskkill", ["/PID", String(backendChild.pid), "/T", "/F"], {
      windowsHide: true,
    });
  } else {
    backendChild.kill("SIGTERM");
  }
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 980,
    minHeight: 640,
    autoHideMenuBar: true,
    backgroundColor: "#0a0a0a",
    title: "Sentinel",
  });
  win.loadURL(BASE_URL);
  return win;
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    const [win] = BrowserWindow.getAllWindows();
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });

  app.whenReady().then(async () => {
    const repoRoot = findRepoRoot();
    let attached = await backendHealthy();

    if (!attached && !repoRoot) {
      dialog.showErrorBox(
        "Sentinel — checkout not found",
        "This shell could not locate the Sentinel checkout (walked up from " +
          `${app.getPath("exe")}).\nSet the SENTINEL_ROOT environment variable ` +
          "to the folder containing run.py and launch again."
      );
      app.quit();
      return;
    }

    if (!attached) {
      backendChild = startBackend(repoRoot);
      if (!backendChild) {
        app.quit();
        return;
      }
      attached = await waitForBackend(STARTUP_TIMEOUT_MS);
      if (!attached) {
        dialog.showErrorBox(
          "Sentinel — backend did not come up",
          `Timed out waiting for ${BASE_URL}/health after ` +
            `${STARTUP_TIMEOUT_MS / 1000}s. Check the run log in data/logs/.`
        );
        app.quit();
        return;
      }
    }

    createWindow();

    app.on("before-quit", stopSpawnedBackend);
  });

  app.on("window-all-closed", () => app.quit());
}
