"""Import images from an uploaded zip archive into the gallery."""

import io
import zipfile
from pathlib import PurePosixPath

from PIL import Image

from .config import (
    DATA_DIR, IMAGE_EXTENSIONS, ENCRYPTED_EXTENSION, SAMPLE_PREFIX,
    UPLOAD_MAX_FILES, UPLOAD_MAX_FILE_SIZE, UPLOAD_MAX_TOTAL_SIZE,
)
from .crypto import encrypt_data


class UploadError(Exception):
    """Raised when the archive as a whole is rejected."""


def _safe_name(member_name):
    """Flatten an archive path to a plain file name (prevents zip-slip)."""
    name = PurePosixPath(member_name.replace('\\', '/')).name
    if not name or name.startswith('.') or name.startswith(SAMPLE_PREFIX):
        return None
    return name


def _classify(name):
    """Return 'encrypted', 'plain' or None for a file name."""
    path = PurePosixPath(name)
    if path.suffix.lower() == ENCRYPTED_EXTENSION:
        return 'encrypted' if path.with_suffix('').suffix.lower() in IMAGE_EXTENSIONS else None
    return 'plain' if path.suffix.lower() in IMAGE_EXTENSIONS else None


def extract_zip_to_gallery(file_storage, passphrase):
    """Extract images from an uploaded zip into the gallery folder.

    - *.<img>.gpg files are stored as-is.
    - Plain images are verified and encrypted with the session passphrase.
    - Everything else, directories, hidden files and existing names are skipped.

    Returns (added, skipped) where added is a list of stored file names and
    skipped is a list of {'name', 'reason'} dicts.
    """
    try:
        archive = zipfile.ZipFile(file_storage.stream)
    except zipfile.BadZipFile:
        raise UploadError('Invalid zip file')

    with archive:
        members = [m for m in archive.infolist() if not m.is_dir()]
        if len(members) > UPLOAD_MAX_FILES:
            raise UploadError(f'Too many files in archive (max {UPLOAD_MAX_FILES})')
        if sum(m.file_size for m in members) > UPLOAD_MAX_TOTAL_SIZE:
            raise UploadError('Archive is too large when extracted')

        added, skipped = [], []
        for member in members:
            name = _safe_name(member.filename)
            if name is None:
                skipped.append({'name': member.filename, 'reason': 'hidden or reserved name'})
                continue
            kind = _classify(name)
            if kind is None:
                skipped.append({'name': member.filename, 'reason': 'not an image'})
                continue
            if member.file_size > UPLOAD_MAX_FILE_SIZE:
                skipped.append({'name': member.filename, 'reason': 'file too large'})
                continue

            target_name = name if kind == 'encrypted' else name + ENCRYPTED_EXTENSION
            target = DATA_DIR / target_name
            if target.exists() or target_name in added:
                skipped.append({'name': member.filename, 'reason': 'already exists'})
                continue

            # Read with a hard cap in case the header lies about the size
            with archive.open(member) as src:
                data = src.read(UPLOAD_MAX_FILE_SIZE + 1)
            if len(data) > UPLOAD_MAX_FILE_SIZE:
                skipped.append({'name': member.filename, 'reason': 'file too large'})
                continue

            if kind == 'plain':
                try:
                    with Image.open(io.BytesIO(data)) as img:
                        img.verify()
                except Exception:
                    skipped.append({'name': member.filename, 'reason': 'invalid image'})
                    continue
                data = encrypt_data(data, passphrase)
                if data is None:
                    skipped.append({'name': member.filename, 'reason': 'encryption failed'})
                    continue

            target.write_bytes(data)
            added.append(target_name)

    return added, skipped
