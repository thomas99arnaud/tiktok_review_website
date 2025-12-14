import time
import json
import secrets
import requests
from typing import Dict, Any, Optional
from urllib.parse import urlencode

TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
TIKTOK_DIRECT_POST_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"

SCOPES = "user.info.basic,video.upload,video.publish"

def build_auth_url(client_key: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_key": client_key,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{TIKTOK_AUTH_URL}?{urlencode(params)}"

def exchange_code_for_token(client_key: str, client_secret: str, code: str, redirect_uri: str) -> Dict[str, Any]:
    data = {
        "client_key": client_key,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    r = requests.post(TIKTOK_TOKEN_URL, data=data, timeout=30)
    r.raise_for_status()
    token = r.json()
    # add expires_at
    if "expires_in" in token and "expires_at" not in token:
        token["expires_at"] = int(time.time()) + int(token["expires_in"])
    return token

def refresh_access_token(client_key: str, client_secret: str, refresh_token: str) -> Dict[str, Any]:
    data = {
        "client_key": client_key,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    r = requests.post(TIKTOK_TOKEN_URL, data=data, timeout=30)
    r.raise_for_status()
    token = r.json()
    if "expires_in" in token and "expires_at" not in token:
        token["expires_at"] = int(time.time()) + int(token["expires_in"])
    return token

def ensure_fresh_token(client_key: str, client_secret: str, token: Dict[str, Any], skew: int = 300) -> Dict[str, Any]:
    expires_at = token.get("expires_at")
    if not isinstance(expires_at, (int, float)):
        return token
    if time.time() < float(expires_at) - skew:
        return token
    rt = token.get("refresh_token")
    if not rt:
        return token
    new_token = refresh_access_token(client_key, client_secret, rt)
    if not new_token.get("refresh_token"):
        new_token["refresh_token"] = rt
    return new_token

def creator_info(access_token: str) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.post(TIKTOK_CREATOR_INFO_URL, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def direct_post(access_token: str, video_url: str, caption: str, privacy_level: str = "PUBLIC_TO_EVERYONE") -> Dict[str, Any]:
    title = (caption or "").strip() or "WildFacts"
    title = title[:2000]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    body = {
        "post_info": {
            "title": title,
            "privacy_level": privacy_level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "video_url": video_url,
        },
    }
    r = requests.post(TIKTOK_DIRECT_POST_URL, headers=headers, data=json.dumps(body), timeout=60)
    data = r.json()
    err = (data.get("error") or {})
    code = err.get("code")
    if code and code != "ok":
        raise RuntimeError(f"{code}: {err.get('message','')} (log_id={err.get('log_id') or err.get('logid')})")
    return data

def gen_state() -> str:
    return secrets.token_urlsafe(24)
