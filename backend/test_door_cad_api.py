from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import get_current_user
from door_cad.api.projects import get_project_repository
from door_cad.repository import DoorCadProjectRepository
from door_cad.router import router


def _request(project_name="API 测试"):
    return {
        "inputs": {"doorWidth": 1800, "doorHeight": 2700},
        "project": {"orderNo": "DD-API-001", "projectName": project_name},
    }


def _client(tmp_path, authenticated=True):
    app = FastAPI()
    app.include_router(router)
    repository = DoorCadProjectRepository(tmp_path / "projects.json", tmp_path / "backups")
    app.dependency_overrides[get_project_repository] = lambda: repository
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "api-user",
            "role": "绘图员",
            "name": "API 测试用户",
        }
    return TestClient(app)


def test_all_routes_require_login(tmp_path):
    client = _client(tmp_path, authenticated=False)
    assert client.post("/api/door-cad/frame/calculate", json=_request()).status_code == 401
    assert client.get("/api/door-cad/frame/projects").status_code == 401


def test_calculate_and_field_validation(tmp_path):
    client = _client(tmp_path)
    response = client.post("/api/door-cad/frame/calculate", json=_request())
    assert response.status_code == 200
    assert response.json()["validation"]["status"] == "PASSED"
    assert len(response.json()["parts"]) == 8

    invalid = _request()
    invalid["inputs"]["doorWidth"] = -1
    response = client.post("/api/door-cad/frame/calculate", json=invalid)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "doorWidth"


def test_project_create_list_get_update_and_audit(tmp_path):
    client = _client(tmp_path)
    response = client.post("/api/door-cad/frame/projects", json=_request())
    assert response.status_code == 201
    created = response.json()
    project_id = created["id"]
    assert created["createdBy"] == "api-user"

    response = client.get("/api/door-cad/frame/projects")
    assert response.status_code == 200
    assert response.json()["projects"][0]["id"] == project_id

    response = client.get(f"/api/door-cad/frame/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["geometry"]["project"]["projectName"] == "API 测试"

    response = client.put(
        f"/api/door-cad/frame/projects/{project_id}",
        json=_request("API 修改后"),
    )
    assert response.status_code == 200
    assert response.json()["id"] == project_id
    assert response.json()["updatedBy"] == "api-user"
    assert response.json()["geometry"]["project"]["projectName"] == "API 修改后"


def test_project_not_found_is_structured(tmp_path):
    client = _client(tmp_path)
    response = client.get("/api/door-cad/frame/projects/missing")
    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "PROJECT_NOT_FOUND",
        "field": "projectId",
        "message": "下料项目不存在",
        "severity": "error",
    }
