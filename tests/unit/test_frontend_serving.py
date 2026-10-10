from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from app.frontend import mount_frontend


def test_frontend_routes_serve_index_and_assets_without_capturing_api(tmp_path):
    distribution = tmp_path / "dist"
    assets = distribution / "assets"
    assets.mkdir(parents=True)
    (distribution / "index.html").write_text("<html><div id='root'></div></html>")
    (distribution / "favicon.svg").write_text("<svg></svg>")
    (assets / "app.js").write_text("console.log('web');")

    app = FastAPI()

    @app.get("/subscriptions/health")
    def api_health():
        return JSONResponse({"status": "ok"})

    assert mount_frontend(app, distribution) is True
    client = TestClient(app)

    assert client.get("/").text == "<html><div id='root'></div></html>"
    assert client.get("/suscripciones").status_code == 200
    assert client.get("/suscripciones/abc-123").status_code == 200
    assert client.get("/assets/app.js").text == "console.log('web');"
    assert client.get("/favicon.svg").headers["content-type"] == "image/svg+xml"
    assert client.get("/subscriptions/health").json() == {"status": "ok"}
    assert client.get("/subscriptions/not-found").status_code == 404


def test_frontend_is_not_mounted_until_a_build_exists(tmp_path):
    app = FastAPI()

    assert mount_frontend(app, tmp_path / "missing-dist") is False
