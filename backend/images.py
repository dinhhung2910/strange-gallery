"""Image listing, mobile samples, thumbnails and sprite sheets."""

import hashlib
import io
import math
import threading

from PIL import Image, ImageOps

from .config import (
    DATA_DIR, SPRITE_DIR, IMAGE_EXTENSIONS, ENCRYPTED_EXTENSION, SAMPLE_PREFIX,
    THUMBNAIL_SIZE, THUMBNAIL_QUALITY, MOBILE_SAMPLE_SIZE, MOBILE_QUALITY,
    PAGE_SIZE, SPRITE_COLS,
)
from .crypto import decrypt_image_data, encrypt_data

# Cache
image_cache = {}
sprite_cache = {}
cache_lock = threading.Lock()


def get_file_hash(file_path):
    """Get MD5 hash of file"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def sample_path_for(filename):
    """Path of the mobile sample for an encrypted image file name."""
    return DATA_DIR / f"{SAMPLE_PREFIX}{filename}"


def sprite_path_for(page):
    """Path of the encrypted sprite sheet for a page."""
    return SPRITE_DIR / f"sprite_page{page}.jpg.gpg"


def to_rgb(img):
    """Flatten transparency onto white and convert to RGB."""
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
        return background
    if img.mode != 'RGB':
        return img.convert('RGB')
    return img


def create_mobile_sample(encrypted_path, passphrase):
    """Create mobile-optimized sample from encrypted image"""
    try:
        sample_path = sample_path_for(encrypted_path.name)
        if sample_path.exists():
            return True

        image_data = decrypt_image_data(encrypted_path, passphrase)
        if not image_data:
            return False

        with Image.open(io.BytesIO(image_data)) as img:
            img = to_rgb(img)
            img.thumbnail(MOBILE_SAMPLE_SIZE, Image.Resampling.LANCZOS)

            sample_io = io.BytesIO()
            img.save(sample_io, 'JPEG', quality=MOBILE_QUALITY, optimize=True)
            sample_data = sample_io.getvalue()

        encrypted_sample = encrypt_data(sample_data, passphrase)
        if encrypted_sample:
            sample_path.write_bytes(encrypted_sample)
            print(f"Created mobile sample: {sample_path.name}")
            return True

        return False

    except Exception as e:
        print(f"Error creating mobile sample for {encrypted_path}: {e}")
        return False


def generate_thumbnail_from_encrypted(encrypted_path, passphrase):
    """Generate thumbnail from encrypted image"""
    try:
        image_data = decrypt_image_data(encrypted_path, passphrase)
        if not image_data:
            return None

        with Image.open(io.BytesIO(image_data)) as img:
            img = ImageOps.fit(to_rgb(img), THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

            thumbnail_io = io.BytesIO()
            img.save(thumbnail_io, 'JPEG', quality=THUMBNAIL_QUALITY, optimize=True)
            return thumbnail_io.getvalue()

    except Exception as e:
        print(f"Error generating thumbnail for {encrypted_path}: {e}")
        return None


def get_encrypted_image_files():
    """Get all encrypted image files (excluding generated samples)"""
    encrypted_files = []

    for file_path in DATA_DIR.iterdir():
        if file_path.is_file() and file_path.suffix.lower() == ENCRYPTED_EXTENSION:
            if file_path.name.startswith(SAMPLE_PREFIX):
                continue
            # e.g. photo.jpg.gpg -> photo.jpg must be an image
            if file_path.with_suffix('').suffix.lower() in IMAGE_EXTENSIONS:
                encrypted_files.append(file_path.name)

    return sorted(encrypted_files)


def paginate(items, page, page_size=PAGE_SIZE):
    """Slice a sorted list of items into the requested page.

    Returns (page_items, page, total_pages, total_count) with page clamped
    to a valid [1, total_pages] range (total_pages is at least 1).
    """
    total_count = len(items)
    total_pages = max(1, math.ceil(total_count / page_size))

    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    page = max(1, min(page, total_pages))

    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], page, total_pages, total_count


def get_page_files(page_param):
    """Get the page-clamped list of encrypted files for a given page param."""
    return paginate(get_encrypted_image_files(), page_param)


def update_image_cache():
    """Update image cache"""
    new_cache = {}

    for file_name in get_encrypted_image_files():
        file_path = DATA_DIR / file_name
        try:
            stat = file_path.stat()
            new_cache[file_name] = {
                'size': stat.st_size,
                'mtime': stat.st_mtime,
                'hash': get_file_hash(file_path),
                'base_name': file_path.stem
            }
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    with cache_lock:
        image_cache.update(new_cache)

    return list(new_cache.keys())


def generate_mobile_samples_async(encrypted_files, passphrase):
    """Generate mobile samples in background"""
    for filename in encrypted_files:
        if not sample_path_for(filename).exists():
            print(f"Generating mobile sample for {filename}...")
            create_mobile_sample(DATA_DIR / filename, passphrase)


def generate_sprite_image(encrypted_files, passphrase):
    """Generate a sprite image for a (page-scoped) list of encrypted files.

    Sprite sheets are generated per-page, so the list passed in is expected
    to already be sliced to a single page's worth of images (<= PAGE_SIZE).
    Thumbnails are laid out in a single-row-per-SPRITE_COLS grid.
    """
    if not encrypted_files:
        return None, {}

    thumbnails = []
    sprite_map = {}

    for i, filename in enumerate(encrypted_files):
        # Use sample if available
        sample_path = sample_path_for(filename)
        file_path = sample_path if sample_path.exists() else DATA_DIR / filename

        thumbnail_data = generate_thumbnail_from_encrypted(file_path, passphrase)
        if thumbnail_data:
            thumbnails.append(Image.open(io.BytesIO(thumbnail_data)))
            row = i // SPRITE_COLS
            col = i % SPRITE_COLS
            sprite_map[filename] = {
                'index': i,
                'x': col * THUMBNAIL_SIZE[0],
                'y': row * THUMBNAIL_SIZE[1]
            }

    if not thumbnails:
        return None, {}

    rows = (len(thumbnails) + SPRITE_COLS - 1) // SPRITE_COLS
    sprite_width = min(len(thumbnails), SPRITE_COLS) * THUMBNAIL_SIZE[0]
    sprite_height = rows * THUMBNAIL_SIZE[1]
    sprite = Image.new('RGB', (sprite_width, sprite_height), (255, 255, 255))

    for i, thumb in enumerate(thumbnails):
        row = i // SPRITE_COLS
        col = i % SPRITE_COLS
        sprite.paste(thumb, (col * THUMBNAIL_SIZE[0], row * THUMBNAIL_SIZE[1]))

    sprite_io = io.BytesIO()
    sprite.save(sprite_io, 'JPEG', quality=THUMBNAIL_QUALITY, optimize=True)
    return sprite_io.getvalue(), sprite_map


def save_encrypted_sprite(sprite_data, passphrase, page):
    """Encrypt and store a page's sprite sheet."""
    encrypted_sprite = encrypt_data(sprite_data, passphrase)
    if encrypted_sprite:
        sprite_path_for(page).write_bytes(encrypted_sprite)


def regenerate_sprite_async(page_files, passphrase, page):
    """Regenerate a single page's sprite in the background"""
    try:
        sprite_data, _ = generate_sprite_image(page_files, passphrase)
        if sprite_data:
            save_encrypted_sprite(sprite_data, passphrase, page)
    except Exception as e:
        print(f"Error regenerating sprite for page {page}: {e}")
