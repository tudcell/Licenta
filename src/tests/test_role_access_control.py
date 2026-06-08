from __future__ import annotations

from uuid import uuid4

from src.api.app import create_app


def _auth_headers(client, username: str, password: str) -> dict[str, str]:
    login_response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert login_response.status_code == 200
    token = login_response.get_json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_viewer_cannot_create_transaction_and_sees_only_owned_wallets(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("METADATA_DB", str(tmp_path / "audit_metadata.db"))

    app = create_app({"SNAPSHOT_RETENTION_COUNT": 3})

    with app.test_client() as client:
        admin_headers = _auth_headers(client, "admin", "admin123")

        viewer_username = f"viewer_{uuid4().hex[:8]}"
        register_response = client.post(
            "/api/auth/register",
            json={"username": viewer_username, "password": "pass12345", "role": "viewer"},
            headers=admin_headers,
        )
        assert register_response.status_code == 201

        viewer_headers = _auth_headers(client, viewer_username, "pass12345")

        wallet_list_response = client.get("/api/wallets", headers=viewer_headers)
        assert wallet_list_response.status_code == 200
        wallet_payload = wallet_list_response.get_json()["data"]
        assert wallet_payload["wallets"] == []
        assert wallet_payload["count"] == 0

        create_tx_response = client.post(
            "/api/transaction",
            json={
                "transaction_type": "LOGIN",
                "data": {"ip_address": "127.0.0.1"},
            },
            headers=viewer_headers,
        )
        assert create_tx_response.status_code == 403
        error_payload = create_tx_response.get_json()["error"]
        assert error_payload["code"] == "FORBIDDEN"
        assert "Required: admin, operator" in error_payload["message"]
