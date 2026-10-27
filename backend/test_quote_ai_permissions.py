"""Quotation AI configuration authorization and credential redaction."""
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import auth
import quote_routes
from business_permissions import ALL_BUSINESS_PERMISSIONS
from quote_database import AiConfigManager


class QuoteAiPermissionsTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="quote-ai-permissions-")
        self.addCleanup(directory.cleanup)
        self.config = AiConfigManager(os.path.join(directory.name, "ai.json"))
        self.config.update({"baseUrl": "https://example.invalid", "model": "test-vision", "apiKey": "test-server-only-secret"})
        patcher = patch.object(quote_routes, "ai_config_db", self.config)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app = FastAPI()
        self.app.include_router(quote_routes.quote_router)

        @self.app.get("/test-super-admin-only")
        def admin_only(user=Depends(auth.require_super_admin)):
            return {"uid": user["uid"]}

        self.user = {"uid": "A", "role": "录入员", "name": "销售小A"}
        self.app.dependency_overrides[auth.get_current_user] = lambda: self.user
        self.client = TestClient(self.app)

    def test_a_can_read_and_update_without_exposing_or_erasing_key(self):
        result = self.client.get("/api/ai-config")
        self.assertEqual(result.status_code, 200, result.text)
        self.assertTrue(result.json()["config"]["hasApiKey"])
        self.assertNotIn("apiKey", result.json()["config"])
        updated = self.client.post("/api/ai-config", json={
            "baseUrl": "https://api.example.invalid", "endpointPath": "/chat/completions",
            "model": "new-vision", "apiKey": "", "prompt": "",
        })
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertNotIn("test-server-only-secret", updated.text)
        self.assertNotIn("apiKey", updated.json()["config"])
        self.assertEqual(self.config.get()["apiKey"], "test-server-only-secret")
        self.assertEqual(self.config.get()["model"], "new-vision")

    def test_super_admin_can_replace_key_but_response_is_redacted(self):
        self.user = {"uid": "root", "role": "超级管理员"}
        self.assertEqual(self.client.get("/api/ai-config").status_code, 200)
        response = self.client.post("/api/ai-config", json={"apiKey": "replacement-secret", "model": "vision"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("replacement-secret", response.text)
        self.assertEqual(self.config.get()["apiKey"], "replacement-secret")

    def test_ordinary_users_cannot_read_or_mutate_even_with_business_grants(self):
        before = self.config.get()
        for user in (
            {"uid": "E", "role": "录入员", "name": "销售小A"},
            {"uid": "a", "role": "录入员"},
            {"uid": "E", "role": "总工"},
            {"uid": "E", "role": "财务", "management_permissions": list(ALL_BUSINESS_PERMISSIONS)},
        ):
            with self.subTest(user=user):
                self.user = user
                self.assertEqual(self.client.get("/api/ai-config").status_code, 403)
                self.assertEqual(self.client.post("/api/ai-config", json={"apiKey": "forbidden"}).status_code, 403)
                self.assertEqual(self.config.get(), before)

    def test_anonymous_requests_are_rejected(self):
        self.app.dependency_overrides.clear()
        self.assertEqual(self.client.get("/api/ai-config").status_code, 401)
        self.assertEqual(self.client.post("/api/ai-config", json={}).status_code, 401)

    def test_other_super_admin_boundaries_are_unchanged(self):
        self.assertEqual(self.client.get("/test-super-admin-only").status_code, 403)
        self.user = {"uid": "root", "role": "超级管理员"}
        self.assertEqual(self.client.get("/test-super-admin-only").status_code, 200)


if __name__ == "__main__":
    unittest.main()
