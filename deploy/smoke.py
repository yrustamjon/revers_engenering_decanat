"""Exercise the built application, real PostgreSQL/Redis and session cookies."""
import json
import os
import re
from http.cookies import SimpleCookie
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

assert os.getuid() != 0, 'The application must run as a non-root user.'
host = os.environ['RENDER_EXTERNAL_HOSTNAME']
base = 'http://127.0.0.1:' + os.environ['PORT']
opener = build_opener(ProxyHandler({}))  # Only the service in this container.
cookies = {}


def call(path, data=None):
    headers = {'Host':host, 'X-Forwarded-Proto':'https', 'Origin':'https://' + host}
    if cookies:
        headers['Cookie'] = '; '.join(key+'='+value for key,value in cookies.items())
    if data is not None:
        headers['Content-Type'] = 'application/json'
        headers['X-CSRFToken'] = cookies.get('csrftoken', '')
    request = Request(base+path, headers=headers, data=None if data is None else json.dumps(data).encode())
    try:
        response = opener.open(request, timeout=5)
    except HTTPError as error:
        response = error
    for header in response.headers.get_all('Set-Cookie', []):
        parsed = SimpleCookie()
        parsed.load(header)
        cookies.update({key:value.value for key,value in parsed.items()})
    return response.code, response.read(), response.headers


code, html, _ = call('/')
assert code == 200 and b'<div id="root">' in html
asset = re.search(rb'src="(/assets/[^\"]+)"', html).group(1).decode()
assert call(asset)[0] == 200
assert call('/healthz')[0] == 200
assert call('/media/private.pdf')[0] == 404
assert call('/api/auth/session/')[0] == 401
assert call('/api/auth/login/', {'username':os.environ['UNIFLOW_ADMIN_USERNAME'],'password':os.environ['UNIFLOW_ADMIN_PASSWORD']})[0] == 200
code, body, headers = call('/api/workspace/')
assert code == 200 and json.loads(body)['user']['role'] == 'administrator'
assert headers['Cache-Control'] == 'private, no-store'
assert call('/api/auth/demo/', {'role':'administrator'})[0] == 404
assert call('/api/auth/logout/', {})[0] == 204
assert call('/api/workspace/')[0] == 403
print('Non-root runtime, React/assets, readiness, private media, real login/CSRF/logout: OK')
