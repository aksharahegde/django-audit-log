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
    
    @pytest.mark.asyncio
    async def test_process_request_skip_get(self):
        """Test that GET requests are skipped."""
        request = HttpRequest()
        request.method = "GET"
        request.user = AnonymousUser()
        
        # This should return early without connecting signals
        result = await self.middleware._process_request(request)
        self.assertIsNone(result)
    
    @pytest.mark.asyncio
    async def test_process_request_authenticated_user(self):
        """Test processing request with authenticated user."""
        request = HttpRequest()
        request.method = "POST"
        request.user = Mock()
        request.user.is_authenticated = True
        request.session = Mock()
        request.session.session_key = "test_session_key"
        
        with patch('audit_log.middleware.signals') as mock_signals:
            await self.middleware._process_request(request)
            
            # Verify signals were connected (they should be called twice, once each)
            self.assertEqual(mock_signals.pre_save.connect.call_count, 1)
            self.assertEqual(mock_signals.post_save.connect.call_count, 1)
            
            # Check that the dispatch_uid contains the middleware class and request
            pre_save_call = mock_signals.pre_save.connect.call_args
            post_save_call = mock_signals.post_save.connect.call_args
            
            self.assertIn('dispatch_uid', pre_save_call.kwargs)
            self.assertIn('dispatch_uid', post_save_call.kwargs)
            
            # Check the dispatch_uid format
            pre_save_uid = pre_save_call.kwargs['dispatch_uid']
            post_save_uid = post_save_call.kwargs['dispatch_uid']
            
            self.assertEqual(pre_save_uid[0], self.middleware.__class__)
            self.assertEqual(pre_save_uid[1], request)
            self.assertEqual(post_save_uid[0], self.middleware.__class__)
            self.assertEqual(post_save_uid[1], request)
    
    @pytest.mark.asyncio
    async def test_cleanup_signals(self):
        """Test that signals are properly cleaned up."""
        request = HttpRequest()
        
        with patch('audit_log.middleware.signals') as mock_signals:
            await self.middleware._cleanup_signals(request)
            
            # Verify signals were disconnected
            self.assertEqual(mock_signals.pre_save.disconnect.call_count, 1)
            self.assertEqual(mock_signals.post_save.disconnect.call_count, 1)
            
            # Check that the dispatch_uid is passed correctly
            pre_save_call = mock_signals.pre_save.disconnect.call_args
            post_save_call = mock_signals.post_save.disconnect.call_args
            
            self.assertIn('dispatch_uid', pre_save_call.kwargs)
            self.assertIn('dispatch_uid', post_save_call.kwargs)
            
            # Check the dispatch_uid format
            pre_save_uid = pre_save_call.kwargs['dispatch_uid']
            post_save_uid = post_save_call.kwargs['dispatch_uid']
            
            self.assertEqual(pre_save_uid[0], self.middleware.__class__)
            self.assertEqual(pre_save_uid[1], request)
            self.assertEqual(post_save_uid[0], self.middleware.__class__)
            self.assertEqual(post_save_uid[1], request)


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
        
        # Mock the _get_user_jwt function since that's what ASGIJWTAuthMiddleware actually uses
        with patch('audit_log.middleware._get_user_jwt') as mock_get_user_jwt:
            mock_user = Mock()
            mock_get_user_jwt.return_value = mock_user
            
            await self.middleware(scope, receive, send)
            
            # Verify the app was called
            self.app.assert_called_once_with(scope, receive, send)


@unittest.skipUnless(ASGI_AVAILABLE, "ASGI support not available")
class ASGIModuleTestCase(TestCase):
    """Test cases for the ASGI module."""
    
    def test_get_asgi_application(self):
        """Test the get_asgi_application function."""
        django_app = Mock()
        
        wrapped_app = get_asgi_application(django_app)
        
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
