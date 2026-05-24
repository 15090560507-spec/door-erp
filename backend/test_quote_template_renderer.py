import asyncio
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

from starlette.datastructures import Headers, UploadFile


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
        "noticeText": "\u672c\u62a5\u4ef7\u542b\u7a0e\u5de5\u5382\u7ed3\u7b97\u4ef7\uff0c\u4e0d\u542b\u6728\u7bb1\u3002",
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


def test_quote_html_contains_uppercase_amount_and_editable_notice():
    section("2. Quote HTML Amount And Notice")

    repo_root = os.path.dirname(BACKEND_DIR)
    tmpdir = tempfile.mkdtemp(prefix="quote_html_contract_")
    quote_path = os.path.join(tmpdir, "quote-data.json")
    with open(quote_path, "w", encoding="utf-8") as f:
        import json

        json.dump(sample_quote(), f, ensure_ascii=False)

    code = """
import { buildQuoteHtml } from './quote-template-pdf/src/renderQuote.mjs';
const html = await buildQuoteHtml(process.argv[1]);
process.stdout.write(html);
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", code, quote_path],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    html = result.stdout
    check("node renderer exits successfully", result.returncode == 0, result.stderr)
    check(
        "uppercase amount is rendered",
        "\u4eba\u6c11\u5e01\u8086\u4edf\u8d30\u4f70\u53c1\u62fe\u8086\u5143\u6574" in html,
        html[html.find("\u5408\u8ba1\u603b\u91d1\u989d"):html.find("\u5408\u8ba1\u603b\u91d1\u989d") + 160],
    )
    check(
        "custom notice text is rendered",
        sample_quote()["noticeText"] in html,
        html[html.find("\u672c\u62a5\u4ef7"):html.find("\u672c\u62a5\u4ef7") + 80],
    )
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_export_routes_use_template_renderer():
    section("3. Export Routes Use Template Renderer")
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


def test_ai_analysis_parses_openai_compatible_response():
    section("4. AI Analysis Parses OpenAI Compatible Response")

    original_get_config = quote_routes.ai_config_db.get
    original_urlopen = quote_routes.urllib.request.urlopen

    quote_routes.ai_config_db.get = lambda: {
        "baseUrl": "https://api.example.test/v1",
        "endpointPath": "/chat/completions",
        "apiKey": "sk-test",
        "model": "vision-test",
        "prompt": "Return JSON only.",
    }

    def fake_urlopen(req, timeout):
        payload = json.loads(req.data.decode("utf-8"))
        globals()["check"]("AI request uses configured model", payload["model"] == "vision-test", str(payload))
        globals()["check"]("AI request uses model-compatible temperature", payload["temperature"] == 1, str(payload))
        image_part = payload["messages"][1]["content"][1]["image_url"]["url"]
        globals()["check"]("AI request includes data URL image", image_part.startswith("data:image/jpeg;base64,"), image_part[:40])

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                content = json.dumps({
                    "customerName": "\u56fe\u7eb8\u5ba2\u6237",
                    "projectName": "\u56fe\u7eb8\u9879\u76ee",
                    "outerWidth": 1200,
                    "outerHeight": 2100,
                    "openDirection": "\u5185\u53f3\u5f00",
                    "items": [
                        {
                            "productName": "\u9632\u76d7\u95e8",
                            "width": 1200,
                            "height": 2100,
                            "openDirection": "\u5185\u53f3\u5f00",
                            "unit": "m2",
                            "unitPrice": 0,
                        }
                    ],
                    "accessories": ["\u6307\u7eb9\u9501"],
                    "notes": "\u6d4b\u8bd5",
                }, ensure_ascii=False)
                return json.dumps({
                    "choices": [{"message": {"content": f"```json\n{content}\n```"}}]
                }, ensure_ascii=False).encode("utf-8")

        return Response()

    quote_routes.urllib.request.urlopen = fake_urlopen

    upload = UploadFile(
        filename="door.jpg",
        file=io.BytesIO(b"\xff\xd8\xff"),
        headers=Headers({"content-type": "image/jpeg"}),
    )

    try:
        result = asyncio.run(quote_routes.analyze_drawing(upload))
        check("AI response has filename", result["filename"] == "door.jpg", str(result))
        check("AI response has analysis", result["analysis"]["customerName"] == "\u56fe\u7eb8\u5ba2\u6237", str(result))
        check("AI response normalizes items", result["analysis"]["items"][0]["productName"] == "\u9632\u76d7\u95e8", str(result))
    finally:
        quote_routes.ai_config_db.get = original_get_config
        quote_routes.urllib.request.urlopen = original_urlopen


if __name__ == "__main__":
    try:
        test_renderer_module_contract()
        test_quote_html_contains_uppercase_amount_and_editable_notice()
        test_export_routes_use_template_renderer()
        test_ai_analysis_parses_openai_compatible_response()
        section("Results")
        print(f"  PASS: {PASSED}")
        print(f"  FAIL: {FAILED}")
        if FAILED:
            sys.exit(1)
    finally:
        shutil.rmtree(os.environ["DATA_DIR"], ignore_errors=True)
