# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — frozen Sentinel backend (Phase 2, v1.17.18.6).

Build from the repo root:
    backend\\.venv\\Scripts\\python.exe -m PyInstaller --noconfirm desktop/server/sentinel-server.spec

Produces desktop/resources/server-runtime/ (onedir: faster startup and fewer
AV false positives than onefile). The Electron shell ships this folder via
extraResources and spawns sentinel-server.exe with per-machine data env vars.
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
BACKEND = os.path.join(SPECPATH, "..", "..", "backend")

datas = [
    # The staged dashboard + Jinja prompt templates must ride inside the
    # bundle; frozen code resolves them relative to sys._MEIPASS/app/...
    (os.path.join(BACKEND, "app", "static"), "app/static"),
    (os.path.join(BACKEND, "app", "data"), "app/data"),
]
datas += collect_data_files("chromadb")

hiddenimports = [
    "app.main",
    # uvicorn's lazy loader imports these dynamically — invisible to static
    # analysis without explicit listing.
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    # chromadb vendors native/binary pieces behind dynamic imports.
    "chromadb",
    "hnswlib",
]
hiddenimports += collect_submodules("chromadb")
hiddenimports += collect_submodules("app")

a = Analysis(
    ["server_entry.py"],
    pathex=[os.path.join(BACKEND)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sentinel-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="server-runtime",
)
