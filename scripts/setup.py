#!/usr/bin/env python3
"""One-shot environment setup for a project.

    python scripts/setup.py [project-dir]

Creates <project>/.venv, installs the toolchain (PyMuPDF, Playwright+Chromium,
Pillow, numpy, rembg, psd-tools), and copies the bundled fonts into the project.
Print line at the end tells you which python to use for the other scripts.
"""
import subprocess, sys, os, shutil
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PKGS = ["pymupdf", "playwright", "pillow", "numpy", "rembg", "onnxruntime", "psd-tools"]

def run(*c):
    print("+", " ".join(str(x) for x in c)); subprocess.check_call(c)

def main():
    proj = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
    proj.mkdir(parents=True, exist_ok=True)
    venv = proj/".venv"
    if not venv.exists():
        run(sys.executable, "-m", "venv", str(venv))
    py = str(venv/("Scripts" if os.name == "nt" else "bin")/("python.exe" if os.name == "nt" else "python"))
    run(py, "-m", "pip", "install", "--quiet", "--upgrade", "pip")
    run(py, "-m", "pip", "install", "--quiet", *PKGS)
    run(py, "-m", "playwright", "install", "chromium")
    fdst = proj/"assets/fonts"; fdst.mkdir(parents=True, exist_ok=True)
    for f in ("Montserrat.ttf", "OpenSans.ttf"):
        src = SKILL_DIR/"assets/fonts"/f
        if src.exists() and not (fdst/f).exists():
            shutil.copy(src, fdst/f)
    print("\n✅ setup complete. Use this python for the other scripts:")
    print("  ", py)
    print("   e.g.:", py, "scripts/ingest.py <design-file>", str(proj))

if __name__ == "__main__":
    main()
