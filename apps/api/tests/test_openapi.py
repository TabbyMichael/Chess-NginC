"""OpenAPI verification (API-021): schema generates and validates."""

from fastapi.testclient import TestClient


def test_openapi_schema_valid(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert spec["info"]["title"] == "Chess Engine API"
    paths = spec["paths"]
    # All Phase 3 + 4 implemented routes present.
    for path in [
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
        "/api/v1/games",
        "/api/v1/games/{game_id}",
        "/api/v1/games/{game_id}/moves",
        "/api/v1/games/{game_id}/undo",
        "/api/v1/games/{game_id}/resign",
        "/api/v1/games/{game_id}/draw-claim",
        "/api/v1/games/{game_id}/engine-move",
    ]:
        assert path in paths, f"missing {path}"
    # Every operation has a response model; mutating routes declare errors.
    for path, ops in paths.items():
        if path in ("/", "/openapi.json"):
            continue
        for method, op in ops.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            assert "responses" in op, f"{method.upper()} {path} has no responses"
            schemas = [
                r.get("content", {}).get("application/json", {}).get("schema", {})
                for r in op["responses"].values()
            ]
            assert any("$$ref" in s or s for s in schemas), f"{method} {path} untyped"
    # All $refs resolve to declared components.
    components = spec.get("components", {}).get("schemas", {})
    refs: list[str] = []

    def collect(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "$$ref" and isinstance(value, str):
                    refs.append(value.split("/")[-1])
                else:
                    collect(value)
        elif isinstance(node, list):
            for item in node:
                collect(item)

    collect(spec["paths"])
    for ref in refs:
        assert ref in components, f"dangling ref {ref}"
