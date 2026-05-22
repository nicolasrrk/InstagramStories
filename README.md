# Instagram Story Bot

Publica una historia de Instagram automaticamente cada dia usando fotos de Google Drive.
**100% gratuito** — sin APIs de pago, sin servicios externos de hosting.

## Como funciona

```
Google Drive (fotos)
        ↓
GitHub Actions (cron diario)
        ↓  descarga foto
        ↓  sube a GitHub Releases (hosting gratuito, URL publica)
        ↓  caption desde nombre del archivo
        ↓
Instagram Graph API → Historia publicada
        ↓
posted_photos.json actualizado en el repo
```

## Costo total: $0

| Servicio | Plan | Costo |
|---|---|---|
| Instagram Graph API | Gratis (oficial Meta) | $0 |
| Google Drive API | Gratis | $0 |
| GitHub Actions | 2000 min/mes gratis | $0 |
| GitHub Releases (hosting) | Gratis (incluido) | $0 |

---

## Setup (una sola vez)

### 1. Tu cuenta de Instagram debe ser Business o Creator

- Instagram → Configuracion → Cuenta → Cambiar tipo de cuenta → Cuenta profesional
- Conectala a una Pagina de Facebook (requerido por la API de Meta)

### 2. Crear una Facebook App

1. Ir a [developers.facebook.com](https://developers.facebook.com) → Mis apps → Crear app
2. Tipo: **Business** (o "Empresa")
3. Agregar producto: **Instagram Graph API**
4. En "Configuracion basica" anotar el **App ID** y el **App Secret**

En "Roles" de la app, agregarte como **Tester** con tu cuenta de Instagram.
Asi usas la API sin necesidad de que Meta apruebe la app (es solo para uso propio).

**Permisos que necesita la app:**
- `instagram_basic`
- `instagram_content_publish`

### 3. Obtener el Access Token

Ejecuta esto una sola vez en tu maquina:

```bash
pip install requests
python scripts/setup_token.py
```

El script te guia para obtener el token largo (dura 60 dias y el bot lo renueva automaticamente).

### 4. Google Drive — carpeta de fotos

1. Crea una carpeta en Drive y sube tus fotos de productos (JPG/PNG)
   - Tamano ideal para stories: **1080 x 1920 px** (relacion 9:16)
   - Nombralas descriptivamente: `remera_azul_talle_m.jpg`, `zapatilla_nike_blanca.jpg`
2. El bot las publica en **orden alfabetico**, ciclando cuando llega al final
3. El `GOOGLE_DRIVE_FOLDER_ID` es el final de la URL de la carpeta:
   `https://drive.google.com/drive/folders/`**`ESTE_ES_EL_ID`**

**Crear Service Account (autenticacion servidor a servidor):**
1. [console.cloud.google.com](https://console.cloud.google.com) → nuevo proyecto
2. Habilitar **Google Drive API**
3. Credenciales → Crear credenciales → **Cuenta de servicio**
4. Descargar el JSON
5. Compartir tu carpeta de Drive con el email de la cuenta de servicio (solo lectura)

### 5. Repositorio en GitHub (debe ser publico)

> La URL de GitHub Releases es publica. Si el repo es privado, Instagram no puede
> acceder a la imagen. Para repos privados ver la seccion de alternativas al final.

1. Crea un repo publico y sube estos archivos
2. Ve a **Settings → Secrets and variables → Actions → New repository secret**

| Secret | De donde sacarlo |
|---|---|
| `INSTAGRAM_ACCESS_TOKEN` | Del paso 3 (setup_token.py) |
| `INSTAGRAM_USER_ID` | Del paso 3 (setup_token.py) |
| `GOOGLE_DRIVE_FOLDER_ID` | URL de la carpeta de Drive |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Contenido completo del JSON descargado |

`GITHUB_TOKEN` y `GITHUB_REPOSITORY` son **automaticos** — GitHub los inyecta solo.

### 6. Ajustar el horario

En `.github/workflows/daily_post.yml`:

```yaml
- cron: "0 14 * * *"   # 14:00 UTC = 11:00 AM Argentina
```

Convertidor de zonas: [crontab.guru](https://crontab.guru) | [worldtimeserver.com](https://www.worldtimeserver.com)

### 7. Primer test

GitHub → Actions → "Daily Instagram Story" → **Run workflow**

Si aparece la historia en Instagram, todo funciona.

---

## Personalizar los captions

Sin IA, los captions se generan desde el nombre del archivo usando plantillas.
Para cambiarlos, edita la lista `CAPTIONS` en `scripts/post_story.py`:

```python
CAPTIONS = [
    "Stock disponible! Consulta por {product} hoy mismo.",
    "{product} en stock! Escribinos para mas info.",
    # Agrega los tuyos aca...
]
```

`{product}` se reemplaza con el nombre del archivo sin extension y con formato titulo.

---

## Preguntas frecuentes

**¿Me pueden banear?**
No. El bot usa la **API oficial de Meta** (Instagram Graph API), la misma que usan
Buffer, Later, Hootsuite. El limite es 25 publicaciones/24hs; con 1 diaria estas
muy por debajo. Ademas la API refresca el token diariamente.

**¿Que pasa si el token expira?**
El script lo refresca en cada ejecucion. El token dura 60 dias y cada refresh
lo resetea al maximo, asi que nunca expira mientras el bot corra diariamente.

**¿Como cambio las fotos?**
Solo agrega, renombra o elimina archivos en la carpeta de Drive.
El orden de publicacion es alfabetico. El `posted_photos.json` guarda el historial.

**¿Puedo agregar texto a la imagen?**
Si, instalando `Pillow` y componiendo la imagen antes de subirla al Release.
La API de Stories no acepta texto via parametros, hay que quemarlo en la foto.

---

## Alternativa si el repo es privado

Si necesitas el repo privado, reemplaza `upload_image_to_release` en el script
por cualquiera de estas opciones gratuitas sin cuenta:

```python
# Opcion A: 0x0.st (anonimo, sin cuenta)
def upload_public(image_bytes: bytes) -> str:
    r = requests.post(
        "https://0x0.st",
        files={"file": ("photo.jpg", image_bytes, "image/jpeg")},
        timeout=30,
    )
    r.raise_for_status()
    return r.text.strip()

# Opcion B: litterbox.catbox.moe (anonimo, expira en 24hs — suficiente)
def upload_public(image_bytes: bytes) -> str:
    r = requests.post(
        "https://litterbox.catbox.moe/resources/internals/api.php",
        data={"reqtype": "fileupload", "time": "24h"},
        files={"fileToUpload": ("photo.jpg", image_bytes, "image/jpeg")},
        timeout=30,
    )
    r.raise_for_status()
    return r.text.strip()
```

---

## Estructura de archivos

```
.
├── .github/
│   └── workflows/
│       └── daily_post.yml      # Cron de GitHub Actions
├── scripts/
│   ├── post_story.py           # Script principal
│   └── setup_token.py          # Helper one-time para el token de Instagram
├── posted_photos.json          # Historial (se commitea automaticamente)
├── requirements.txt
└── README.md
```
# InstagramStories
