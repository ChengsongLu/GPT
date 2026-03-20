from hashlib import md5
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

router = APIRouter()


def build_static_version() -> str:
    parts = []
    for path in (STATIC_DIR / "app.js", STATIC_DIR / "styles.css"):
        stat = path.stat()
        parts.append(f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}")
    return md5("|".join(parts).encode("utf-8")).hexdigest()[:10]


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        name="index.html",
        context={
            "request": request,
            "page_title": "Git Progress Tracker",
            "asset_version": build_static_version(),
        },
    )
