#!/usr/bin/env python3
"""
Obtiene el Instagram Access Token usando el Graph API Explorer de Meta.
No requiere configurar redirect URIs ni levantar un servidor local.

Uso:
  pip install requests
  python scripts/setup_token.py
"""

import sys
import webbrowser
import requests

print("=" * 60)
print("  Instagram Access Token — Setup")
print("=" * 60)

# ── Paso 1: Graph API Explorer ─────────────────────────────────────────────────
print("""
PASO 1 — Abri el Graph API Explorer en el navegador:
""")
webbrowser.open("https://developers.facebook.com/tools/explorer/")

input("Presiona Enter cuando se haya abierto el navegador...")

print("""
En el Graph API Explorer:

  1. Arriba a la derecha → desplegable "Meta App" → selecciona TU app
  2. Click en "Generate Access Token"
  3. Tilda estos dos permisos:
       - instagram_basic
       - instagram_content_publish
  4. Click "Generate Access Token" → autorizas con tu cuenta de Facebook
  5. Copia el token que aparece en el campo de texto (empieza con EAA...)
""")

SHORT_TOKEN = input("Pega el token aqui: ").strip()
if not SHORT_TOKEN.startswith("EAA"):
    print("Advertencia: el token no parece valido (deberia empezar con EAA)")

# ── Paso 2: App ID y Secret ────────────────────────────────────────────────────
print("""
PASO 2 — App ID y App Secret
  Encontralos en: tu App → Configuracion basica (Settings → Basic)
""")
APP_ID     = input("App ID: ").strip()
APP_SECRET = input("App Secret: ").strip()

# ── Paso 3: Intercambiar por token largo (60 dias) ─────────────────────────────
print("\nConvirtiendo a token largo (60 dias)...")
r = requests.get(
    "https://graph.facebook.com/v21.0/oauth/access_token",
    params={
        "grant_type":       "fb_exchange_token",
        "client_id":        APP_ID,
        "client_secret":    APP_SECRET,
        "fb_exchange_token": SHORT_TOKEN,
    },
    timeout=15,
)

if not r.ok:
    print(f"\nError al obtener el token largo:\n{r.text}")
    print("\nPosibles causas:")
    print("  - App ID o App Secret incorrecto")
    print("  - El token corto ya expiro (tienen 1 hora de vida, volvelo a generar)")
    sys.exit(1)

data       = r.json()
long_token = data["access_token"]
dias       = data.get("expires_in", 0) // 86400
print(f"Token largo obtenido (expira en ~{dias} dias)")

# ── Paso 4: Obtener Instagram User ID ─────────────────────────────────────────
print("\nBuscando tu Instagram User ID...")
ig_user_id = None
username   = None

# Primero obtenemos las paginas de Facebook del usuario
r = requests.get(
    "https://graph.facebook.com/v21.0/me/accounts",
    params={"access_token": long_token},
    timeout=15,
)

if r.ok:
    pages = r.json().get("data", [])
    if not pages:
        print("  No se encontraron Paginas de Facebook asociadas.")
        print("  Asegurate de que tu cuenta de Instagram este conectada a una Pagina.")
    for page in pages:
        r2 = requests.get(
            f"https://graph.facebook.com/v21.0/{page['id']}/instagram_accounts",
            params={"fields": "id,username", "access_token": long_token},
            timeout=15,
        )
        if r2.ok and r2.json().get("data"):
            account    = r2.json()["data"][0]
            ig_user_id = account["id"]
            username   = account.get("username", "?")
            print(f"  Encontrada: @{username} → ID: {ig_user_id}")
            break
else:
    print(f"  Error buscando paginas: {r.text}")

# ── Resultado final ────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("  Guarda estos valores en GitHub Secrets:")
print("  (repo → Settings → Secrets and variables → Actions)")
print("=" * 60)
print(f"\n  INSTAGRAM_ACCESS_TOKEN  =  {long_token}")
if ig_user_id:
    print(f"  INSTAGRAM_USER_ID       =  {ig_user_id}")
else:
    print("  INSTAGRAM_USER_ID       =  (no se encontro automaticamente)")
    print()
    print("Para obtenerlo manualmente, en el Graph API Explorer ejecuta:")
    print("  GET  me?fields=id,name")
    print("  y busca tu cuenta de Instagram en las paginas vinculadas.")
print()
