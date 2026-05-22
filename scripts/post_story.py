#!/usr/bin/env python3
"""
Instagram Story Automation
- Google Drive   → fuente de fotos de stock
- GitHub Releases → hosting gratuito (GITHUB_TOKEN automatico)
- Instagram Graph API → publicacion oficial (sin riesgo de ban)
"""

import os
import json
import io
import time
import datetime
import random
import requests
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


# ── Config ─────────────────────────────────────────────────────────────────────
ACCESS_TOKEN    = os.environ["INSTAGRAM_ACCESS_TOKEN"]
IG_USER_ID      = os.environ["INSTAGRAM_USER_ID"]
DRIVE_FOLDER_ID = os.environ["GOOGLE_DRIVE_FOLDER_ID"]
SA_JSON         = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
GITHUB_TOKEN    = os.environ["GITHUB_TOKEN"]
GITHUB_REPO     = os.environ["GITHUB_REPOSITORY"]   # owner/repo (Actions lo pone solo)

TRACKING_FILE = Path("posted_photos.json")
IG_API_BASE   = "https://graph.facebook.com/v21.0"
GH_API_BASE   = "https://api.github.com"
RELEASE_TAG   = "photo-cache"   # Release permanente para hospedar imagenes

# Captions sin IA: se elige uno al azar segun el nombre del archivo
CAPTIONS = [
    "Stock disponible! Consulta por {product} hoy mismo.",
    "{product} en stock! Escribinos para mas informacion.",
    "Nuevo disponible: {product}. No te lo pierdas!",
    "Tenes {product} esperandote! Consulta precio y unidades.",
    "{product} disponible! Mandanos un mensaje y te asesoramos.",
]


