from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.auth.auth_api import router
from src.app.auth.auth_service import InvalidCredentialsError, LoginThrottledError


class DummyAuthService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    def authenticate(self, username: str, password: str, client_ip: str | None = None) -> tuple[str, int]:
        self.calls.append((username, password, client_ip))
        if username == "fail":
            raise InvalidCredentialsError("invalid")
        if username == "blocked":
            raise LoginThrottledError("throttled")
        return ("token-123", 100)


def build_client(service: DummyAuthService) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.auth_service = service
    return TestClient(app)


def test_login_returns_token_on_success() -> None:
    service = DummyAuthService()
    client = build_client(service)

    response = client.post("/api/login", json={"username": "serg", "password": "secret"})

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "token-123"
    assert data["token_type"] == "bearer"
    assert service.calls[-1][0] == "serg"


def test_login_returns_401_on_invalid_credentials() -> None:
    service = DummyAuthService()
    client = build_client(service)

    response = client.post("/api/login", json={"username": "fail", "password": "secret"})

    assert response.status_code == 401
    assert response.json()["detail"]["failure_reason"] == "invalid_credentials"


def test_login_returns_429_when_throttled() -> None:
    service = DummyAuthService()
    client = build_client(service)

    response = client.post("/api/login", json={"username": "blocked", "password": "secret"})

    assert response.status_code == 429
    assert response.json()["detail"]["failure_reason"] == "throttled"

