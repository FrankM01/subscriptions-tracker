"""Serve the compiled single-page frontend when a build is available."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI, distribution: Path) -> bool:
    """Mount built assets and the supported browser routes, if built.

    The fallback is limited to frontend routes so unknown API URLs continue to
    return FastAPI's JSON 404 response instead of the SPA document.
    """
    index_file = distribution / "index.html"
    if not index_file.is_file():
        return False

    assets_directory = distribution / "assets"
    if assets_directory.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=assets_directory),
            name="frontend-assets",
        )

    favicon = distribution / "favicon.svg"

    @app.get("/", include_in_schema=False)
    def frontend_home() -> FileResponse:
        return FileResponse(index_file)

    @app.get("/suscripciones", include_in_schema=False)
    def frontend_subscriptions() -> FileResponse:
        return FileResponse(index_file)

    @app.get("/suscripciones/{frontend_path:path}", include_in_schema=False)
    def frontend_subscription_page(frontend_path: str) -> FileResponse:
        return FileResponse(index_file)

    if favicon.is_file():
        @app.get("/favicon.svg", include_in_schema=False)
        def frontend_favicon() -> FileResponse:
            return FileResponse(favicon, media_type="image/svg+xml")

    return True
