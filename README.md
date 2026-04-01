# Reflex — macOS Macro Automation

![macOS 12+](https://img.shields.io/badge/macOS-12%2B-blue?logo=apple&logoColor=white)
![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

Reflex is a lightweight macOS desktop app that lets you record keyboard and mouse actions as macros, bind them to hotkeys, and replay them on demand or automatically via color-detection triggers. No subscription, no cloud — runs fully offline.

## Screenshots

<!-- Add screenshots here -->

## Download

Grab the latest `.dmg` from the [Releases](https://github.com/Daiuski/Reflex/releases) page. Open it, drag Reflex to your Applications folder, and you're done — no Python or dependencies required.

> **Note:** On first launch macOS will prompt for Accessibility permission.
> Open **System Settings → Privacy & Security → Accessibility** and enable Reflex.

## Features

- **Record & replay** keyboard and mouse macros with a single click
- **Global hotkeys** — assign custom key combos to start/stop recording and trigger playback
- **Loop macros** indefinitely with one toggle
- **Color-trigger monitoring** — automatically fire a macro when a specific pixel color appears on screen
- **3-second countdown** with a visual overlay before playback begins
- **Sound effects** via Web Audio API (no external audio files needed)
- **Always-on-top** window mode for easy access while using other apps
- **Undo deleted macros and triggers** — nothing is gone for good
- **Save/load macros** to and from JSON files for backup or sharing
- **Settings persisted** across launches
- **Fully self-contained macOS .app** — no Python install required

## Project structure

```
ReflexProject/
├── reflex/
│   ├── main.py               # App entry point, pywebview window
│   ├── requirements.txt
│   ├── backend/
│   │   ├── api.py            # JS↔Python bridge (pywebview js_api)
│   │   ├── recorder.py       # Subprocess manager for input recording
│   │   ├── recorder_worker.py# Isolated pynput recording process
│   │   ├── player.py         # Macro playback engine
│   │   ├── monitor.py        # Color-trigger monitor
│   │   ├── hotkeys.py        # Global hotkey listener
│   │   └── hotkey_worker.py  # Isolated pynput hotkey process
│   └── frontend/
│       ├── index.html        # App shell
│       ├── app.js            # UI logic
│       ├── sounds.js         # Web Audio API sound effects
│       └── style.css         # Styles
├── setup.py                  # py2app packaging config
├── build.sh                  # Build + DMG script
├── entitlements.plist        # macOS code-signing entitlements
└── icon.icns                 # App icon
```

## License

MIT © 2026 Daiuski
