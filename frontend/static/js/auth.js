document.getElementById('authForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    const passphrase = document.getElementById('passphrase').value.trim();
    const submitBtn = document.getElementById('submitBtn');
    const loading = document.getElementById('loading');
    const errorMessage = document.getElementById('errorMessage');
    const successMessage = document.getElementById('successMessage');

    if (!passphrase) {
        showError('Please enter a decryption key');
        return;
    }

    submitBtn.disabled = true;
    loading.style.display = 'block';
    errorMessage.style.display = 'none';
    successMessage.style.display = 'none';

    try {
        const formData = new FormData();
        formData.append('passphrase', passphrase);

        const response = await fetch('/authenticate', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            successMessage.textContent = 'Authentication successful! Loading gallery...';
            successMessage.style.display = 'block';

            setTimeout(() => {
                window.location.href = '/';
            }, 1000);
        } else {
            showError(result.error || 'Authentication failed');
        }
    } catch (error) {
        showError('Network error. Please try again.');
    } finally {
        submitBtn.disabled = false;
        loading.style.display = 'none';
    }
});

function showError(message) {
    const errorMessage = document.getElementById('errorMessage');
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
}

document.getElementById('passphrase').focus();

document.getElementById('passphrase').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        document.getElementById('authForm').dispatchEvent(new Event('submit'));
    }
});
