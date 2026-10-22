"""Client addressing and response policy shared by login and API throttles."""
import ipaddress
from django.conf import settings
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


def client_ip(request):
    remote = request.META.get('REMOTE_ADDR', '')
    try:
        address = ipaddress.ip_address(remote)
        trusted = [ipaddress.ip_network(value) for value in settings.TRUSTED_PROXY_CIDRS]
        if not any(address in network for network in trusted):
            return str(address)
        chain = [ipaddress.ip_address(value.strip()) for value in request.META.get('HTTP_X_FORWARDED_FOR', '').split(',') if value.strip()]
        for address in reversed(chain):
            if not any(address in network for network in trusted):
                return str(address)
    except ValueError:
        pass
    return remote or 'unknown'


class TrustedAnonThrottle(AnonRateThrottle):
    def get_ident(self, request):
        return client_ip(request)


class TrustedUserThrottle(UserRateThrottle):
    def get_ident(self, request):
        return client_ip(request)


class PrivateResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(('/api/', '/admin/')):
            response['Cache-Control'] = 'private, no-store'
        return response
