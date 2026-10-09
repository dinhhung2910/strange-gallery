"""Flask application and HTTP routes."""

import hashlib
import io
import mimetypes
import threading

from flask import Flask, render_template, send_file, abort, request, jsonify, session, redirect

from . import config
from .config import DATA_DIR, ENCRYPTED_EXTENSION, PAGE_SIZE
from .crypto import decrypt_image_data
from .images import (
    cache_lock, sprite_cache, sample_path_for, sprite_path_for,
    get_encrypted_image_files, paginate, get_page_files, update_image_cache,
    generate_mobile_samples_async, generate_sprite_image, save_encrypted_sprite,
    regenerate_sprite_async,
)
from .upload import UploadError, extract_zip_to_gallery

app = Flask(
    __name__,
    template_folder=str(config.TEMPLATE_DIR),
    static_folder=str(config.STATIC_DIR),
)
app.config.update(
    SECRET_KEY=config.SECRET_KEY,
    MAX_CONTENT_LENGTH=config.MAX_CONTENT_LENGTH,
    PERMANENT_SESSION_LIFETIME=config.PERMANENT_SESSION_LIFETIME,
)

config.ensure_dirs()


def is_session_authenticated():
    """Check if user is authenticated"""
    return session.get('decryption_key') is not None


def send_decrypted(file_path, filename):
    """Decrypt an encrypted file and send it as an inline image."""
    if not file_path.exists():
        abort(404)

    image_data = decrypt_image_data(file_path, session['decryption_key'])
    if image_data is None:
        abort(500)

    base_name = filename[:-len(ENCRYPTED_EXTENSION)]
    content_type, _ = mimetypes.guess_type(base_name)

    return send_file(
        io.BytesIO(image_data),
        mimetype=content_type or 'image/jpeg',
        as_attachment=False,
        download_name=base_name
    )


@app.route('/')
def index():
    """Main page"""
    if not is_session_authenticated():
        return render_template('auth.html')

    all_images = sorted(update_image_cache())
    page_images, page, total_pages, total_count = paginate(all_images, request.args.get('page', 1))

    return render_template(
        'gallery.html',
        images=page_images,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        page_size=PAGE_SIZE,
        has_prev=page > 1,
        has_next=page < total_pages,
    )


@app.route('/authenticate', methods=['POST'])
def authenticate():
    """Handle authentication"""
    passphrase = request.form.get('passphrase', '').strip()

    if not passphrase:
        return jsonify({'success': False, 'error': 'Please enter a decryption key'})

    encrypted_files = get_encrypted_image_files()
    if not encrypted_files:
        return jsonify({'success': False, 'error': 'No encrypted images found'})

    if decrypt_image_data(DATA_DIR / encrypted_files[0], passphrase) is None:
        return jsonify({'success': False, 'error': 'Invalid decryption key'})

    session['decryption_key'] = passphrase
    session.permanent = True

    with cache_lock:
        sprite_cache.clear()

    # Start generating mobile samples in background
    threading.Thread(
        target=generate_mobile_samples_async,
        args=(encrypted_files, passphrase),
        daemon=True
    ).start()

    return jsonify({'success': True})


@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    with cache_lock:
        sprite_cache.clear()
    return redirect('/')


@app.route('/upload', methods=['POST'])
def upload_zip():
    """Upload a zip of images (plain or *.gpg) and extract it into the gallery"""
    if not is_session_authenticated():
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    upload = request.files.get('file')
    if not upload or not upload.filename:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
    if not upload.filename.lower().endswith('.zip'):
        return jsonify({'success': False, 'error': 'Only .zip files are accepted'}), 400

    passphrase = session['decryption_key']
    try:
        added, skipped = extract_zip_to_gallery(upload, passphrase)
    except UploadError as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    if added:
        with cache_lock:
            sprite_cache.clear()
        threading.Thread(
            target=generate_mobile_samples_async,
            args=(added, passphrase),
            daemon=True
        ).start()

    return jsonify({'success': True, 'added': added, 'skipped': skipped})


@app.route('/image/<filename>')
def serve_image(filename):
    """Serve mobile-optimized sample image (falls back to the original)"""
    if not is_session_authenticated():
        abort(401)
    if not filename.endswith(ENCRYPTED_EXTENSION):
        abort(404)

    sample_path = sample_path_for(filename)
    file_path = sample_path if sample_path.exists() else DATA_DIR / filename
    return send_decrypted(file_path, filename)


@app.route('/image-original/<filename>')
def serve_original_image(filename):
    """Serve original full-size image"""
    if not is_session_authenticated():
        abort(401)
    if not filename.endswith(ENCRYPTED_EXTENSION):
        abort(404)

    return send_decrypted(DATA_DIR / filename, filename)


@app.route('/sprite')
def serve_sprite():
    """Serve the sprite image for a single page of images (?page=N)"""
    if not is_session_authenticated():
        abort(401)

    passphrase = session['decryption_key']
    page_files, page, _, _ = get_page_files(request.args.get('page', 1))
    sprite_path = sprite_path_for(page)

    if sprite_path.exists():
        threading.Thread(
            target=regenerate_sprite_async, args=(page_files, passphrase, page), daemon=True
        ).start()
        sprite_data = decrypt_image_data(sprite_path, passphrase)
        if sprite_data:
            return send_file(io.BytesIO(sprite_data), mimetype='image/jpeg', as_attachment=False)

    sprite_data, _ = generate_sprite_image(page_files, passphrase)
    if not sprite_data:
        abort(500)

    save_encrypted_sprite(sprite_data, passphrase, page)
    return send_file(io.BytesIO(sprite_data), mimetype='image/jpeg', as_attachment=False)


@app.route('/sprite-map')
def serve_sprite_map():
    """Serve the sprite map for a single page of images (?page=N)"""
    if not is_session_authenticated():
        return jsonify({})

    passphrase = session['decryption_key']
    page_files, page, _, _ = get_page_files(request.args.get('page', 1))

    cache_key = f"sprite:page{page}:{hashlib.md5((passphrase + str(page_files)).encode()).hexdigest()[:8]}"

    with cache_lock:
        if cache_key in sprite_cache:
            sprite_map = sprite_cache[cache_key]['map']
        else:
            sprite_data, sprite_map = generate_sprite_image(page_files, passphrase)
            if not sprite_data:
                return jsonify({})
            sprite_cache[cache_key] = {'data': sprite_data, 'map': sprite_map}

    return jsonify(sprite_map)


@app.route('/api/thumbnail-status')
def thumbnail_status():
    """API endpoint for status"""
    if not is_session_authenticated():
        return jsonify({'authenticated': False})

    images = get_encrypted_image_files()
    return jsonify({
        'authenticated': True,
        'total': len(images),
        'ready': len(images),
        'percentage': 100
    })


@app.errorhandler(401)
def unauthorized_error(error):
    session.clear()
    return redirect('/')


@app.errorhandler(413)
def too_large_error(error):
    limit_mb = app.config['MAX_CONTENT_LENGTH'] // config.MB
    return jsonify({'success': False, 'error': f'Upload too large (max {limit_mb} MB)'}), 413


@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', code=404, title='Not Found',
                           heading='File Not Found'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', code=500, title='Internal Error',
                           heading='Internal Server Error',
                           message='Something went wrong. Please try again later.'), 500
