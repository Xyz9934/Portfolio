# FRIDAY Flutter UI

This folder contains a runnable Flutter client for the FRIDAY assistant app.

## Included

- Dark neon home screen inspired by your reference
- Live chat screen connected to the local FRIDAY Flask backend
- Tools dashboard
- Settings / control panel
- Profile screen
- Android and web project targets
- Bottom navigation shell

## Run

1. Start the backend from the repo root with `python server.py`
2. Open this folder in a terminal
3. Run `flutter pub get`
4. Run `flutter run`

## Backend URL

The app now tries to discover a working local backend automatically:

- Web: current browser host on port `5000`, then `localhost`, `127.0.0.1`, and the current LAN fallback
- Android emulator: `http://10.0.2.2:5000`, then the current LAN fallback
- Desktop: `http://127.0.0.1:5000`, then `localhost`, then the current LAN fallback

Current LAN fallback:

- `http://10.211.16.101:5000`

You can override it with:

`flutter run --dart-define=FRIDAY_API_BASE_URL=http://YOUR_HOST:5000`

## Notes

The Flutter app talks to the Flask API in [server.py](D:/FRIDAY/server.py:1). The older Kivy app is still untouched.
