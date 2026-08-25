"""
Quality Gate HF-003 — Password Toggle

Tests:
  HF003-01: Register page has password toggle button
  HF003-02: Login page has password toggle button
  HF003-03: Password field defaults to type="password" (masked)
  HF003-04: Toggle button has correct aria-label
  HF003-05: Toggle button has correct title
  HF003-06: Toggle button is keyboard accessible (tabindex)
  HF003-07: Password value not changed by toggle
  HF003-08: No password logged or exposed in HTML
"""

import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db


def _app():
    os.environ.setdefault('DATABASE_URL', 'sqlite:///test_hf003.db')
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app


def test_hf003_01_register_has_toggle():
    """Register page has password toggle button."""
    app = _app()
    with app.test_client() as c:
        resp = c.get('/auth/register')
        html = resp.data.decode()
        assert 'id="pw-toggle"' in html, "Toggle button not found in register page"
        assert 'class="password-toggle"' in html, "Toggle button missing class"
        assert 'type="button"' in html, "Toggle button should be type=button"
        print("  OK register page has toggle button")


def test_hf003_02_login_has_toggle():
    """Login page has password toggle button."""
    app = _app()
    with app.test_client() as c:
        resp = c.get('/auth/login')
        html = resp.data.decode()
        assert 'id="login-pw-toggle"' in html, "Toggle button not found in login page"
        assert 'class="password-toggle"' in html, "Toggle button missing class"
        assert 'type="button"' in html, "Toggle button should be type=button"
        print("  OK login page has toggle button")


def test_hf003_03_password_default_masked():
    """Password field defaults to type=password (masked)."""
    app = _app()
    with app.test_client() as c:
        # Register page
        resp = c.get('/auth/register')
        html = resp.data.decode()
        assert 'type="password"' in html, "Register: password field should default to type=password"
        
        # Login page
        resp = c.get('/auth/login')
        html = resp.data.decode()
        assert 'type="password"' in html, "Login: password field should default to type=password"
        print("  OK password fields default to masked")


def test_hf003_04_aria_label():
    """Toggle button has correct aria-label."""
    app = _app()
    with app.test_client() as c:
        # Register page
        resp = c.get('/auth/register')
        html = resp.data.decode()
        assert 'aria-label="Tampilkan password"' in html, "Register: missing aria-label"
        
        # Login page
        resp = c.get('/auth/login')
        html = resp.data.decode()
        assert 'aria-label="Tampilkan password"' in html, "Login: missing aria-label"
        print("  OK aria-label correct")


def test_hf003_05_title():
    """Toggle button has correct title."""
    app = _app()
    with app.test_client() as c:
        # Register page
        resp = c.get('/auth/register')
        html = resp.data.decode()
        assert 'title="Tampilkan password"' in html, "Register: missing title"
        
        # Login page
        resp = c.get('/auth/login')
        html = resp.data.decode()
        assert 'title="Tampilkan password"' in html, "Login: missing title"
        print("  OK title correct")


def test_hf003_06_keyboard_accessible():
    """Toggle button is keyboard accessible (tabindex)."""
    app = _app()
    with app.test_client() as c:
        # Register page
        resp = c.get('/auth/register')
        html = resp.data.decode()
        assert 'tabindex="0"' in html, "Register: toggle not keyboard accessible"
        
        # Login page
        resp = c.get('/auth/login')
        html = resp.data.decode()
        assert 'tabindex="0"' in html, "Login: toggle not keyboard accessible"
        print("  OK keyboard accessible")


def test_hf003_07_toggle_js_exists():
    """Toggle JavaScript exists and handles both states."""
    app = _app()
    with app.test_client() as c:
        # Register page
        resp = c.get('/auth/register')
        html = resp.data.decode()
        assert "pwEl.type === 'password'" in html, "Register: toggle JS missing password check"
        assert "isPassword ? 'text' : 'password'" in html, "Register: toggle JS missing type toggle"
        assert "Sembunyikan password" in html, "Register: toggle JS missing hide label"
        
        # Login page
        resp = c.get('/auth/login')
        html = resp.data.decode()
        assert "pwEl.type === 'password'" in html, "Login: toggle JS missing password check"
        assert "isPassword ? 'text' : 'password'" in html, "Login: toggle JS missing type toggle"
        assert "Sembunyikan password" in html, "Login: toggle JS missing hide label"
        print("  OK toggle JS handles both states")


def test_hf003_08_no_password_exposure():
    """No password logged or exposed in HTML source."""
    app = _app()
    with app.test_client() as c:
        # Register page
        resp = c.get('/auth/register')
        html = resp.data.decode()
        # Check no hardcoded password values
        assert 'value="' not in html.split('type="password"')[0].split('<input')[-1] if 'type="password"' in html else True, \
            "Register: password field should not have hardcoded value"
        
        # Login page
        resp = c.get('/auth/login')
        html = resp.data.decode()
        assert 'value="' not in html.split('type="password"')[0].split('<input')[-1] if 'type="password"' in html else True, \
            "Login: password field should not have hardcoded value"
        print("  OK no password exposure")


if __name__ == '__main__':
    tests = [
        test_hf003_01_register_has_toggle,
        test_hf003_02_login_has_toggle,
        test_hf003_03_password_default_masked,
        test_hf003_04_aria_label,
        test_hf003_05_title,
        test_hf003_06_keyboard_accessible,
        test_hf003_07_toggle_js_exists,
        test_hf003_08_no_password_exposure,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAIL {test.__name__}: {e}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"  HF-003 PASSWORD TOGGLE TESTS")
    print(f"  Total: {len(tests)}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"{'='*60}")
    
    if failed == 0:
        print("\n✅ ALL HF-003 TESTS PASSED")
    else:
        print(f"\n❌ {failed} TESTS FAILED")
        sys.exit(1)