# ── Google Drive ───────────────────────────────────────────────────────────────
def get_drive_service():
    creds = service_account.Credentials.from_service_account_info(
        json.loads(SA_JSON),
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_photos(service) -> list[dict]:
    query = (
        f"'{DRIVE_FOLDER_ID}' in parents "
        "and mimeType contains 'image/' "
        "and trashed=false"
    )
    result = (
        service.files()
        .list(q=query, fields="files(id,name,mimeType)", orderBy="name")
        .execute()
    )
    return result.get("files", [])


def download_photo(service, file_id: str) -> bytes:
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


# ── GitHub Releases (hosting gratuito) ────────────────────────────────────────
def gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_or_create_release() -> tuple[int, str]:
    """Devuelve (release_id, upload_url_base) del release 'photo-cache'."""
    r = requests.get(
        f"{GH_API_BASE}/repos/{GITHUB_REPO}/releases/tags/{RELEASE_TAG}",
        headers=gh_headers(),
        timeout=15,
    )
    if r.ok:
        data = r.json()
        return data["id"], data["upload_url"].split("{")[0]

    # No existe aun: crearlo
    r = requests.post(
        f"{GH_API_BASE}/repos/{GITHUB_REPO}/releases",
        headers=gh_headers(),
        json={
            "tag_name": RELEASE_TAG,
            "name": "Photo Cache",
            "body": "Imagenes temporales usadas por el bot de Instagram. No borrar.",
            "prerelease": True,
        },
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    return data["id"], data["upload_url"].split("{")[0]


def upload_image_to_release(image_bytes: bytes, filename: str) -> str:
    """Sube la imagen al release y devuelve la URL publica de descarga."""
    release_id, upload_url_base = get_or_create_release()

    # Borrar asset anterior con el mismo nombre (evitar duplicados)
    assets_r = requests.get(
        f"{GH_API_BASE}/repos/{GITHUB_REPO}/releases/{release_id}/assets",
        headers=gh_headers(),
        timeout=15,
    )
    if assets_r.ok:
        for asset in assets_r.json():
            if asset["name"] == filename:
                requests.delete(
                    f"{GH_API_BASE}/repos/{GITHUB_REPO}/releases/assets/{asset['id']}",
                    headers=gh_headers(),
                    timeout=15,
                )

    # Subir nuevo asset
    upload_headers = {
        **gh_headers(),
        "Content-Type": "image/jpeg",
    }
    r = requests.post(
        f"{upload_url_base}?name={filename}",
        headers=upload_headers,
        data=image_bytes,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["browser_download_url"]


# ── Caption sin IA ─────────────────────────────────────────────────────────────
def make_caption(photo_name: str) -> str:
    product = Path(photo_name).stem.replace("_", " ").replace("-", " ").title()
    return random.choice(CAPTIONS).format(product=product)


# ── Instagram Graph API ────────────────────────────────────────────────────────
def refresh_token() -> str:
    """Extiende el token de 60 dias. Devuelve el nuevo (o el mismo si falla)."""
    r = requests.get(
        "https://graph.instagram.com/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": ACCESS_TOKEN},
        timeout=15,
    )
    if r.ok:
        new = r.json().get("access_token", ACCESS_TOKEN)
        expires = r.json().get("expires_in", "?")
        print(f"  Token OK (expira en {int(expires)//86400} dias)")
        return new
    print(f"  Refresh fallo ({r.status_code}), usando token actual")
    return ACCESS_TOKEN


def post_story(image_url: str, token: str) -> str:
    """Crea y publica una historia. Devuelve el media ID."""
    # 1. Crear container
    r = requests.post(
        f"{IG_API_BASE}/{IG_USER_ID}/media",
        data={"image_url": image_url, "media_type": "STORIES", "access_token": token},
        timeout=30,
    )
    r.raise_for_status()
    container_id = r.json()["id"]
    print(f"  Container: {container_id}")

    # Instagram recomienda esperar antes de publicar
    time.sleep(5)

    # 2. Publicar
    r2 = requests.post(
        f"{IG_API_BASE}/{IG_USER_ID}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=30,
    )
    r2.raise_for_status()
    media_id = r2.json()["id"]
    print(f"  Media ID: {media_id}")
    return media_id


# ── Tracking ───────────────────────────────────────────────────────────────────
def load_tracking() -> dict:
    if TRACKING_FILE.exists():
        return json.loads(TRACKING_FILE.read_text(encoding="utf-8"))
    return {"last_index": -1, "history": []}


def save_tracking(data: dict):
    TRACKING_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print("=== Instagram Story Bot ===")
    print(f"Hora UTC: {datetime.datetime.utcnow().isoformat()}")

    print("\n[1/5] Refrescando token de Instagram...")
    token = refresh_token()

    print("\n[2/5] Listando fotos en Google Drive...")
    drive = get_drive_service()
    photos = list_photos(drive)
    if not photos:
        raise RuntimeError("No se encontraron fotos en la carpeta de Drive.")
    print(f"  {len(photos)} fotos disponibles")

    tracking = load_tracking()
    idx = (tracking["last_index"] + 1) % len(photos)
    photo = photos[idx]
    print(f"  Seleccionada: {photo['name']} ({idx + 1}/{len(photos)})")

    print("\n[3/5] Descargando foto y subiendo a GitHub Releases...")
    image_bytes = download_photo(drive, photo["id"])
    print(f"  Descargados: {len(image_bytes):,} bytes")

    safe_name = Path(photo["name"]).stem[:40] + ".jpg"
    image_url = upload_image_to_release(image_bytes, safe_name)
    print(f"  URL publica: {image_url}")

    caption = make_caption(photo["name"])
    print(f"  Caption: {caption}")

    print("\n[4/5] Publicando historia en Instagram...")
    media_id = post_story(image_url, token)

    print("\n[5/5] Guardando historial...")
    tracking["last_index"] = idx
    tracking["history"].append(
        {
            "file_name": photo["name"],
            "file_id": photo["id"],
            "media_id": media_id,
            "caption": caption,
            "posted_at": datetime.datetime.utcnow().isoformat() + "Z",
        }
    )
    save_tracking(tracking)

    print("\nHistoria publicada exitosamente!")


if __name__ == "__main__":
    main()
