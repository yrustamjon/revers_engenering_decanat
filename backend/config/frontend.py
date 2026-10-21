"""Headers for the optional single-service React deployment."""
def static_headers(headers, path, url):
    headers['X-Content-Type-Options'] = 'nosniff'
    headers['X-Frame-Options'] = 'DENY'
    headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if url in ('/', '/index.html'):
        headers['Cache-Control'] = 'no-store'
