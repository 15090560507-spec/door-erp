"""Reviewed reference motifs: exact geometry, durable jobs and optional templates."""
import io
import os
import tempfile
import unittest
import json
import time
from unittest.mock import patch

from PIL import Image
from pydantic import ValidationError

from reference_pattern_models import PatternDefinition, PatternPlacement, AppliedPattern
from reference_pattern_geometry import pattern_contours
from reference_pattern_service import ReferencePatternService, infer_pattern


def motif():
    return {"name": "回纹", "paths": [{"points": [[0, 0], [1, 0], [1, 1], [0, 1]], "closed": True}],
            "stretch_x": [0.3, 0.7], "stretch_y": [0.3, 0.7], "warnings": []}


class ReferencePatternTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.calls = []
        self.config = {"baseUrl": "https://example.invalid/v1", "endpointPath": "/chat/completions", "apiKey": "secret", "model": "vision-model", "prompt": "QUOTE PROMPT MUST NOT LEAK"}
        def infer(config, image):
            self.calls.append((config, image))
            return {"supported": True, **motif()}
        self.service = ReferencePatternService(os.path.join(self.temp.name, "patterns.db"), lambda: self.config, infer=infer, auto_start=False)
        buffer = io.BytesIO()
        Image.new("RGB", (100, 200), "white").save(buffer, "PNG")
        self.image = buffer.getvalue()

    def test_geometry_preserves_width_and_stays_inside(self):
        placement = PatternPlacement(definition=motif(), band_width=20, inset=10, detail_x=50, detail_y=50)
        for width, height in [(300, 1000), (1200, 300)]:
            result = pattern_contours(placement, width, height)
            self.assertTrue(result["loops"])
            self.assertEqual(result["bounds"], [10.0, 10.0, width - 10.0, height - 10.0])
            self.assertEqual(result["band_width"], 20)
        with self.assertRaises(ValueError):
            pattern_contours(placement, 80, 1000)

    def test_graph_rejects_nonfinite_diagonal_and_too_many_points(self):
        for points in [[[0, 0], [1, 1]], [[0, 0], [float("nan"), 0]], [[0, 0], [2, 0]]]:
            with self.assertRaises(ValidationError):
                PatternDefinition.model_validate({**motif(), "paths": [{"points": points}]})
        with self.assertRaises(ValidationError):
            PatternDefinition.model_validate({**motif(), "stretch_x": [0.8, 0.2]})
        with self.assertRaises(ValidationError):
            AppliedPattern(definition=motif(), reviewed=False)
        repeated = {"points": [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]], "closed": True}
        self.assertEqual(len(PatternDefinition.model_validate({**motif(), "paths": [repeated]}).paths[0].points), 4)

    def test_close_parallel_bands_cannot_silently_merge(self):
        definition = {**motif(), "paths": [{"points": [[0, 0], [0, 1]], "closed": False}, {"points": [[0.01, 0], [0.01, 1]], "closed": False}]}
        with self.assertRaisesRegex(ValueError, "局部线距"):
            pattern_contours(PatternPlacement(definition=definition), 500, 1400)

    def test_mirror_and_fixed_corner_details_are_deterministic(self):
        definition = {**motif(), "stretch_x": [0.2, 0.6]}
        placement = PatternPlacement(definition=definition, detail_x=50, detail_y=40)
        normal = pattern_contours(placement, 500, 1200)
        placement.mirror = True
        mirrored = pattern_contours(placement, 500, 1200)
        for first, second in zip(normal["centerlines"][0], mirrored["centerlines"][0]):
            self.assertAlmostEqual(first[0] + second[0], 500)
            self.assertAlmostEqual(first[1], second[1])
        placement.mirror = False
        wider = pattern_contours(placement, 900, 1600)
        self.assertEqual(normal["centerlines"][0][0], wider["centerlines"][0][0])

    def test_jobs_are_idempotent_explicit_and_durable(self):
        job = self.service.submit("A", self.image, "request-1")
        self.assertEqual(job["status"], "queued")
        self.assertEqual(len(self.calls), 0)
        retry = self.service.submit("A", self.image, "request-1")
        self.assertEqual(job["id"], retry["id"])
        self.service.run_job(job["id"], self.config)
        result = self.service.get_job(job["id"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["definition"]["name"], "回纹")
        self.assertEqual(self.service.get_image(job["id"])[:2], b"\xff\xd8")
        self.assertNotIn("apiKey", str(result))
        self.assertNotIn("QUOTE PROMPT", str(result))
        self.assertEqual(len(self.calls), 1)
        restarted = ReferencePatternService(self.service.path, lambda: self.config, auto_start=False)
        self.assertEqual(restarted.get_job(job["id"])["status"], "completed")
        self.assertEqual(restarted.list_templates("A"), [])

    def test_worker_pool_completes_without_an_open_browser(self):
        threaded = ReferencePatternService(os.path.join(self.temp.name, "threaded.db"), lambda: self.config,
                                           infer=lambda *_: {"supported": True, **motif()})
        self.addCleanup(threaded.pool.shutdown, wait=True)
        job = threaded.submit("A", self.image, "background-test")
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            status = threaded.get_job(job["id"])["status"]
            if status == "completed":
                break
            time.sleep(0.02)
        self.assertEqual(threaded.get_job(job["id"])["status"], "completed")

    def test_templates_are_opt_in_owner_scoped_and_snapshots(self):
        snapshot = AppliedPattern(definition=motif(), reviewed=True)
        template = self.service.save_template("A", "常用回纹", snapshot)
        self.assertEqual(len(self.service.list_templates("A")), 1)
        self.assertEqual(self.service.list_templates("B"), [])
        snapshot.definition.name = "本单修改"
        self.assertEqual(template["snapshot"]["definition"]["name"], "回纹")

    def test_invalid_image_no_configuration_and_model_failure(self):
        with self.assertRaises(ValueError):
            self.service.submit("A", b"not-image", "invalid")
        self.config["apiKey"] = ""
        with self.assertRaises(ValueError):
            self.service.submit("A", self.image, "no-config")
        self.config["apiKey"] = "secret"
        job = self.service.submit("A", self.image, "bad-model")
        self.service.infer = lambda *_: {"supported": False, "reason": "曲线无法识别"}
        self.service.run_job(job["id"], self.config)
        failed = self.service.get_job(job["id"])
        self.assertEqual(failed["status"], "failed")
        self.assertIn("曲线", failed["error"])

    def test_restart_and_limits_are_visible_not_silent(self):
        one = self.service.submit("A", self.image, "one")
        self.service.submit("A", self.image, "two")
        with self.assertRaises(RuntimeError):
            self.service.submit("A", self.image, "three")
        restarted = ReferencePatternService(self.service.path, lambda: self.config, auto_start=False)
        self.assertEqual(restarted.get_job(one["id"])["status"], "failed")
        self.assertIn("重启", restarted.get_job(one["id"])["error"])

    def test_network_payload_is_separate_from_quote_prompt(self):
        import httpx
        original = httpx.Client
        def respond(request):
            data = json.loads(request.content)
            self.assertEqual(data["model"], "vision-model")
            self.assertNotIn("QUOTE PROMPT", str(data))
            self.assertEqual(data["response_format"], {"type": "json_object"})
            self.assertEqual(data["messages"][1]["content"][1]["type"], "image_url")
            return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"supported": True, **motif()})}}]})
        with patch("reference_pattern_service.httpx.Client", side_effect=lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs)):
            self.assertTrue(infer_pattern(self.config, self.image)["supported"])

    def test_authenticated_routes_and_optional_template(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import auth
        import reference_pattern_routes as routes
        app = FastAPI(); app.include_router(routes.router)
        user = {"uid": "A", "role": "录入员"}
        app.dependency_overrides[auth.get_current_user] = lambda: user
        with patch.object(routes, "service", self.service), patch.object(routes, "shared_connection", return_value=self.config):
            client = TestClient(app)
            public = client.get("/api/reference-patterns/connection")
            self.assertNotIn("secret", public.text)
            self.assertEqual(set(public.json()), {"model", "configured"})
            response = client.post("/api/reference-patterns/jobs", files={"file": ("image.png", self.image, "image/png")}, data={"request_key": "api-test"})
            self.assertEqual(response.status_code, 202, response.text)
            job_id = response.json()["job"]["id"]
            self.service.run_job(job_id, self.config)
            self.assertEqual(client.get(f"/api/reference-patterns/jobs/{job_id}").json()["job"]["status"], "completed")
            self.assertEqual(client.get("/api/reference-patterns/templates").json(), {"templates": []})
            user["role"] = "仓管员"
            self.assertEqual(client.post("/api/reference-patterns/jobs", files={"file": ("image.png", self.image)}, data={"request_key": "denied"}).status_code, 403)
            self.assertEqual(client.get(f"/api/reference-patterns/jobs/{job_id}/source").status_code, 403)
        app.dependency_overrides.clear()
        self.assertEqual(TestClient(app).get("/api/reference-patterns/connection").status_code, 401)


class ReferencePatternCadTest(unittest.TestCase):
    def snapshot(self):
        return AppliedPattern(definition=motif(), reviewed=True, detail_x=40, detail_y=40).model_dump(mode="json")

    def test_applied_geometry_reaches_real_dxf(self):
        from test_glass_pattern_controls import draw
        baseline = draw("无线条")
        custom = draw("参考图线稿", reference_patterns={"panel_b2": self.snapshot()})
        def count(doc):
            return len([entity for entity in doc.modelspace().query("LWPOLYLINE") if entity.dxf.layer == "A-DOOR-PANEL"])
        self.assertGreater(count(custom), count(baseline))
        linked = draw("参考图线稿", back_panel_same_as_front=True, reference_patterns={"panel_b2": self.snapshot()})
        preset = draw("参考图线稿", panel_preset="竖条款", back_panel_same_as_front=True, reference_patterns={"panel_b2": self.snapshot()})
        self.assertEqual(count(preset), count(linked))
        self.assertFalse(custom.audit().errors)
        with self.assertRaisesRegex(ValueError, "尚未识别"):
            draw("参考图线稿")

    def test_transom_and_front_back_linkage(self):
        from test_glass_pattern_controls import draw, panel_geometry
        opts = {"reference_patterns": {"panel_b2": self.snapshot()}, "back_panel_same_as_front": True}
        linked = draw("参考图线稿", **opts)
        separate = draw("参考图线稿", reference_patterns=opts["reference_patterns"], back_panel_same_as_front=False)
        self.assertNotEqual(panel_geometry(linked), panel_geometry(separate))
        transom = draw("无线条", sel_qc="玻璃", qc_height=600, qc_glass_style="参考图线稿", reference_patterns={"transom": self.snapshot()})
        self.assertFalse(transom.audit().errors)

    def test_task_snapshot_roundtrip_never_needs_template_or_model(self):
        from models import CADRequest, TaskCreateRequest, TaskUpdateRequest
        from main import build_cad_params, _cad_cache_key
        payload = {"reference_patterns": {"panel_b2": self.snapshot()}, "panel_b2_glass_style": "参考图线稿"}
        create = TaskCreateRequest(params=payload).params
        update = TaskUpdateRequest(params=json.loads(json.dumps(create))).params
        cad = CADRequest(**update)
        self.assertEqual(build_cad_params(cad)[2]["reference_patterns"], payload["reference_patterns"])
        pending = CADRequest(**{**update, "reference_pattern_jobs": {"panel_b2": "a" * 32}})
        self.assertEqual(_cad_cache_key(cad), _cad_cache_key(pending))
        with self.assertRaises(ValidationError):
            TaskCreateRequest(params={"reference_patterns": {"panel_b2": {**self.snapshot(), "reviewed": False}}})


if __name__ == "__main__":
    unittest.main()
