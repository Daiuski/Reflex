import webview
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.api import ReflexAPI

PORT = 8420

def main():
    api = ReflexAPI()

    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend')
    index_path = os.path.join(frontend_dir, 'index.html')

    icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'icon.icns')

    # Set macOS dock icon 
    try:
        from AppKit import NSApplication, NSImage
        ns_app = NSApplication.sharedApplication()
        ns_icon = NSImage.alloc().initWithContentsOfFile_(icon_path)
        if ns_icon:
            ns_app.setApplicationIconImage_(ns_icon)
    except Exception:
        pass

    window = webview.create_window(
        'Reflex',
        url=index_path,
        js_api=api,
        width=960,
        height=640,
        resizable=False,
        background_color='#060a10',
    )

    api.set_window(window)

    webview.start(http_server=True, http_port=PORT, debug=False)

if __name__ == '__main__':
    main()
