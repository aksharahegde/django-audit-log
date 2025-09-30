from functools import partial
from django.db.models import signals

# Django 4.0+ uses modern middleware patterns
from django.utils.deprecation import MiddlewareMixin

from audit_log import registration, settings
from audit_log.models import fields
from audit_log.models.managers import AuditLogManager

# ASGI support
try:
    from asgiref.sync import sync_to_async
    ASGI_AVAILABLE = True
except ImportError:
    ASGI_AVAILABLE = False


def _disable_audit_log_managers(instance):
    for attr in dir(instance):
        try:
            if isinstance(getattr(instance, attr), AuditLogManager):
                getattr(instance, attr).disable_tracking()
        except AttributeError:
            pass


def _enable_audit_log_managers(instance):
    for attr in dir(instance):
        try:
            if isinstance(getattr(instance, attr), AuditLogManager):
                getattr(instance, attr).enable_tracking()
        except AttributeError:
            pass


class UserLoggingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if settings.DISABLE_AUDIT_LOG:
            return
        if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
            return
        if hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
        else:
            user = None
        session = request.session.session_key
        update_pre_save_info = partial(self._update_pre_save_info, user,
                                       session)
        update_post_save_info = partial(self._update_post_save_info, user,
                                        session)
        signals.pre_save.connect(update_pre_save_info,
                                 dispatch_uid=(self.__class__, request,),
                                 weak=False)
        signals.post_save.connect(update_post_save_info,
                                  dispatch_uid=(self.__class__, request,),
                                  weak=False)

    def process_response(self, request, response):
        if settings.DISABLE_AUDIT_LOG:
            return
        signals.pre_save.disconnect(dispatch_uid=(self.__class__, request,))
        signals.post_save.disconnect(dispatch_uid=(self.__class__, request,))
        return response

    def process_exception(self, request, exception):
        if settings.DISABLE_AUDIT_LOG:
            return None
        signals.pre_save.disconnect(dispatch_uid=(self.__class__, request,))
        signals.post_save.disconnect(dispatch_uid=(self.__class__, request,))
        return None

    def _update_pre_save_info(self, user, session, sender, instance, **kwargs):
        registry = registration.FieldRegistry(fields.LastUserField)
        if sender in registry:
            for field in registry.get_fields(sender):
                setattr(instance, field.name, user)

        registry = registration.FieldRegistry(fields.LastSessionKeyField)
        if sender in registry:
            for field in registry.get_fields(sender):
                setattr(instance, field.name, session)

    def _update_post_save_info(self, user, session, sender, instance, created,
                               **kwargs):
        if created:
            registry = registration.FieldRegistry(fields.CreatingUserField)
            if sender in registry:
                for field in registry.get_fields(sender):
                    setattr(instance, field.name, user)
                    _disable_audit_log_managers(instance)
                    instance.save()
                    _enable_audit_log_managers(instance)

            registry = registration.FieldRegistry(
                fields.CreatingSessionKeyField)
            if sender in registry:
                for field in registry.get_fields(sender):
                    setattr(instance, field.name, session)
                    _disable_audit_log_managers(instance)
                    instance.save()
                    _enable_audit_log_managers(instance)


class JWTAuthMiddleware(MiddlewareMixin):
    """
    Convenience middleware for users of django-rest-framework-jwt.
    Fixes issue https://github.com/GetBlimp/django-rest-framework-jwt/issues/45
    """

    def get_user_jwt(self, request):
        from rest_framework.request import Request
        from rest_framework.exceptions import AuthenticationFailed
        from django.utils.functional import SimpleLazyObject
        from django.contrib.auth.middleware import get_user
        from rest_framework_jwt.authentication import JSONWebTokenAuthentication

        user = get_user(request)
        if user.is_authenticated:
            return user
        try:
            user_jwt = JSONWebTokenAuthentication().authenticate(
                Request(request))
            if user_jwt is not None:
                return user_jwt[0]
        except AuthenticationFailed:
            pass
        return user

    def process_request(self, request):
        from django.utils.functional import SimpleLazyObject
        assert hasattr(request, 'session'), \
            """The Django authentication middleware requires session middleware to be installed.
         Edit your MIDDLEWARE setting to insert 'django.contrib.sessions.middleware.SessionMiddleware'."""

        request.user = SimpleLazyObject(lambda: self.get_user_jwt(request))


