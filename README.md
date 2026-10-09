# strange-gallery

Images are stored GPG-encrypted on disk and decrypted on the fly with the
passphrase you enter. Mobile-optimized samples and per-page thumbnail sprites
are generated automatically (also encrypted).

## Requirements
- Python 3.9+
- GnuPG (`gpg` on `PATH`)

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Add images
Encrypt images with a passphrase and put them in `gallery/` (created automatically):
```bash
gpg --symmetric --cipher-algo AES256 -o gallery/photo.jpg.gpg photo.jpg
```
Or, once logged in, click **Upload ZIP** (`POST /upload`, form field `file`). Plain images
are encrypted with your passphrase; `*.gpg` images are stored as-is; other files are skipped.

## Run (production)
```bash
SECRET_KEY=$(openssl rand -hex 32) python main.py
```
Serves with waitress on http://0.0.0.0:8000. Use `python main.py --dev` for the Flask debug server.

## Configuration
| Env var / flag         | Default     | Description                                 |
|------------------------|-------------|---------------------------------------------|
| `DATA_PATH`            | `gallery`   | Image folder                                |
| `SECRET_KEY`           | random      | Session key; set it to keep logins on restart |
| `PORT` / `--port`      | `8000`      | Listen port                                 |
| `HOST` / `--host`      | `0.0.0.0`   | Listen address                              |
| `THREADS` / `--threads`| `8`         | Worker threads                              |
| `UPLOAD_MAX_MB`        | `500`       | Max zip upload size                         |

## Layout
```
main.py      entry point (production server)
backend/     Flask app, GPG crypto, image processing
frontend/    templates/, static/css, static/js
gallery/     encrypted images, samples (sample_*), .sprites/
```
