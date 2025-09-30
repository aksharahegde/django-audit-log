"""
ASGI support for django-audit-log.

This module provides ASGI middleware classes for Django applications using ASGI.
"""

try:
    from asgiref.sync import sync_to_async
    ASGI_AVAILABLE = True
except ImportError:
    ASGI_AVAILABLE = False

if ASGI_AVAILABLE:
    from .middleware import ASGIUserLoggingMiddleware, ASGIJWTAuthMiddleware
    
    __all__ = ['ASGIUserLoggingMiddleware', 'ASGIJWTAuthMiddleware']
else:
    __all__ = []


def get_asgi_application(django_app):
    """
    Get an ASGI application with audit logging middleware applied.
    
    Usage:
        from audit_log.asgi import get_asgi_application
        
        application = get_asgi_application(your_django_asgi_app)
    """
    if not ASGI_AVAILABLE:
        raise ImportError(
            "ASGI support requires asgiref>=3.2.0. "
            "Install with: pip install django-audit-log[asgi]"
        )
    
    return ASGIUserLoggingMiddleware(django_app)
