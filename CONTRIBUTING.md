# Contributing · Cómo aportar

[English](#english) · [Español](#español)

## English

Thanks for helping! Puente is small on purpose. We prefer simple, safe and well-tested changes over big features.

1. **Open an issue first** for anything larger than a small fix, so we can agree on the approach.
2. **Fork, then create a branch** from `main`.
3. **Run the tests** before and after your change:
   ```bash
   python -m pip install -r requirements.txt
   python -m unittest discover -s pruebas -v
   ```
4. **Add a test** for every bug fix or new behavior, especially anything touching security, paths or file types.
5. **Open a pull request** that explains what changed and why, with screenshots if the phone page changed.

### Ground rules

- **Standard library first.** The server only uses Python's standard library, plus Pillow, pillow-heif and qrcode. New dependencies need a very good reason.
- **Security rules are not relaxed:** local network only, the PIN and its lockout, `X-Puente` on every `POST`, file type by contents, nothing written outside the shared folder, and never re-compressing images when erasing GPS. See [SECURITY.md](SECURITY.md).
- **No cloud, no telemetry, no external CDNs** on the phone page.
- **Two languages.** Every visible text goes in Spanish and English: `TX` in `web/app.js`, `TEXTOS` and `PC_TEXTOS` in `puente.py`, and `T 'es' 'en'` in the PowerShell scripts.
- **Brand.** The icon and the README header come from `docs/marca/puente-icono.svg` and `docs/marca/encabezado.html`; export them with `python herramientas/iconos.py` (needs Chrome or Edge).
- **Code style.** Follow the surrounding code. It is written in Spanish (names and comments), and we keep it that way for consistency. You may write your PR description in English.

Good first contributions: a tray icon for macOS or Linux, more languages, resumable uploads for very large videos, and sending files from the computer to the phone.

## Español

¡Gracias por ayudar! El Puente es pequeño a propósito. Preferimos cambios simples, seguros y con pruebas antes que funciones grandes.

1. **Primero abre un issue** si el cambio es más que un arreglo pequeño, para ponernos de acuerdo en cómo hacerlo.
2. **Haz un fork y crea una rama** desde `main`.
3. **Corre las pruebas** antes y después de tu cambio (los comandos están arriba).
4. **Agrega una prueba** por cada arreglo o comportamiento nuevo, sobre todo si toca seguridad, rutas o tipos de archivo.
5. **Abre el pull request** explicando qué cambió y por qué, con capturas si cambió la página del celular.

### Reglas de la casa

- **Primero la librería estándar.** El servidor solo usa la librería estándar de Python, más Pillow, pillow-heif y qrcode. Una dependencia nueva necesita una muy buena razón.
- **Las reglas de seguridad no se aflojan:** solo red local, el PIN y su bloqueo, `X-Puente` en todo `POST`, el tipo de archivo por su contenido, nada escrito fuera de la carpeta compartida y nunca recomprimir una imagen al borrar el GPS. Ver [SECURITY.md](SECURITY.md).
- **Sin nube, sin telemetría y sin CDN externos** en la página del celular.
- **Dos idiomas.** Todo texto visible va en español e inglés: `TX` en `web/app.js`, `TEXTOS` y `PC_TEXTOS` en `puente.py`, y `T 'es' 'en'` en los scripts de PowerShell.
- **Estilo.** Sigue el código que ya está: nombres y comentarios en español.

Buenos primeros aportes: un ícono junto al reloj para macOS o Linux, más idiomas, envíos que siguen donde iban si se corta el Wi‑Fi (para videos muy grandes) y pasar archivos del computador al celular.
