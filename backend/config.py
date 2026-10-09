"""Application settings. All paths are resolved relative to the project root."""

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / 'frontend'
TEMPLATE_DIR = FRONTEND_DIR / 'templates'
STATIC_DIR = FRONTEND_DIR / 'static'


def _resolve(path_str):
    """Resolve a relative path against the project root."""
    path = Path(path_str)
    return path if path.is_absolute() else BASE_DIR / path


# Encrypted images (and their generated samples) live in gallery/ by default
DATA_DIR = _resolve(os.environ.get('DATA_PATH', 'gallery'))
SPRITE_DIR = DATA_DIR / '.sprites'

# Flask
SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
PERMANENT_SESSION_LIFETIME = 3600

# Zip upload limits
MB = 1024 * 1024
MAX_CONTENT_LENGTH = int(os.environ.get('UPLOAD_MAX_MB', 500)) * MB  # request body size
UPLOAD_MAX_FILES = 2000
UPLOAD_MAX_FILE_SIZE = 100 * MB  # per extracted file
UPLOAD_MAX_TOTAL_SIZE = 4 * MAX_CONTENT_LENGTH  # all extracted files (zip bomb guard)

# Image settings
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
ENCRYPTED_EXTENSION = '.gpg'
SAMPLE_PREFIX = 'sample_'
THUMBNAIL_SIZE = (300, 300)
THUMBNAIL_QUALITY = 85
MOBILE_SAMPLE_SIZE = (1200, 1200)  # Mobile-optimized size
MOBILE_QUALITY = 85

# Pagination settings
PAGE_SIZE = 60
SPRITE_COLS = 60  # one row per page's sprite sheet (PAGE_SIZE images per row)


def ensure_dirs():
    """Create data directories if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SPRITE_DIR.mkdir(parents=True, exist_ok=True)