# ASGI Middleware Classes
if ASGI_AVAILABLE:
    class ASGIUserLoggingMiddleware:
        """
        ASGI middleware equivalent of UserLoggingMiddleware for Django ASGI applications.
        
        Usage in ASGI application:
        
        from audit_log.middleware import ASGIUserLoggingMiddleware
        
        application = ASGIUserLoggingMiddleware(your_asgi_app)
        """
        
        def __init__(self, app):
            self.app = app
        
        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return
            
            # Create a mock request object for ASGI
            from django.http import HttpRequest
            from django.contrib.sessions.middleware import SessionMiddleware
            from django.contrib.auth.middleware import AuthenticationMiddleware
            
            request = HttpRequest()
            request.method = scope["method"]
            request.path = scope["path"]
            request.META = dict(scope.get("headers", []))
            
            # Apply session middleware
            session_middleware = SessionMiddleware(lambda req: None)
            session_middleware.process_request(request)
            
            # Apply auth middleware
            auth_middleware = AuthenticationMiddleware(lambda req: None)
            auth_middleware.process_request(request)
            
            # Process the request with our audit logging logic
            await self._process_request(request)
            
            # Create a response wrapper to handle cleanup
            response_wrapper = ASGIResponseWrapper(send, self._cleanup_signals, request)
            
            try:
                await self.app(scope, receive, response_wrapper.send)
            except Exception as e:
                await self._cleanup_signals(request)
                raise
        
        async def _process_request(self, request):
            if settings.DISABLE_AUDIT_LOG:
                return
            if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
                return
            if hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user
            else:
                user = None
            session = request.session.session_key if hasattr(request, 'session') else None
            
            update_pre_save_info = partial(self._update_pre_save_info, user, session)
            update_post_save_info = partial(self._update_post_save_info, user, session)
            
            signals.pre_save.connect(update_pre_save_info,
                                   dispatch_uid=(self.__class__, id(request),),
                                   weak=False)
            signals.post_save.connect(update_post_save_info,
                                    dispatch_uid=(self.__class__, id(request),),
                                    weak=False)
        
        async def _cleanup_signals(self, request):
            if settings.DISABLE_AUDIT_LOG:
                return
            signals.pre_save.disconnect(dispatch_uid=(self.__class__, id(request),))
            signals.post_save.disconnect(dispatch_uid=(self.__class__, id(request),))
        
        def _update_pre_save_info(self, user, session, sender, instance, **kwargs):
            registry = registration.FieldRegistry(fields.LastUserField)
            if sender in registry:
                for field in registry.get_fields(sender):
                    setattr(instance, field.name, user)

            registry = registration.FieldRegistry(fields.LastSessionKeyField)
            if sender in registry:
                for field in registry.get_fields(sender):
                    setattr(instance, field.name, session)

        def _update_post_save_info(self, user, session, sender, instance, created, **kwargs):
            if created:
                registry = registration.FieldRegistry(fields.CreatingUserField)
                if sender in registry:
                    for field in registry.get_fields(sender):
                        setattr(instance, field.name, user)
                        _disable_audit_log_managers(instance)
                        instance.save()
                        _enable_audit_log_managers(instance)

                registry = registration.FieldRegistry(fields.CreatingSessionKeyField)
                if sender in registry:
                    for field in registry.get_fields(sender):
                        setattr(instance, field.name, session)
                        _disable_audit_log_managers(instance)
                        instance.save()
                        _enable_audit_log_managers(instance)


    class ASGIResponseWrapper:
        """
        Wrapper for ASGI send callable to handle response cleanup.
        """
        
        def __init__(self, send, cleanup_func, request):
            self.send = send
            self.cleanup_func = cleanup_func
            self.request = request
            self.started = False
        
        async def send(self, message):
            if not self.started and message["type"] == "http.response.start":
                self.started = True
            elif self.started and message["type"] == "http.response.body":
                # Response is complete, cleanup signals
                await self.cleanup_func(self.request)
            
            await self.send(message)


    class ASGIJWTAuthMiddleware:
        """
        ASGI middleware equivalent of JWTAuthMiddleware for Django ASGI applications.
        """
        
        def __init__(self, app):
            self.app = app
        
        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return
            
            # Create a mock request object for ASGI
            from django.http import HttpRequest
            from django.contrib.sessions.middleware import SessionMiddleware
            from django.contrib.auth.middleware import AuthenticationMiddleware
            from django.utils.functional import SimpleLazyObject
            
            request = HttpRequest()
            request.method = scope["method"]
            request.path = scope["path"]
            request.META = dict(scope.get("headers", []))
            
            # Apply session middleware
            session_middleware = SessionMiddleware(lambda req: None)
            session_middleware.process_request(request)
            
            # Apply auth middleware
            auth_middleware = AuthenticationMiddleware(lambda req: None)
            auth_middleware.process_request(request)
            
            # Apply JWT auth logic
            assert hasattr(request, 'session'), \
                """The Django authentication middleware requires session middleware to be installed.
             Edit your MIDDLEWARE setting to insert 'django.contrib.sessions.middleware.SessionMiddleware'."""

            request.user = SimpleLazyObject(lambda: self.get_user_jwt(request))
            
            await self.app(scope, receive, send)
        
        def get_user_jwt(self, request):
            from rest_framework.request import Request
            from rest_framework.exceptions import AuthenticationFailed
            from django.utils.functional import SimpleLazyObject
            from django.contrib.auth.middleware import get_user
            from rest_framework_jwt.authentication import JSONWebTokenAuthentication

            user = get_user(request)
            if user.is_authenticated:
                return user
            try:
                user_jwt = JSONWebTokenAuthentication().authenticate(
                    Request(request))
                if user_jwt is not None:
                    return user_jwt[0]
            except AuthenticationFailed:
                pass
            return user
