import logging

from ipware import get_client_ip


class WithClientIP(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[{self.extra['ip']}] {msg}", kwargs


def get_client_ip_logger(name, request):
    client_ip, _is_routable = get_client_ip(request)

    return WithClientIP(logging.getLogger(name), {"ip": client_ip})
