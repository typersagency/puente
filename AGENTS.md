# Notes for AI coding agents (Claude Code, Codex, etc.)

Puente was built with Claude Code. If you are an AI agent helping someone with this repo:

- **Run the tests** before and after changing `puente.py`: `python -m unittest discover -s pruebas -v`.
- **Never launch `puente.py` just to try something** on a machine where the user runs Puente. If the port is free, your copy keeps running and the user's phone may end up talking to it. Use the tests, or a temporary `config.local.json` with `"puerto": 0` and `"escuchar": "127.0.0.1"`.
- **Security rules are not negotiable.** See `SECURITY.md` and `CONTRIBUTING.md`: local network only, PIN with lockout, the `X-Puente` header, file type by contents, every path through `Carpetas.ruta()`, and GPS erased in place without re-compressing.
- **Every visible text goes in Spanish and English:** `TX` in `web/app.js`, `TEXTOS` and `PC_TEXTOS` in `puente.py`, and `T 'es' 'en'` in the `.ps1` files.
- **`config.local.json` and `datos/` belong to the user.** They hold the PIN, the shortcut key, the shared folder, the log and the sessions. Do not print or commit them.
- **The code is written in Spanish.** Keep new names and comments in Spanish, to match.

Map:
- `puente.py`: HTTP server, standard library only, plus Pillow, pillow-heif and qrcode.
- `web/`: the phone page, with no external libraries.
- `herramientas/`: Windows tray icon, installer, shortcuts and firewall rule.
- `pruebas/`: unittest suite. It starts a real server on `127.0.0.1` with a random port.
