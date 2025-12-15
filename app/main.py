import os
import json
from typing import Dict, Any, List
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse,FileResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from .tiktok import build_auth_url, exchange_code_for_token, ensure_fresh_token, creator_info, direct_post, gen_state

load_dotenv()

CLIENT_KEY = os.environ["TIKTOK_CLIENT_KEY"]
CLIENT_SECRET = os.environ["TIKTOK_CLIENT_SECRET"]
REDIRECT_URI = os.environ["TIKTOK_REDIRECT_URI"]
APP_SECRET_KEY = os.environ.get("APP_SECRET_KEY", "change-me")
VIDEO_BASE_URL = os.environ.get("VIDEO_BASE_URL", "https://social-deployment.netlify.app/").rstrip("/") + "/"

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.add_middleware(SessionMiddleware, secret_key=APP_SECRET_KEY)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Pour l’audit: liste simple (tu peux remplacer par un JSON "manifest" plus tard)
AVAILABLE_VIDEOS = [
    "cat_anglais.mp4",
    "dog_anglais.mp4",
]

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    token = request.session.get("tiktok_token")
    return templates.TemplateResponse("index.html", {"request": request, "connected": bool(token)})

@app.get("/tiktok/login")
def tiktok_login(request: Request):
    state = gen_state()
    request.session["oauth_state"] = state
    url = build_auth_url(CLIENT_KEY, REDIRECT_URI, state)
    return RedirectResponse(url)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@app.get("/tiktok/callback")
def tiktok_callback(request: Request, code: str = "", state: str = ""):
    expected = request.session.get("oauth_state")
    if not expected or state != expected:
        return HTMLResponse("Invalid state", status_code=400)

    token = exchange_code_for_token(CLIENT_KEY, CLIENT_SECRET, code, REDIRECT_URI)
    request.session["tiktok_token"] = token
    return RedirectResponse("/publish")

@app.get("/publish", response_class=HTMLResponse)
def publish_page(request: Request):
    token = request.session.get("tiktok_token")
    if not token:
        return RedirectResponse("/")

    token = ensure_fresh_token(CLIENT_KEY, CLIENT_SECRET, token)
    request.session["tiktok_token"] = token

    info = creator_info(token["access_token"])
    data = info.get("data") or {}
    nickname = data.get("creator_nickname")
    username = data.get("creator_username")
    privacy_opts = data.get("privacy_level_options") or []

    return templates.TemplateResponse(
        "publish.html",
        {
            "request": request,
            "nickname": nickname,
            "username": username,
            "privacy_opts": privacy_opts,
            "videos": AVAILABLE_VIDEOS,
            "video_base": VIDEO_BASE_URL,
        },
    )

@app.post("/publish")
def do_publish(
    request: Request,
    video_filename: str = Form(...),
    caption: str = Form(""),
    privacy_level: str = Form("SELF_ONLY"),
):
    token = request.session.get("tiktok_token")
    if not token:
        return RedirectResponse("/")

    token = ensure_fresh_token(CLIENT_KEY, CLIENT_SECRET, token)
    request.session["tiktok_token"] = token

    video_url = f"{VIDEO_BASE_URL}{video_filename}"

    # Appelle Direct Post
    result = direct_post(token["access_token"], video_url, caption, privacy_level=privacy_level)

    # Affichage simple
    request.session["last_result"] = result
    return RedirectResponse(url="/done", status_code=303)

@app.get("/done", response_class=HTMLResponse)
def done(request: Request):
    token = request.session.get("tiktok_token")
    result = request.session.get("last_result")
    return templates.TemplateResponse("done.html", {"request": request, "connected": bool(token), "result": result})

@app.get("/terms", response_class=HTMLResponse)
def terms_page(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request})

@app.get("/privacy", response_class=HTMLResponse)
def privacy_page(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})


@app.get("/tiktoklZMH3IJtaGmfDxImk57gOXUJNC2kdZsu.txt")
def tiktok_domain_verify_1():
    return FileResponse(
        "app/domain_verification/tiktoklZMH3IJtaGmfDxImk57gOXUJNC2kdZsu.txt",
        media_type="text/plain"
    )

@app.get("/tiktokiBuxjByVLGIO8QUUT9sB0BPwgEDdG19B.txt")
def tiktok_domain_verify_2():
    return FileResponse(
        "app/domain_verification/tiktokiBuxjByVLGIO8QUUT9sB0BPwgEDdG19B.txt",
        media_type="text/plain"
    )

from pathlib import Path

@app.get("/_debug_static")
def debug_static():
    base = Path(__file__).resolve().parent / "static"
    return {
        "static_dir": str(base),
        "exists": base.exists(),
        "files": [p.name for p in base.glob("*")],
    }
