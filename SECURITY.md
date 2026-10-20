# Security · Seguridad

[English](#english) · [Español](#español)

## English

### What Puente is designed for

Puente is for a **home or office network you trust**. It is not meant to be reachable from the internet. **Never** forward its port on your router or put it behind a tunnel.

### What it protects

| Protection | How |
|---|---|
| Local network only | Requests from public IP addresses are refused. The `Host` header must be an IP, `localhost` or the computer's name, which blocks DNS rebinding. On Windows, the installer opens the port only on the *Private* network profile and only for the local subnet. |
| PIN | 8 digits by default (6–12 allowed), compared in constant time. After 5 wrong attempts from one address, that address is locked out for 10 minutes; after 20 wrong attempts from the whole network, nobody can sign in for 10 minutes. |
| Sessions | Random token in an `HttpOnly; SameSite=Strict` cookie (`Secure` with HTTPS). Only its SHA-256 hash is stored on disk. Signing out deletes it, and changing the PIN or the shortcut key signs out every phone. |
| Cross-site requests | Every `POST` must carry the `X-Puente: 1` header. Other websites cannot send it without a CORS preflight, and Puente never grants one. |
| File types | The type is detected from the file's contents (magic bytes), never from its name. Only JPG, PNG, GIF, WebP, HEIC, MOV and MP4 are accepted. |
| Paths | The server builds every file name. Folders are resolved with `realpath` and must stay inside the shared folder: no `..`, no drive letters, no links that lead outside, no hidden or technical folders. |
| Sizes | Per-type size limits, a minimum free disk space, and images over 90 megapixels are never decoded. |
| Privacy | GPS location is erased on arrival from JPG, HEIC, PNG and WebP photos (EXIF and XMP) and from MOV/MP4 videos (QuickTime metadata), in place, without re-compressing. |
| Audit | Every event (sign-in, wrong PIN, upload, rejection) is written to `datos/registro/subidas.log`. PINs and tokens are never logged. |

### Known limitations

- **Plain HTTP by default.** On your Wi‑Fi, someone already connected to the same network could read the PIN, the session cookie and the files in transit. With a WPA2/WPA3 password and people you trust, this is usually acceptable. If not, enable HTTPS (below).
- **Lost phone:** the phone stays signed in for up to 30 days, and the shortcut key lives in the shortcut. Delete `llave_atajo` from `config.local.json` (or change the PIN) and restart Puente: a new key is created and every phone is signed out.
- **Anyone with the PIN can write** to any visible folder inside the shared folder. Share a folder that contains only what your phone should reach.

### Optional HTTPS

You need a certificate your phone trusts. The simplest way is [mkcert](https://github.com/FiloSottile/mkcert):

1. On the computer: `mkcert -install`, then `mkcert 192.168.1.20 localhost 127.0.0.1`, using your computer's IP. It creates two `.pem` files.
2. Put them in the Puente folder and add this to `config.local.json`:
   ```json
   "https": { "cert": "192.168.1.20.pem", "key": "192.168.1.20-key.pem", "nombre": "192.168.1.20" }
   ```
3. Install mkcert's root certificate on the phone. Its location is shown by `mkcert -CAROOT`. On iPhone: send `rootCA.pem` to the phone, install the profile in Settings, then turn it on in **Settings → General → About → Certificate Trust Settings**.
4. Restart Puente. The address now starts with `https://`.

Give your computer a fixed IP in your router, so the certificate keeps matching.

### Reporting a vulnerability

Please **do not open a public issue**. Use GitHub's private **"Report a vulnerability"** button in this repository's *Security* tab. We will reply as soon as we can and credit you in the fix, unless you prefer otherwise.

## Español

### Para qué está hecho

El Puente es para **la red de tu casa u oficina, en la que confías**. No está pensado para estar en internet. **Nunca** abras su puerto en el router ni lo pongas detrás de un túnel.

### Qué protege

| Protección | Cómo |
|---|---|
| Solo red local | Rechaza pedidos desde IP públicas. El encabezado `Host` debe ser una IP, `localhost` o el nombre del equipo, contra el *DNS rebinding*. En Windows, el instalador abre el puerto solo en el perfil de red *Privada* y solo para la subred local. |
| PIN | 8 números por defecto (se permiten de 6 a 12), comparado en tiempo constante. Después de 5 intentos equivocados desde una dirección, esa dirección queda bloqueada 10 minutos. Después de 20 intentos equivocados desde toda la red, nadie puede entrar durante 10 minutos. |
| Sesiones | Un token al azar en una cookie `HttpOnly; SameSite=Strict` (y `Secure` con HTTPS). En el disco solo queda su huella SHA-256. Al salir se borra, y al cambiar el PIN o la llave del atajo se cierra la sesión en todos los celulares. |
| Pedidos de otros sitios | Todo `POST` debe llevar el encabezado `X-Puente: 1`. Otro sitio web no puede mandarlo sin un *preflight* de CORS, y el Puente nunca lo autoriza. |
| Tipos de archivo | El tipo se revisa por el contenido del archivo (su firma), nunca por el nombre. Solo entran JPG, PNG, GIF, WebP, HEIC, MOV y MP4. |
| Rutas | El nombre de cada archivo lo arma el servidor. Las carpetas se resuelven con `realpath` y deben quedar dentro de la carpeta compartida: sin `..`, sin letras de unidad, sin enlaces que lleven afuera y sin carpetas ocultas ni técnicas. |
| Tamaños | Límite por tipo de archivo y espacio mínimo libre en el disco. Las imágenes de más de 90 megapíxeles nunca se abren. |
| Privacidad | Al llegar, se borra la ubicación GPS de las fotos JPG, HEIC, PNG y WebP (EXIF y XMP) y de los videos MOV/MP4 (metadatos QuickTime), en el mismo lugar y sin recomprimir. |
| Registro | Todo evento (entrada, PIN equivocado, subida, rechazo) queda en `datos/registro/subidas.log`. Nunca se anotan el PIN ni los tokens. |

### Límites conocidos

- **HTTP sin cifrar por defecto.** Alguien que ya esté conectado a tu mismo Wi‑Fi podría ver el PIN, la cookie de sesión y los archivos mientras viajan. Con un Wi‑Fi con clave (WPA2/WPA3) y gente de confianza, suele ser aceptable. Si no es tu caso, activa HTTPS (abajo).
- **Celular perdido:** la sesión sigue abierta hasta 30 días, y la llave del atajo queda guardada en el atajo. Borra `llave_atajo` de `config.local.json` (o cambia el PIN) y reinicia el Puente: se crea una llave nueva y se cierra la sesión en todos los celulares.
- **Quien tenga el PIN puede escribir** en cualquier carpeta visible dentro de la carpeta compartida. Comparte una carpeta que solo tenga lo que el celular debe alcanzar.

### HTTPS opcional

Necesitas un certificado en el que confíe tu celular. Lo más fácil es [mkcert](https://github.com/FiloSottile/mkcert):

1. En el computador: `mkcert -install` y luego `mkcert 192.168.1.20 localhost 127.0.0.1`, con la IP de tu computador. Se crean dos archivos `.pem`.
2. Ponlos en la carpeta del Puente y agrega esto a `config.local.json`:
   ```json
   "https": { "cert": "192.168.1.20.pem", "key": "192.168.1.20-key.pem", "nombre": "192.168.1.20" }
   ```
3. Instala en el celular el certificado raíz de mkcert, que está en la carpeta que muestra `mkcert -CAROOT`. En el iPhone: mándale `rootCA.pem` al celular, instala el perfil en Configuración y actívalo en **Configuración → General → Información → Ajustes de confianza de certificados**.
4. Reinicia el Puente. La dirección ahora empieza con `https://`.

Dale a tu computador una IP fija en el router, para que el certificado siga coincidiendo.

### Reportar una vulnerabilidad

Por favor **no abras un issue público**. Usa el botón privado **«Report a vulnerability»** de la pestaña *Security* de este repositorio. Te respondemos lo antes posible y te damos el crédito en el arreglo, si así lo quieres.
