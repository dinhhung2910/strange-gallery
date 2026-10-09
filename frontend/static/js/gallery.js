// Sprite thumbnails are generated per-page: SPRITE_COLS images per row.
const SPRITE_COLS = Number(document.body.dataset.pageSize);
const CURRENT_PAGE = Number(document.body.dataset.page);

let currentImages = [];
let currentImageIndex = 0;

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.image-tile').forEach(tile => {
        tile.classList.add('loading');
    });

    const imageElements = document.querySelectorAll('.sprite-thumb');
    currentImages = Array.from(imageElements).map(el => el.dataset.filename);

    loadSprite();
    checkSessionStatus();
});

function loadSprite() {
    fetch(`/sprite?page=${CURRENT_PAGE}`).then(r => r.blob()).then(spriteBlob => {
        const spriteUrl = URL.createObjectURL(spriteBlob);

        document.querySelectorAll('.sprite-thumb').forEach((thumb, index) => {
            const row = Math.floor(index / SPRITE_COLS);
            const col = index % SPRITE_COLS;
            const x = col * 300;
            const y = row * 300;

            thumb.style.backgroundImage = `url(${spriteUrl})`;
            thumb.style.backgroundPosition = `-${x}px -${y}px`;
            thumb.parentElement.classList.remove('loading');
        });
    }).catch(console.error);
}

function checkSessionStatus() {
    fetch('/api/thumbnail-status')
        .then(response => response.json())
        .then(data => {
            if (!data.authenticated) {
                window.location.href = '/';
            }
        })
        .catch(error => {
            console.log('Session check failed:', error);
        });
}

setInterval(checkSessionStatus, 5 * 60 * 1000);

function openModal(filename) {
    const modal = document.getElementById('imageModal');

    currentImageIndex = currentImages.indexOf(filename);
    if (currentImageIndex === -1) {
        currentImageIndex = 0;
    }

    modal.style.display = 'block';
    loadModalImage(filename);
    updateModalNavigation();

    document.body.style.overflow = 'hidden';
}

function loadModalImage(filename) {
    const modalImg = document.getElementById('modalImage');
    const modalFilename = document.getElementById('modalFilename');
    const spinner = document.getElementById('modalSpinner');
    const downloadBtn = document.getElementById('downloadBtn');

    const displayName = filename.replace('.gpg', '');
    modalFilename.textContent = displayName;

    // Set download button URL to original image
    downloadBtn.href = '/image-original/' + filename;

    spinner.style.display = 'block';
    modalImg.style.display = 'none';

    modalImg.onload = function() {
        spinner.style.display = 'none';
        modalImg.style.display = 'block';
    };

    modalImg.onerror = function() {
        spinner.style.display = 'none';
        modalImg.style.display = 'block';
        modalImg.alt = 'Failed to decrypt image';
        modalImg.style.display = 'none';
        spinner.innerHTML = '<div style="color: white; text-align: center;">❌<br>Decryption Failed</div>';
        spinner.style.display = 'block';
    };

    // Load mobile-optimized sample (server falls back to original if not generated yet)
    modalImg.src = '/image/' + filename;
    modalImg.alt = displayName;
}

function updateModalNavigation() {
    const counter = document.getElementById('modalCounter');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');

    counter.textContent = `${currentImageIndex + 1} / ${currentImages.length}`;

    // Navigation wraps within the current page only; use the page
    // controls above/below the gallery to move between pages.
    prevBtn.disabled = currentImageIndex === 0;
    nextBtn.disabled = currentImageIndex === currentImages.length - 1;
}

function navigateImage(direction) {
    const newIndex = currentImageIndex + direction;

    if (newIndex >= 0 && newIndex < currentImages.length) {
        currentImageIndex = newIndex;
        loadModalImage(currentImages[currentImageIndex]);
        updateModalNavigation();
    }
}

