import os
import shutil
import sys
import tempfile


os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="door_quote_export_test_")

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

import importlib
import config as cfg

importlib.reload(cfg)

import main as backend_main
import quote_routes


PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASSED, FAILED
    if condition:
      PASSED += 1
      print(f"  PASS {name}")
    else:
      FAILED += 1
      print(f"  FAIL {name} -- {detail}")


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def sample_quote():
    return {
        "id": 1,
        "customerName": "Cloud Test",
        "projectName": "Render Flow",
        "quoteDate": "2026-05-22",
        "items": [
            {
                "id": 1,
                "accessoryId": None,
                "productName": "Test Door",
                "width": 1200,
                "height": 2100,
                "openDirection": "Right",
                "unit": "m2",
                "unitPrice": 1680,
                "rowOrder": 0,
            }
        ],
    }


def test_renderer_module_contract():
    section("1. Renderer Module Contract")
    import quote_template_renderer as renderer
    import quote_excel

    local_root = renderer._resolve_project_root(os.path.join(BACKEND_DIR, "quote_template_renderer.py"))
    container_root = renderer._resolve_project_root("/app/quote_template_renderer.py")
    excel_container_root = quote_excel._resolve_project_root("/app/quote_excel.py")

    check("renderer resolves local repo root", os.path.basename(local_root) != "backend", str(local_root))
    check("renderer resolves container app root", str(container_root).replace("\\", "/").endswith("/app"), str(container_root))
    check("excel resolves container app root", str(excel_container_root).replace("\\", "/").endswith("/app"), str(excel_container_root))
    check("renderer script exists", os.path.exists(renderer._RENDER_SCRIPT), renderer._RENDER_SCRIPT)
    check("excel template exists", os.path.exists(quote_excel.TEMPLATE_PATH), quote_excel.TEMPLATE_PATH)

    tmpdir = tempfile.mkdtemp(prefix="quote_renderer_contract_")
    original_run = renderer.subprocess.run
    original_resolver = renderer._resolve_playwright_executable

    def fake_run(cmd, check, capture_output, text, env):
        globals()["check"]("renderer uses node", cmd[0] == "node", str(cmd))
        globals()["check"]("renderer passes script path", cmd[1].endswith("render-artifacts.mjs"), str(cmd))
        globals()["check"]("renderer passes quote json path", cmd[2].endswith("quote-data.json"), str(cmd))
        globals()["check"]("renderer passes output dir", cmd[3] == tmpdir, str(cmd))
        globals()["check"]("renderer exports chromium hint", bool(env.get("PLAYWRIGHT_EXECUTABLE_PATH")), str(env))

        with open(os.path.join(tmpdir, "quote.html"), "w", encoding="utf-8") as f:
            f.write("<html>ok</html>")
        with open(os.path.join(tmpdir, "quote.jpg"), "wb") as f:
            f.write(b"\xff\xd8\xff")
        with open(os.path.join(tmpdir, "quote.pdf"), "wb") as f:
            f.write(b"%PDF-1.4")

        class Result:
            stdout = "ok"
            stderr = ""

        return Result()

    renderer.subprocess.run = fake_run
    renderer._resolve_playwright_executable = lambda: "C:/fake/chrome.exe"
    try:
        artifacts = renderer.render_quote_template_artifacts(sample_quote(), tmpdir)
        check("html artifact exists", artifacts["html_path"].endswith("quote.html"), str(artifacts))
        check("jpg artifact exists", artifacts["jpg_path"].endswith("quote.jpg"), str(artifacts))
        check("pdf artifact exists", artifacts["pdf_path"].endswith("quote.pdf"), str(artifacts))
    finally:
        renderer.subprocess.run = original_run
        renderer._resolve_playwright_executable = original_resolver
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_export_routes_use_template_renderer():
    section("2. Export Routes Use Template Renderer")
    original_get_by_id = quote_routes.quote_db.get_by_id
    original_renderer = quote_routes.render_quote_template_artifacts

    def fake_get_by_id(_quote_id):
        return sample_quote()

    def fake_renderer(_quote, output_dir):
        html_path = os.path.join(output_dir, "quote.html")
        jpg_path = os.path.join(output_dir, "quote.jpg")
        pdf_path = os.path.join(output_dir, "quote.pdf")

        with open(html_path, "w", encoding="utf-8") as f:
            f.write("<html><body>preview</body></html>")
        with open(jpg_path, "wb") as f:
            f.write(b"\xff\xd8\xff")
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4")

        return {
            "html_path": html_path,
            "jpg_path": jpg_path,
            "pdf_path": pdf_path,
        }

    quote_routes.quote_db.get_by_id = fake_get_by_id
    quote_routes.render_quote_template_artifacts = fake_renderer
    try:
        xlsx_resp = quote_routes.export_quote_xlsx(1)
        check(
            "xlsx export response class",
            xlsx_resp.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            str(xlsx_resp.media_type),
        )
        check("xlsx export filename set", xlsx_resp.filename.endswith(".xlsx"), str(xlsx_resp.filename))
        check("xlsx export path exists", os.path.exists(xlsx_resp.path), str(xlsx_resp.path))
        check("xlsx export has content", os.path.getsize(xlsx_resp.path) > 1000, str(xlsx_resp.path))
        os.unlink(xlsx_resp.path)

        html_resp = quote_routes.quote_preview_html(1)
        check("preview html response class", html_resp.media_type == "text/html", str(html_resp.media_type))
        check("preview html contains body", b"preview" in html_resp.body, str(html_resp.body[:80]))

        jpg_resp = quote_routes.export_quote_jpg(1)
        check("jpg export response class", jpg_resp.media_type == "image/jpeg", str(jpg_resp.media_type))
        check("jpg export filename set", jpg_resp.filename.endswith(".jpg"), str(jpg_resp.filename))
        check("jpg export path exists", os.path.exists(jpg_resp.path), str(jpg_resp.path))
        with open(jpg_resp.path, "rb") as f:
            check("jpg export is jpeg bytes", f.read(3) == b"\xff\xd8\xff", str(jpg_resp.path))

        pdf_resp = quote_routes.export_quote_pdf(1)
        check("pdf export response class", pdf_resp.media_type == "application/pdf", str(pdf_resp.media_type))
        check("pdf export filename set", pdf_resp.filename.endswith(".pdf"), str(pdf_resp.filename))
        check("pdf export path exists", os.path.exists(pdf_resp.path), str(pdf_resp.path))
        with open(pdf_resp.path, "rb") as f:
            check("pdf export is pdf bytes", f.read(4) == b"%PDF", str(pdf_resp.path))
    finally:
        quote_routes.quote_db.get_by_id = original_get_by_id
        quote_routes.render_quote_template_artifacts = original_renderer


if __name__ == "__main__":
    try:
        test_renderer_module_contract()
        test_export_routes_use_template_renderer()
        section("Results")
        print(f"  PASS: {PASSED}")
        print(f"  FAIL: {FAILED}")
        if FAILED:
            sys.exit(1)
    finally:
        shutil.rmtree(os.environ["DATA_DIR"], ignore_errors=True)
