"""
Tests for ASGI compatibility of django-audit-log.
"""

import unittest
from unittest.mock import Mock, patch, AsyncMock
import pytest
from django.test import TestCase
from django.http import HttpRequest
from django.contrib.auth.models import AnonymousUser

try:
    from asgiref.sync import sync_to_async
    ASGI_AVAILABLE = True
except ImportError:
    ASGI_AVAILABLE = False

if ASGI_AVAILABLE:
    from audit_log.middleware import ASGIUserLoggingMiddleware, ASGIJWTAuthMiddleware
    from audit_log.asgi import get_asgi_application


@unittest.skipUnless(ASGI_AVAILABLE, "ASGI support not available")
class ASGIMiddlewareTestCase(TestCase):
    """Test cases for ASGI middleware functionality."""
    
    def setUp(self):
        self.app = AsyncMock()
        self.middleware = ASGIUserLoggingMiddleware(self.app)
        
    @pytest.mark.asyncio
    async def test_non_http_scope_passthrough(self):
        """Test that non-HTTP scopes are passed through unchanged."""
        scope = {"type": "websocket"}
        receive = Mock()
        send = Mock()
        
        # This should not raise an exception and should call the app
        await self.middleware(scope, receive, send)
        self.app.assert_called_once_with(scope, receive, send)
    
    @pytest.mark.asyncio
    async def test_http_scope_processing(self):
        """Test that HTTP scopes are processed correctly."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test/",
            "headers": [(b"content-type", b"application/json")]
        }
        receive = Mock()
        send = Mock()
        
        # Mock the response wrapper
        with patch('audit_log.middleware.ASGIResponseWrapper') as mock_wrapper:
            mock_wrapper_instance = Mock()
            mock_wrapper.return_value = mock_wrapper_instance
            
            # This should not raise an exception
            await self.middleware(scope, receive, send)
            
            # Verify the app was called with the wrapper
            self.app.assert_called_once_with(scope, receive, mock_wrapper_instance.send)
    
    def test_process_request_skip_get(self):
        """Test that GET requests are skipped."""
        request = HttpRequest()
        request.method = "GET"
        request.user = AnonymousUser()
        
        # This should return early without connecting signals
        result = self.middleware._process_request(request)
        self.assertIsNone(result)
    
    def test_process_request_authenticated_user(self):
        """Test processing request with authenticated user."""
        request = HttpRequest()
        request.method = "POST"
        request.user = Mock()
        request.user.is_authenticated = True
        request.session = Mock()
        request.session.session_key = "test_session_key"
        
        with patch('audit_log.middleware.signals') as mock_signals:
            self.middleware._process_request(request)
            
            # Verify signals were connected
            mock_signals.pre_save.connect.assert_called_once()
            mock_signals.post_save.connect.assert_called_once()
    
    def test_cleanup_signals(self):
        """Test that signals are properly cleaned up."""
        request = HttpRequest()
        
        with patch('audit_log.middleware.signals') as mock_signals:
            self.middleware._cleanup_signals(request)
            
            # Verify signals were disconnected
            mock_signals.pre_save.disconnect.assert_called_once()
            mock_signals.post_save.disconnect.assert_called_once()


@unittest.skipUnless(ASGI_AVAILABLE, "ASGI support not available")
class ASGIJWTAuthMiddlewareTestCase(TestCase):
    """Test cases for ASGI JWT auth middleware."""
    
    def setUp(self):
        self.app = AsyncMock()
        self.middleware = ASGIJWTAuthMiddleware(self.app)
    
    @pytest.mark.asyncio
    async def test_non_http_scope_passthrough(self):
        """Test that non-HTTP scopes are passed through unchanged."""
        scope = {"type": "websocket"}
        receive = Mock()
        send = Mock()
        
        await self.middleware(scope, receive, send)
        self.app.assert_called_once_with(scope, receive, send)
    
    @pytest.mark.asyncio
    async def test_http_scope_with_jwt_auth(self):
        """Test HTTP scope processing with JWT authentication."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test/",
            "headers": [(b"authorization", b"Bearer test_token")]
        }
        receive = Mock()
        send = Mock()
        
        with patch('audit_log.middleware.SessionMiddleware') as mock_session_middleware, \
             patch('audit_log.middleware.AuthenticationMiddleware') as mock_auth_middleware:
            
            mock_session_instance = Mock()
            mock_session_middleware.return_value = mock_session_instance
            
            mock_auth_instance = Mock()
            mock_auth_middleware.return_value = mock_auth_instance
            
            await self.middleware(scope, receive, send)
            
            # Verify middleware was applied
            mock_session_instance.process_request.assert_called_once()
            mock_auth_instance.process_request.assert_called_once()
            self.app.assert_called_once_with(scope, receive, send)


@unittest.skipUnless(ASGI_AVAILABLE, "ASGI support not available")
class ASGIModuleTestCase(TestCase):
    """Test cases for the ASGI module."""
    
    def test_get_asgi_application(self):
        """Test the get_asgi_application function."""
        django_app = Mock()
        
        asgi_app = get_asgi_application()
        wrapped_app = asgi_app(django_app)
        
        self.assertIsInstance(wrapped_app, ASGIUserLoggingMiddleware)
        self.assertEqual(wrapped_app.app, django_app)
    
    def test_imports_available(self):
        """Test that ASGI classes are available for import."""
        from audit_log.asgi import ASGIUserLoggingMiddleware, ASGIJWTAuthMiddleware
        
        self.assertTrue(ASGIUserLoggingMiddleware)
        self.assertTrue(ASGIJWTAuthMiddleware)


class ASGIUnavailableTestCase(TestCase):
    """Test cases when ASGI is not available."""
    
    @unittest.skipIf(ASGI_AVAILABLE, "ASGI is available")
    def test_asgi_imports_not_available(self):
        """Test that ASGI classes are not available when asgiref is not installed."""
        with self.assertRaises(ImportError):
            from audit_log.asgi import ASGIUserLoggingMiddleware
    
    @unittest.skipIf(ASGI_AVAILABLE, "ASGI is available")
    def test_get_asgi_application_raises_error(self):
        """Test that get_asgi_application raises an error when ASGI is not available."""
        with self.assertRaises(ImportError) as context:
            from audit_log.asgi import get_asgi_application
            get_asgi_application()
        
        self.assertIn("ASGI support requires asgiref>=3.2.0", str(context.exception))