function closeModal() {
    const modal = document.getElementById('imageModal');
    modal.style.display = 'none';
    document.body.style.overflow = 'auto';
}

document.addEventListener('keydown', function(event) {
    const modal = document.getElementById('imageModal');
    if (modal.style.display === 'block') {
        switch(event.key) {
            case 'Escape':
                closeModal();
                break;
            case 'ArrowLeft':
                event.preventDefault();
                navigateImage(-1);
                break;
            case 'ArrowRight':
                event.preventDefault();
                navigateImage(1);
                break;
        }
    }
});

document.getElementById('modalImage').addEventListener('click', function(event) {
    event.stopPropagation();
});

let touchStartX = 0;
let touchStartY = 0;
let touchEndX = 0;
let touchEndY = 0;
let isDragging = false;

const modal = document.getElementById('imageModal');

modal.addEventListener('touchstart', function(event) {
    touchStartX = event.changedTouches[0].screenX;
    touchStartY = event.changedTouches[0].screenY;
    isDragging = true;
}, { passive: true });

modal.addEventListener('touchmove', function(event) {
    if (!isDragging) return;

    touchEndX = event.changedTouches[0].screenX;
    touchEndY = event.changedTouches[0].screenY;

    const deltaX = Math.abs(touchEndX - touchStartX);
    const deltaY = Math.abs(touchEndY - touchStartY);

    if (deltaX > deltaY && deltaX > 20) {
        event.preventDefault();
    }
}, { passive: false });

modal.addEventListener('touchend', function(event) {
    if (!isDragging) return;

    touchEndX = event.changedTouches[0].screenX;
    touchEndY = event.changedTouches[0].screenY;
    isDragging = false;

    handleSwipe();
}, { passive: true });

function handleSwipe() {
    const swipeThreshold = 50;
    const deltaX = touchStartX - touchEndX;
    const deltaY = touchStartY - touchEndY;

    if (Math.abs(deltaX) > Math.abs(deltaY)) {
        if (Math.abs(deltaX) > swipeThreshold) {
            if (deltaX > 0) {
                navigateImage(1);
            } else {
                navigateImage(-1);
            }
        }
    } else {
        if (Math.abs(deltaY) > swipeThreshold) {
            closeModal();
        }
    }
}

modal.addEventListener('wheel', function(event) {
    if (modal.style.display === 'block') {
        event.preventDefault();

        if (event.deltaY > 0) {
            navigateImage(1);
        } else {
            navigateImage(-1);
        }
    }
}, { passive: false });

let warningShown = false;
setTimeout(() => {
    if (!warningShown) {
        warningShown = true;
        if (confirm('Your session will expire in 5 minutes. Click OK to stay logged in.')) {
            fetch('/api/thumbnail-status');
        }
    }
}, 55 * 60 * 1000);

// ZIP upload: extracts images into the gallery, then reloads the page
document.getElementById('uploadInput').addEventListener('change', async function() {
    const file = this.files[0];
    if (!file) return;

    const uploadBtn = document.getElementById('uploadBtn');
    const status = document.getElementById('uploadStatus');
    const showStatus = (type, message) => {
        status.className = `upload-status ${type}`;
        status.textContent = message;
    };

    uploadBtn.classList.add('busy');
    showStatus('success', `Uploading ${file.name}... (images are encrypted on the server, this may take a while)`);

    try {
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetch('/upload', { method: 'POST', body: formData });
        const result = await response.json();

        if (result.success) {
            const skipped = result.skipped.length ? `, ${result.skipped.length} skipped` : '';
            showStatus('success', `Added ${result.added.length} image(s)${skipped}.`);
            if (result.added.length) setTimeout(() => window.location.reload(), 1500);
        } else {
            showStatus('error', result.error || 'Upload failed');
        }
    } catch (error) {
        showStatus('error', 'Network error. Please try again.');
    } finally {
        uploadBtn.classList.remove('busy');
        this.value = '';
    }
});
