"""GPG symmetric encryption helpers."""

import subprocess


def decrypt_image_data(encrypted_file_path, passphrase):
    """Decrypt GPG encrypted image data"""
    try:
        cmd = [
            'gpg', '--quiet', '--batch', '--yes', '--decrypt',
            '--passphrase', passphrase,
            '--passphrase-fd', '0',
            str(encrypted_file_path)
        ]

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process.communicate(input=passphrase.encode())

        if process.returncode != 0:
            print(f"GPG decryption failed: {stderr.decode()}")
            return None

        return stdout

    except Exception as e:
        print(f"Error decrypting {encrypted_file_path}: {e}")
        return None


def encrypt_data(data, passphrase):
    """Encrypt data using GPG"""
    try:
        cmd = [
            'gpg', '--quiet', '--batch', '--yes', '--cipher-algo', 'AES256',
            '--compress-algo', '1', '--s2k-mode', '3', '--s2k-digest-algo', 'SHA512',
            '--s2k-count', '65011712', '--symmetric', '--passphrase', passphrase
        ]

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process.communicate(input=data)

        if process.returncode != 0:
            print(f"GPG encryption failed: {stderr.decode()}")
            return None

        return stdout

    except Exception as e:
        print(f"Error encrypting data: {e}")
        return None
