#!/usr/bin/env python
"""
Test runner for django-audit-log package.

This script runs all tests including the new ASGI tests.
"""

import os
import sys
import subprocess

def main():
    # Add current directory to Python path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)
    
    # Set PYTHONPATH environment variable
    env = os.environ.copy()
    env['PYTHONPATH'] = current_dir
    
    print("Running django-audit-log tests...")
    print("=" * 50)
    
    # Run main tests
    print("\n1. Running main tests...")
    try:
        result = subprocess.run([
            sys.executable, 'audit_log/tests/runtests.py'
        ], env=env, cwd=current_dir, check=True)
        print("✓ Main tests passed")
    except subprocess.CalledProcessError as e:
        print(f"✗ Main tests failed with exit code {e.returncode}")
        return e.returncode
    
    # Run custom auth tests
    print("\n2. Running custom auth tests...")
    try:
        result = subprocess.run([
            sys.executable, 'audit_log/tests/runtests_custom_auth.py'
        ], env=env, cwd=current_dir, check=True)
        print("✓ Custom auth tests passed")
    except subprocess.CalledProcessError as e:
        print(f"✗ Custom auth tests failed with exit code {e.returncode}")
        return e.returncode
    
    # Run ASGI tests if available
    print("\n3. Running ASGI tests...")
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 'audit_log/tests/test_asgi.py', '-v'
        ], env=env, cwd=current_dir, check=True)
        print("✓ ASGI tests passed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        # If pytest is not available, try running with unittest
        try:
            result = subprocess.run([
                sys.executable, '-m', 'unittest', 'audit_log.tests.test_asgi', '-v'
            ], env=env, cwd=current_dir, check=True)
            print("✓ ASGI tests passed")
        except subprocess.CalledProcessError as e:
            print(f"✗ ASGI tests failed with exit code {e.returncode}")
            return e.returncode
    
    print("\n" + "=" * 50)
    print("All tests completed successfully! ✓")
    return 0

if __name__ == '__main__':
    sys.exit(main())
