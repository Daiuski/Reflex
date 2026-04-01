"""
py2app build script for Reflex.

Usage:
    pip install py2app
    python setup.py py2app
"""
from setuptools import setup

APP        = ['reflex/main.py']
APP_NAME   = 'Reflex'
BUNDLE_ID  = 'com.daiuski.reflex'
VERSION    = '1.0.0'
ICON       = 'icon.icns'

OPTIONS = {
    'iconfile': ICON,
    'plist': {
        'CFBundleName':               APP_NAME,
        'CFBundleDisplayName':        APP_NAME,
        'CFBundleIdentifier':         BUNDLE_ID,
        'CFBundleVersion':            VERSION,
        'CFBundleShortVersionString': VERSION,
        'NSHumanReadableCopyright':   'Copyright © 2026 Daiuski. All rights reserved.',
        # Accessibility usage — shown in System Settings
        'NSAccessibilityUsageDescription':
            'Reflex needs Accessibility access to record and replay keyboard & mouse input.',
        # Microphone / screen recording not needed — suppress macOS prompts
        'NSMicrophoneUsageDescription': '',
        # Allow the subprocess (recorder_worker) to be spawned
        'NSAppTransportSecurity': {'NSAllowsArbitraryLoads': True},
        # Dock icon appears immediately
        'LSUIElement': False,
        'LSMinimumSystemVersion': '12.0',
        'NSHighResolutionCapable': True,
    },
    'packages': [
        'webview',
        'pynput',
        'mss',
        'numpy',
        'PIL',
        'AppKit',
        'Foundation',
        'objc',
        'backend',
    ],
    'includes': [
        'webview',
        'webview.platforms',
        'webview.platforms.cocoa',
        'pynput',
        'pynput.keyboard',
        'pynput.mouse',
        'pynput._util',
        'pynput._util.darwin',
        'mss',
        'mss.darwin',
        'numpy',
        'PIL',
        'PIL.Image',
        'AppKit',
        'Foundation',
        'objc',
        'ctypes',
        'threading',
        'json',
        'pathlib',
        'subprocess',
        'base64',
        'io',
    ],
    # Bundle the recorder worker script and all frontend assets
    'resources': [
        'reflex/backend/recorder_worker.py',
        'reflex/frontend',
    ],
    'excludes': [
        'tkinter',
        'matplotlib',
        'scipy',
        'IPython',
        'PyQt5',
        'PyQt6',
        'wx',
    ],
    # Keep the bundle semi-standalone so the bundled Python can run worker scripts
    'semi_standalone': False,
    'site_packages': True,
    'strip': False,      # keep debug symbols — easier to diagnose crashes
    'optimize': 1,
}

setup(
    name=APP_NAME,
    version=VERSION,
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
