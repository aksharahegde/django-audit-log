Changelog
=========

Version 1.0.0 (Django 4.0+ Support & ASGI)
--------------------------------------------

* **BREAKING CHANGE**: Dropped support for Django < 4.0
* **BREAKING CHANGE**: Dropped support for Python < 3.8
* Added ASGI support for Django 4.0+ applications
* New ASGI middleware classes: ``ASGIUserLoggingMiddleware`` and ``ASGIJWTAuthMiddleware``
* New ``audit_log.asgi`` module with convenience functions
* Added ``asgiref>=3.2.0`` dependency for ASGI support
* Added comprehensive tests for ASGI functionality
* Updated documentation with ASGI setup instructions
* Added example ASGI application file
* Modernized codebase to use Django 4.0+ features
* Updated URL patterns to use modern Django URL routing
* Removed deprecated compatibility code

Breaking Changes
~~~~~~~~~~~~~~~~
* **Django 4.0+ required**: Minimum Django version is now 4.0
* **Python 3.8+ required**: Minimum Python version is now 3.8
* Removed deprecated ``MIDDLEWARE_CLASSES`` support (use ``MIDDLEWARE``)
* Removed deprecated URL ``patterns()`` function support
* Removed deprecated ``failUnlessEqual`` test methods

New Features
~~~~~~~~~~~~
* ASGI middleware equivalent of existing WSGI middleware
* Automatic session and authentication handling in ASGI context
* Graceful fallback when ASGI dependencies are not available

Dependencies
~~~~~~~~~~~~
* Added ``asgiref>=3.2.0`` as optional dependency for ASGI support
* Updated Python version support to 3.8-3.12
* Updated Django version support to 4.0-5.0

Installation
~~~~~~~~~~~~
* For ASGI support: ``pip install django-audit-log[asgi]``
* Regular installation remains unchanged: ``pip install django-audit-log``
