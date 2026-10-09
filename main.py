#!/usr/bin/env python3
"""
Mobile-Optimized Encrypted Image Gallery Web App
Features:
- Automatic mobile-optimized sample generation
- Download button to view original in new tab
- Improved mobile performance
- Pagination (60 images per page) with page-scoped sprite sheets

Runs a production WSGI server (waitress) by default; pass --dev for the
Flask debug server.
"""

import argparse
import os
import shutil
import sys

from backend.app import app
from backend.config import DATA_DIR, PAGE_SIZE


def main():
    parser = argparse.ArgumentParser(description='Encrypted image gallery')
    parser.add_argument('--dev', action='store_true', help='run the Flask debug server')
    parser.add_argument('--host', default=os.environ.get('HOST', '0.0.0.0'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', 8000)))
    parser.add_argument('--threads', type=int, default=int(os.environ.get('THREADS', 8)))
    args = parser.parse_args()

    if shutil.which('gpg') is None:
        print("ERROR: GPG not found! Please install GPG")
        sys.exit(1)

    if not os.environ.get('SECRET_KEY'):
        print("WARNING: SECRET_KEY not set; using a random key (sessions reset on restart)")

    print("Starting Mobile-Optimized Encrypted Image Gallery...")
    print(f"  - Gallery folder: {DATA_DIR}")
    print(f"  - Pagination: {PAGE_SIZE} images per page, page-scoped sprites")

    if args.dev:
        print(f"\nRunning in development mode on http://localhost:{args.port}")
        app.run(debug=True, host=args.host, port=args.port)
    else:
        from waitress import serve
        print(f"\nRunning in production mode on http://{args.host}:{args.port}")
        serve(app, host=args.host, port=args.port, threads=args.threads)


if __name__ == '__main__':
    main()
