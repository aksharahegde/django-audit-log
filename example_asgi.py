"""
Example ASGI application using django-audit-log.

This file demonstrates how to set up an ASGI application with audit logging middleware.
"""

import os
import django
from django.core.asgi import get_asgi_application

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')
django.setup()

# Get the Django ASGI application
django_asgi_app = get_asgi_application()

# Apply audit logging middleware
try:
    from audit_log.asgi import get_asgi_application
    application = get_asgi_application()(django_asgi_app)
except ImportError:
    # Fallback if ASGI support is not available
    print("ASGI support not available. Install with: pip install django-audit-log[asgi]")
    application = django_asgi_app
