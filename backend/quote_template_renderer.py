import json
import os
import subprocess
from pathlib import Path
from typing import Dict


def _resolve_project_root(module_file: str = __file__) -> Path:
    module_dir = Path(module_file).resolve().parent
    if module_dir.name == "backend":
        return module_dir.parent
    return module_dir


_BASE_DIR = str(_resolve_project_root())
_QUOTE_TEMPLATE_DIR = os.path.join(_BASE_DIR, "quote-template-pdf")
_RENDER_SCRIPT = os.path.join(_QUOTE_TEMPLATE_DIR, "scripts", "render-artifacts.mjs")


def _resolve_playwright_executable() -> str:
    candidates = [
        os.environ.get("PLAYWRIGHT_EXECUTABLE_PATH", ""),
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]

    for path in candidates:
        if path and os.path.exists(path):
            return path

    return ""


def render_quote_template_artifacts(quote: Dict, output_dir: str) -> Dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)

    quote_json_path = os.path.join(output_dir, "quote-data.json")
    with open(quote_json_path, "w", encoding="utf-8") as f:
        json.dump(quote, f, ensure_ascii=False, indent=2)

    env = os.environ.copy()
    executable_path = _resolve_playwright_executable()
    if executable_path:
        env["PLAYWRIGHT_EXECUTABLE_PATH"] = executable_path

    subprocess.run(
        ["node", _RENDER_SCRIPT, quote_json_path, output_dir],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    artifacts = {
        "html_path": os.path.join(output_dir, "quote.html"),
        "jpg_path": os.path.join(output_dir, "quote.jpg"),
        "pdf_path": os.path.join(output_dir, "quote.pdf"),
        "preview_path": os.path.join(output_dir, "quote-preview.png"),
    }

    missing = [name for name, path in artifacts.items() if name != "preview_path" and not os.path.exists(path)]
    if missing:
        raise RuntimeError(f"Missing rendered artifacts: {', '.join(missing)}")

    return artifacts
