# Puente by Typers — https://typersagency.com · Licencia MIT (ver LICENSE)
#
# Sube fotos y videos del celular al computador por el Wi-Fi de la casa, sin cables ni nube.
# Solo atiende a equipos de la red local, pide PIN (o la llave del atajo «Compartir → Puente»)
# y guarda en la carpeta que se elija dentro de la carpeta compartida («carpetas» → «raiz»),
# con nombres por la hora en que se tomó cada foto o video:
#   AAAA-MM-DD_HHMMSS_<carpeta>_NN.<ext>   (carpeta: la del proyecto, saltando «imagenes», «fotos»…)
# Al llegar se borra la ubicación GPS. Las fotos HEIC se convierten a JPG (el original se queda al lado).
#
# Uso: python puente.py                  (abre la pantalla con el QR)
#      python puente.py --sin-navegador  (o --no-browser)
#      python puente.py --version
# En Windows: herramientas/instalar.ps1 deja el ícono junto al reloj (herramientas/bandeja.ps1).
import datetime
import hashlib
import hmac
import html
import http.server
import io
import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.parse
import warnings
import zlib

VERSION = "1.0.0"
AQUI = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(AQUI, "web")

# Archivos de la página: solo estos se sirven (nada de rutas que vengan del navegador).
ESTATICOS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/estilos.css": ("estilos.css", "text/css; charset=utf-8"),
    "/manifest.json": ("manifest.json", "application/manifest+json"),
    "/icono-180.png": ("icono-180.png", "image/png"),
    "/icono-512.png": ("icono-512.png", "image/png"),
}
SEGURIDAD = {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; "
                               "style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}
INTENTOS = 5            # PIN equivocado: a los 5 intentos esa IP queda bloqueada…
BLOQUEO_S = 10 * 60     # …por 10 minutos
FALLOS_RED = 20         # y si en 10 minutos hay 20 fallos en toda la red (alguien cambiando de IP), se frena todo
MAX_PIXELES = 90_000_000   # fotos más grandes no se abren (protege la memoria del computador)
RE_LOTE = re.compile(r"^[a-f0-9]{8,32}$")
RE_GUARDADO = re.compile(r"^\d{4}-\d\d-\d\d_\d{6}_[A-Za-z0-9._-]+_\d{2,4}\.(jpg|png|gif|webp|heic|mp4|mov)$")
EXT_VIDEO = ("mp4", "mov")
# Lo que el servidor le dice a la persona, en español e inglés (según el idioma del iPhone).
TEXTOS = {
    'solo-red': ('Solo desde la red local.', 'Only from the local network.'),
    'direccion': ('Dirección no válida.', 'Invalid address.'),
    'falta-pin': ('Falta el PIN.', 'PIN required.'),
    'no-existe': ('No existe.', 'Not found.'),
    'carpeta-mala': ('Esa carpeta no existe o no se puede usar.', 'That folder does not exist or cannot be used.'),
    'sin-miniatura': ('Sin miniatura.', 'No thumbnail.'),
    'solo-pc': ('Esta pantalla solo se abre en el PC.', 'This screen only opens on the computer itself.'),
    'pedido': ('Pedido no válido.', 'Invalid request.'),
    'intentos': ('Demasiados intentos. Espera {min} min.', 'Too many attempts. Wait {min} min.'),
    'llave-mala': ('La llave del atajo no coincide. Revísala en la pantalla del PC.', 'The shortcut key does not match. Check it on the computer screen.'),
    'raiz': ('Elige una carpeta dentro de {raiz}.', 'Pick a folder inside {raiz}.'),
    'nombre-malo': ('Ese nombre no sirve. Usa letras, números, espacios o guiones.', "That name won't work. Use letters, numbers, spaces or dashes."),
    'ya-archivo': ('Ya hay un archivo con ese nombre.', 'There is already a file with that name.'),
    'no-creada': ('No se pudo crear la carpeta.', 'Could not create the folder.'),
    'pin-malo': ('PIN equivocado. Te quedan {n} intentos.', 'Wrong PIN. {n} attempts left.'),
    'sin-tamano': ('Falta el tamaño del archivo.', 'Missing file size.'),
    'limite': ('El archivo pasa del límite ({mb} MB) o está vacío.', 'The file is over the limit ({mb} MB) or empty.'),
    'carpeta-otra': ('Esa carpeta no existe o no se puede usar. Elige otra en la página.', 'That folder does not exist or cannot be used. Pick another one on the page.'),
    'disco': ('El disco del PC está casi lleno.', "The computer's disk is almost full."),
    'tipo': ('Solo se aceptan fotos (JPG, PNG, HEIC, WebP, GIF) y videos (MOV, MP4).', 'Only photos (JPG, PNG, HEIC, WebP, GIF) and videos (MOV, MP4) are accepted.'),
    'limite-foto': ('La foto pasa del límite ({mb} MB).', 'The photo is over the limit ({mb} MB).'),
    'no-guardado': ('No se pudo guardar. Vuelve a intentarlo.', 'Could not save it. Please try again.'),
    'heic': ('Se guardó el HEIC, pero no se pudo pasar a JPG.', 'The HEIC was saved, but it could not be converted to JPG.'),
    'en-pc': ('En el PC: {donde}', 'On the computer: {donde}'),
}
FFMPEG = shutil.which("ffmpeg")   # solo para las miniaturas de los videos; sin él, los videos salen con ▶
LETRAS_LLAVE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # sin 0/O ni 1/I, para escribirla sin confundirse
RE_LLAVE = re.compile(r"^[A-Z2-9]{4}(-[A-Z2-9]{4}){4}$")


# ---------- Configuración ----------
def cargar_config(carpeta=AQUI):
    """config.json (general) + config.local.json (de este equipo: PIN, rutas). Crea el PIN la primera vez."""
    with io.open(os.path.join(carpeta, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    ruta_local = os.path.join(carpeta, "config.local.json")
    local = {}
    if os.path.exists(ruta_local):
        with io.open(ruta_local, encoding="utf-8") as f:
            local = json.load(f)
    for k, v in local.items():   # lo local gana, clave por clave (también dentro de «carpetas» y «https»)
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k] = {**cfg[k], **v}
        else:
            cfg[k] = v
    nuevo = False
    if not re.fullmatch(r"\d{6,12}", str(cfg.get("pin", ""))):
        cfg["pin"] = local["pin"] = "".join(secrets.choice("0123456789") for _ in range(8))
        nuevo = True
    # Llave del atajo «Compartir → Puente» del iPhone. Para quitarle el acceso a un iPhone perdido, bórrala y reinicia.
    if not RE_LLAVE.match(str(cfg.get("llave_atajo", ""))):
        cfg["llave_atajo"] = local["llave_atajo"] = "-".join(
            "".join(secrets.choice(LETRAS_LLAVE) for _ in range(4)) for _ in range(5))
        nuevo = True
    if nuevo:
        local.setdefault("_nota", "De este equipo; no va a git. Cambia el PIN aquí (6 a 12 números) y reinicia el puente. "
                                  "Si borras llave_atajo, se crea otra y el atajo del iPhone deja de funcionar hasta ponerle la nueva.")
        with io.open(ruta_local, "w", encoding="utf-8") as f:
            json.dump(local, f, ensure_ascii=False, indent=2)
    c = cfg.setdefault("carpetas", {})
    c["raiz"] = os.path.realpath(os.path.expanduser(c.get("raiz") or carpeta_por_defecto()))
    if not os.path.isdir(c["raiz"]):
        raise SystemExit(f"No existe la carpeta compartida {c['raiz']!r}: revisa «carpetas» → «raiz» en config.local.json. / "
                         f"Shared folder not found: check «carpetas» → «raiz» in config.local.json.")
    https = cfg.get("https") or {}
    if https.get("cert"):
        for k in ("cert", "key"):
            https[k] = os.path.normpath(os.path.join(carpeta, os.path.expanduser(https.get(k) or "")))
    cfg["datos"] = os.path.normpath(os.path.join(carpeta, cfg.get("datos", "datos")))
    return cfg


def carpeta_por_defecto():
    """Si no se configuró otra: la carpeta de imágenes del usuario. Nunca toda su carpeta personal:
    si no encuentra una, crea ~/Puente."""
    casa = os.path.realpath(os.path.expanduser("~"))
    candidatas = []
    try:   # Linux: la carpeta de imágenes en el idioma del sistema
        r = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True, text=True, timeout=3)
        candidatas.append(r.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    candidatas += [os.path.join(casa, n) for n in ("Pictures", "Imágenes", "Imagenes", "Images", "Bilder", "Immagini", "Imagens")]
    for ruta in candidatas:
        if ruta and os.path.isdir(ruta) and os.path.normcase(os.path.realpath(ruta)) != os.path.normcase(casa):
            return ruta
    ruta = os.path.join(casa, "Puente")
    os.makedirs(ruta, exist_ok=True)
    return ruta


# ---------- Nombres y tipos ----------
def limpiar_parte(texto, largo=40):
    """Deja solo letras sin tilde, números, punto y guion. «M.11» sigue siendo «M.11»; «../x» queda «x»."""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^A-Za-z0-9.-]+", "-", t)
    t = re.sub(r"\.{2,}", ".", t).strip(".-")
    return t[:largo].strip(".-")


FTYP_HEIC = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"}
FTYP_MP4 = {b"isom", b"iso2", b"iso4", b"iso5", b"iso6", b"mp41", b"mp42", b"M4V ", b"avc1", b"3gp4", b"3gp5", b"3g2a"}


def detectar(cab):
    """Mira los primeros bytes (la «firma») y dice qué es de verdad, sin creerle al nombre. None = no se acepta."""
    if cab[:3] == b"\xff\xd8\xff":
        return "jpg"
    if cab[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if cab[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if cab[:4] == b"RIFF" and cab[8:12] == b"WEBP":
        return "webp"
    if cab[4:8] == b"ftyp":
        marca = cab[8:12]
        if marca in FTYP_HEIC:
            return "heic"
        if marca == b"qt  ":
            return "mov"
        if marca in FTYP_MP4:
            return "mp4"
    return None


def ip_permitida(ip):
    """Solo red local (192.168.x, 10.x, 172.16–31.x) o el mismo PC. Nada que venga de internet."""
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if getattr(a, "ipv4_mapped", None):
        a = a.ipv4_mapped
    return a.is_loopback or (a.is_private and not a.is_unspecified)


def es_local(ip):
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if getattr(a, "ipv4_mapped", None):
        a = a.ipv4_mapped
    return a.is_loopback


def ip_de_la_red():
    """La IP del PC en el Wi-Fi (la que usa para salir; no envía nada)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def avisar(texto):
    """Escribe en la ventana del puente. Si la consola no puede mostrar algo, no pasa nada: la subida sigue."""
    try:
        print(texto, flush=True)
    except (UnicodeError, OSError, ValueError):
        pass


def tamano(n):
    return f"{n / 1048576:.1f} MB".replace(".", ",")


# ---------- Ubicación y fecha de toma ----------
TAM_TIPO = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}   # bytes por tipo de dato EXIF
RE_EXIF = re.compile(rb"Exif\x00\x00(?=MM\x00\*|II\*\x00)")
RE_EXIF_CRUDO = re.compile(rb"(?:eXIf|EXIF[\s\S]{4})(?=MM\x00\*|II\*\x00)")   # PNG y WebP: el TIFF sin «Exif\0\0»
RE_XMP_GPS = re.compile(rb'exif:GPS[A-Za-z]+(?:="([^"]*)"|>([^<]*)<)')
RE_ISO6709 = re.compile(rb"[+-]\d{2}(?:\.\d+)?[+-]\d{3}(?:\.\d+)?(?:[+-]\d+(?:\.\d+)?)?(?:CRS[A-Za-z0-9_:]*)?/")
RE_FECHA_QT = re.compile(rb"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)[+-]\d{4}")
SEGUNDOS_1904 = 2082844800   # los videos cuentan el tiempo desde 1904


def _borrar_gps_tiff(d, base):
    """Vacía el bloque GPS de un EXIF (en formato TIFF desde d[base]) sin mover ningún otro byte."""
    orden = {b"MM": ">", b"II": "<"}.get(bytes(d[base:base + 2]))
    if not orden:
        return False
    u16 = lambda o: struct.unpack_from(orden + "H", d, base + o)[0]
    u32 = lambda o: struct.unpack_from(orden + "I", d, base + o)[0]
    ifd0 = u32(4)
    gps = next((u32(ifd0 + 10 + 12 * i) for i in range(u16(ifd0)) if u16(ifd0 + 2 + 12 * i) == 0x8825), 0)
    if not gps or base + gps + 2 > len(d):
        return False
    n = u16(gps)
    fin_tabla = base + gps + 2 + 12 * n
    if fin_tabla > len(d):
        return False
    for i in range(n):
        e = gps + 2 + 12 * i
        tam = TAM_TIPO.get(u16(e + 2), 1) * u32(e + 4)
        if tam > 4:
            o = base + u32(e + 8)
            if o + tam <= len(d):
                d[o:o + tam] = bytes(tam)
    d[base + gps:fin_tabla] = bytes(fin_tabla - base - gps)   # la tabla queda vacía (0 datos)
    return n > 0


def _buscar_moov(f):
    """Ubica el bloque «moov» de un MOV/MP4 (ahí van la fecha y el GPS). Devuelve (posición, bytes) o None."""
    f.seek(0, 2)
    fin, pos = f.tell(), 0
    while pos + 8 <= fin:
        f.seek(pos)
        cab = f.read(16)
        tam, tipo = struct.unpack(">I4s", cab[:8])
        ini = 8
        if tam == 1:
            tam, ini = struct.unpack(">Q", cab[8:16])[0], 16
        elif tam == 0:
            tam = fin - pos
        if tam < ini:
            return None
        if tipo == b"moov":
            if tam > 64 << 20:
                return None
            f.seek(pos)
            return pos, bytearray(f.read(tam))
        pos += tam
    return None


def _arreglar_crc_png(d):
    """Un PNG lleva una suma de control por bloque: después de cambiar bytes, se recalculan."""
    i = 8
    while i + 12 <= len(d):
        n = struct.unpack_from(">I", d, i)[0]
        fin = i + 8 + n
        if fin + 4 > len(d):
            break
        struct.pack_into(">I", d, fin, zlib.crc32(bytes(d[i + 4:fin])) & 0xFFFFFFFF)
        if d[i + 4:i + 8] == b"IEND":
            break
        i = fin + 4


def quitar_ubicacion(ruta, tipo):
    """Borra el GPS (dónde se tomó) sin tocar la imagen ni el video: esos bytes quedan en ceros o espacios."""
    with open(ruta, "r+b") as f:
        if tipo in EXT_VIDEO:
            moov = _buscar_moov(f)
            if not moov:
                return False
            pos, d = moov
            cambios = [m.span() for m in RE_ISO6709.finditer(d)]
            for a, b in cambios:
                d[a:b] = b" " * (b - a)
            if cambios:
                f.seek(pos)
                f.write(d)
            return bool(cambios)
        d = bytearray(f.read())
        cambio = False
        inicios = [m.end() for m in RE_EXIF.finditer(d)] + [m.end() for m in RE_EXIF_CRUDO.finditer(d)]
        for i in inicios:   # la foto principal y sus copias internas (HDR, miniatura)
            try:
                cambio = _borrar_gps_tiff(d, i) or cambio
            except struct.error:
                pass
        for m in list(RE_XMP_GPS.finditer(d)):   # el GPS repetido en el XMP: el valor queda en espacios
            g = 1 if m.group(1) is not None else 2
            a, b = m.span(g)
            if b > a:
                d[a:b] = b" " * (b - a)
                cambio = True
        if cambio and tipo == "png":
            _arreglar_crc_png(d)
        if cambio:
            f.seek(0)
            f.write(d)
        return cambio


def fecha_de_toma(ruta, tipo):
    """Cuándo se tomó la foto o empezó el video, en la hora del iPhone. None si el archivo no lo dice."""
    try:
        if tipo in EXT_VIDEO:
            with open(ruta, "rb") as f:
                moov = _buscar_moov(f)
            if not moov:
                return None
            d = moov[1]
            m = RE_FECHA_QT.search(d)   # com.apple.quicktime.creationdate, ya en hora local
            if m:
                fecha = datetime.datetime.strptime(m.group(1).decode(), "%Y-%m-%dT%H:%M:%S")
            else:
                i = d.find(b"mvhd")
                if i < 0:
                    return None
                t = struct.unpack_from(">Q" if d[i + 4] == 1 else ">I", d, i + 8)[0]
                if not t:
                    return None
                fecha = datetime.datetime.fromtimestamp(t - SEGUNDOS_1904)
        else:
            with abrir_imagen(ruta, heic=tipo == "heic") as im:
                exif = im.getexif()
            texto = exif.get_ifd(0x8769).get(36867) or exif.get(306)   # DateTimeOriginal o DateTime
            if not texto:
                return None
            fecha = datetime.datetime.strptime(str(texto).strip("\x00 ")[:19], "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None
    if not datetime.datetime(2000, 1, 1) < fecha < datetime.datetime.now() + datetime.timedelta(days=1):
        return None
    return fecha


# ---------- Carpetas ----------
TECNICAS = {"node_modules", "__pycache__", "venv", "env", "site-packages", "dist", "build", "target", "bin", "obj"}
GENERICAS = {"imagenes", "imágenes", "images", "img", "fotos", "videos", "media", "assets", "capturas",
             "bitacora", "bitácora", "recursos", "archivos"}
RESERVADOS = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


class Carpetas:
    """Dónde se puede guardar: solo dentro de la carpeta compartida («carpetas» → «raiz»), sin carpetas ocultas, técnicas
    (.git, node_modules…) ni las de la lista «ocultar» (respaldos, versiones anteriores…).
    Una carpeta se nombra por su ruta relativa con «/»: «MiProyecto/fotos»."""

    def __init__(self, cfg):
        self.raiz = cfg["carpetas"]["raiz"]
        self.ocultar = {n.lower() for n in cfg["carpetas"].get("ocultar", [])}

    def visible(self, nombre):
        n = nombre.lower()
        return (bool(nombre) and not nombre.startswith((".", "$")) and not nombre.endswith((".", " ")) and "~" not in nombre
                and n not in TECNICAS and n not in self.ocultar)

    @staticmethod
    def escondida(ruta):
        """Carpeta marcada como oculta o de sistema en Windows."""
        try:
            return bool(getattr(os.lstat(ruta), "st_file_attributes", 0) & 6)
        except OSError:
            return True

    def ruta(self, rel):
        """Ruta real de una carpeta, o None si sale de la raíz, está escondida o no existe."""
        partes = [x for x in str(rel or "").replace("\\", "/").split("/") if x]
        if any(x in (".", "..") or ":" in x or not self.visible(x) for x in partes):
            return None
        ruta = os.path.realpath(os.path.join(self.raiz, *partes))
        raiz = os.path.normcase(self.raiz)
        if os.path.normcase(ruta) != raiz and not os.path.normcase(ruta).startswith(raiz.rstrip(os.sep) + os.sep):
            return None   # un acceso directo o enlace que lleva afuera
        if not os.path.isdir(ruta):
            return None
        # Otra vez con los nombres ya resueltos: en Windows «Viejo.» o «NODE_M~1» llevan a carpetas escondidas.
        actual = self.raiz
        for x in [y for y in os.path.relpath(ruta, self.raiz).split(os.sep) if y not in ("", ".")]:
            actual = os.path.join(actual, x)
            if not self.visible(x) or self.escondida(actual):
                return None
        return ruta

    def relativa(self, ruta):
        r = os.path.relpath(ruta, self.raiz).replace("\\", "/")
        return "" if r == "." else r

    def listar(self, ruta):
        hijas = []
        with os.scandir(ruta) as it:
            for e in it:
                try:
                    if (not e.is_dir(follow_symlinks=False) or e.is_symlink() or not self.visible(e.name)
                            or getattr(e.stat(follow_symlinks=False), "st_file_attributes", 0) & 6):   # ocultas o de sistema
                        continue
                except OSError:
                    continue
                hijas.append(e.name)
        return sorted(hijas, key=str.lower)

    @staticmethod
    def proyecto(rel):
        """La carpeta del proyecto: la última que no sea genérica («imagenes», «fotos», «bitacora»…). (posición, nombre)"""
        partes = [x for x in rel.split("/") if x]
        for i in range(len(partes) - 1, -1, -1):
            if partes[i].lower() not in GENERICAS:
                return i, partes[i]
        return (len(partes) - 1, partes[-1]) if partes else (-1, "")

    @classmethod
    def etiqueta(cls, rel):
        """La parte del nombre del archivo: el proyecto, con letras sin tilde, números, puntos y guiones."""
        return limpiar_parte(cls.proyecto(rel)[1], 30) or "carpeta"

    def info(self, rel):
        i, nombre = self.proyecto(rel)
        return {"carpeta": rel, "etiqueta": self.etiqueta(rel), "nombre": nombre or rel, "posicion": i,
                "partes": [x for x in rel.split("/") if x]}


def nombre_de_carpeta(texto):
    """Nombre para una carpeta nueva: letras (con tilde), números, espacios, guiones y puntos. None si no sirve."""
    t = re.sub(r"[^\w .-]+", "", unicodedata.normalize("NFC", str(texto)))
    t = re.sub(r"\s+", " ", t).strip(" .")[:60].strip(" .")
    if not t or t.upper().split(".")[0] in RESERVADOS or t.startswith(("-", "$", "~")):
        return None
    return t


# ---------- El puente ----------
class Puente:
    """Estado compartido: configuración, sesiones, intentos de PIN, lotes y registro."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.carpetas = Carpetas(cfg)
        self.datos = cfg["datos"]
        self.registro_dir = os.path.join(self.datos, "registro")
        os.makedirs(self.registro_dir, exist_ok=True)
        self.candado = threading.Lock()
        self.fallos = {}        # ip -> [intentos, bloqueado_hasta]
        self.lotes = {}         # lote -> (marca de tiempo, creado)
        self.ruta_sesiones = os.path.join(self.datos, "sesiones.json")
        self.sesiones = {}      # sha256(token) -> [vence (epoch), huella del PIN y la llave]
        # Si cambian el PIN o la llave del atajo, todas las sesiones abiertas dejan de servir (celular perdido).
        self.huella_acceso = hashlib.sha256(f"{cfg['pin']}|{cfg['llave_atajo']}".encode()).hexdigest()[:16]
        try:
            with io.open(self.ruta_sesiones, encoding="utf-8") as f:
                self.sesiones = {k: v for k, v in json.load(f).items()
                                 if isinstance(v, list) and len(v) == 2 and v[0] > time.time() and v[1] == self.huella_acceso}
        except (OSError, ValueError, TypeError):
            pass
        self.fallos_red = []    # momentos de los últimos intentos fallidos, de cualquier IP
        self.huellas = self._leer_huellas()
        # La carpeta elegida (la página la cambia; ahí llega también lo del atajo) y las últimas usadas.
        self.ruta_destino = os.path.join(self.datos, "destino.json")
        self.destino, self.recientes = "", []
        try:
            with io.open(self.ruta_destino, encoding="utf-8") as f:
                d = json.load(f)
            self.recientes = [r for r in d.get("recientes", []) if isinstance(r, str) and self.carpetas.ruta(r)][:6]
            if isinstance(d.get("carpeta"), str) and self.carpetas.ruta(d["carpeta"]):
                self.destino = d["carpeta"]
        except (OSError, ValueError):
            pass
        inicial = cfg["carpetas"].get("inicial", "")
        if not self.destino and inicial and self.carpetas.ruta(inicial):
            self.destino = inicial
            self.recientes = self.recientes or [inicial]

    def fijar_destino(self, rel):
        with self.candado:
            self.destino = rel
            self.recientes = [rel] + [r for r in self.recientes if r != rel][:5]
            tmp = self.ruta_destino + ".tmp"
            with io.open(tmp, "w", encoding="utf-8") as f:
                json.dump({"carpeta": rel, "recientes": self.recientes}, f, ensure_ascii=False)
            os.replace(tmp, self.ruta_destino)

    # Registro: una línea JSON por evento en datos/registro/subidas.log
    def anotar(self, **ev):
        ev = {"fecha": datetime.datetime.now().isoformat(timespec="seconds"), **ev}
        with self.candado, io.open(os.path.join(self.registro_dir, "subidas.log"), "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    def _leer_huellas(self):
        """Huellas (sha256) de lo ya subido a cada carpeta, para no guardar dos veces la misma foto."""
        h = {}
        try:
            with io.open(os.path.join(self.registro_dir, "subidas.log"), encoding="utf-8") as f:
                for linea in f:
                    try:
                        ev = json.loads(linea)
                    except ValueError:
                        continue
                    if ev.get("evento") == "subida" and ev.get("carpeta"):
                        h[(os.path.normcase(ev["carpeta"]), ev["sha256"])] = ev.get("jpg") or ev["guardado"]
        except OSError:
            pass
        return h

    # Sesiones: el navegador guarda un token al azar; aquí solo queda su huella.
    def nueva_sesion(self):
        token = secrets.token_urlsafe(32)
        with self.candado:
            self.sesiones[hashlib.sha256(token.encode()).hexdigest()] = [time.time() + self.cfg["sesion_dias"] * 86400, self.huella_acceso]
            self._guardar_sesiones()
        return token

    def sesion_valida(self, token):
        if not token:
            return False
        s = self.sesiones.get(hashlib.sha256(token.encode()).hexdigest())
        return bool(s and s[0] > time.time())

    def cerrar_sesion(self, token):
        with self.candado:
            if self.sesiones.pop(hashlib.sha256(str(token).encode()).hexdigest(), None):
                self._guardar_sesiones()

    def _guardar_sesiones(self):
        ahora = time.time()
        self.sesiones = {k: v for k, v in self.sesiones.items() if v[0] > ahora}
        tmp = self.ruta_sesiones + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.sesiones, f)
        os.replace(tmp, self.ruta_sesiones)

    # PIN y llave con freno: 5 intentos fallidos por IP (entre los dos) y queda bloqueada 10 minutos.
    def probar_pin(self, ip, pin):
        return self._probar(ip, str(pin), str(self.cfg["pin"]), "pin-equivocado")

    def probar_llave(self, ip, llave):
        limpia = re.sub(r"[\s-]", "", str(llave)).upper()
        return self._probar(ip, limpia, self.cfg["llave_atajo"].replace("-", ""), "llave-equivocada")

    def _probar(self, ip, dado, correcto, evento):
        ahora = time.time()
        with self.candado:
            n, hasta = self.fallos.get(ip, [0, 0])
            if hasta > ahora:
                return "bloqueado", int(hasta - ahora)
            self.fallos_red = [t for t in self.fallos_red if ahora - t < BLOQUEO_S]
            if len(self.fallos_red) >= FALLOS_RED:   # demasiados fallos en toda la red: nadie entra por un rato
                return "bloqueado", int(BLOQUEO_S - (ahora - self.fallos_red[0]))
            if hmac.compare_digest(dado.encode(), correcto.encode()):
                self.fallos.pop(ip, None)
                return "ok", 0
            n += 1
            self.fallos_red.append(ahora)
            self.fallos[ip] = [0, ahora + BLOQUEO_S] if n >= INTENTOS else [n, 0]
        self.anotar(evento=evento, ip=ip, intento=n)
        return ("bloqueado", BLOQUEO_S) if n >= INTENTOS else ("mal", INTENTOS - n)

    def marca_de_lote(self, lote):
        """Todas las fotos de una misma tanda llevan la misma hora y se numeran 01, 02, 03…"""
        ahora = time.time()
        with self.candado:
            self.lotes = {k: v for k, v in self.lotes.items() if ahora - v[1] < 6 * 3600}
            if lote not in self.lotes:
                self.lotes[lote] = (datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S"), ahora)
            return self.lotes[lote][0]

    def reservar_nombre(self, destino, prefijo, ext, tmp):
        """Busca el siguiente NN libre y mueve el archivo temporal a su nombre final (sin pisar nada)."""
        with self.candado:
            usados = {os.path.splitext(n)[0] for n in os.listdir(destino) if n.startswith(prefijo)}
            nn = 1
            while f"{prefijo}{nn:02d}" in usados:
                nn += 1
            nombre = f"{prefijo}{nn:02d}.{ext}"
            os.replace(tmp, os.path.join(destino, nombre))
            return nombre


_PIL_LISTO = False


def abrir_imagen(ruta, heic=False):
    """Abre una imagen con Pillow, sin aceptar las que tengan más de MAX_PIXELES (una «bomba» llenaría la memoria)."""
    global _PIL_LISTO
    from PIL import Image
    if not _PIL_LISTO:
        Image.MAX_IMAGE_PIXELS = MAX_PIXELES
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        _PIL_LISTO = True
    if heic:
        import pillow_heif
        pillow_heif.register_heif_opener()
    return Image.open(ruta)


def convertir_heic(ruta_heic):
    """HEIC -> JPG al lado (misma base). Gira la foto según la cámara y no copia los metadatos (ni el GPS)."""
    from PIL import ImageOps
    ruta_jpg = os.path.splitext(ruta_heic)[0] + ".jpg"
    with abrir_imagen(ruta_heic, heic=True) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.save(ruta_jpg, "JPEG", quality=90, optimize=True)
    return ruta_jpg


def miniatura(origen, cache):
    """Miniatura de 360 px guardada en datos/miniaturas (se hace una vez)."""
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(origen):
        return cache
    from PIL import ImageOps
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with abrir_imagen(origen, heic=origen.lower().endswith(".heic")) as im:
        im = ImageOps.exif_transpose(im)
        im.thumbnail((360, 360))
        im.convert("RGB").save(cache, "JPEG", quality=78)
    return cache


def miniatura_video(origen, cache):
    """Un cuadro del video como miniatura (con ffmpeg). None si no hay ffmpeg o no se pudo."""
    if not FFMPEG:
        return None
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(origen):
        return cache
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    for segundo in ("0.5", "0"):   # un video de menos de medio segundo no tiene cuadro en 0,5
        try:
            subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", segundo, "-i", origen, "-frames:v", "1",
                            "-vf", "scale=360:360:force_original_aspect_ratio=decrease", "-q:v", "5", cache],
                           timeout=30, check=True, stdin=subprocess.DEVNULL, capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if os.path.exists(cache) and os.path.getsize(cache):
                return cache
        except (OSError, subprocess.SubprocessError):
            pass
    return None


class Manejador(http.server.BaseHTTPRequestHandler):
    server_version = "PuenteFotos/1"
    sys_version = ""
    timeout = 120
    protocol_version = "HTTP/1.1"

    @property
    def puente(self):
        return self.server.puente

    def log_message(self, formato, *args):   # sin ruido en la consola; lo importante va al registro
        pass

    # ----- respuestas -----
    def responder(self, codigo, cuerpo=b"", tipo="application/json; charset=utf-8", extra=None):
        if isinstance(cuerpo, (dict, list)):
            cuerpo = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        elif isinstance(cuerpo, str):
            cuerpo = cuerpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        for k, v in {**SEGURIDAD, **(extra or {})}.items():
            self.send_header(k, v)
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(cuerpo)

    def idioma(self):
        """«es» o «en»: lo que pida la página (X-Idioma) o, si no, el idioma del navegador."""
        pedido = (self.headers.get("X-Idioma") or self.headers.get("Accept-Language") or "").strip().lower()
        return "es" if pedido.startswith("es") else "en"

    def t(self, clave, **datos):
        es, en = TEXTOS[clave]
        return (es if self.idioma() == "es" else en).format(**datos)

    def error(self, codigo, mensaje):
        self.responder(codigo, {"ok": False, "error": mensaje})

    def ip(self):
        return self.client_address[0]

    def cookie(self, nombre):
        for parte in self.headers.get("Cookie", "").split(";"):
            k, _, v = parte.strip().partition("=")
            if k == nombre:
                return v
        return ""

    def con_sesion(self):
        return self.puente.sesion_valida(self.cookie("puente"))

    def host_valido(self):
        """Contra «DNS rebinding»: solo se aceptan direcciones IP, localhost o el nombre de este PC."""
        host = self.headers.get("Host", "").strip().lower()
        if host.startswith("["):
            nombre = host[1:host.find("]")]
        else:
            nombre = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
        propio = str((self.puente.cfg.get("https") or {}).get("nombre") or "").lower()   # el nombre del certificado, si hay HTTPS
        if nombre in ("localhost", socket.gethostname().lower(), socket.gethostname().lower() + ".local") or (propio and nombre == propio):
            return True
        try:
            ipaddress.ip_address(nombre)
            return True
        except ValueError:
            return False

    def filtro(self):
        """Lo primero en cada pedido: ¿viene de la red local y a una dirección válida?"""
        if not ip_permitida(self.ip()):
            self.close_connection = True
            self.error(403, self.t("solo-red"))
            return False
        if not self.host_valido():
            self.close_connection = True
            self.error(421, self.t("direccion"))
            return False
        return True

    # ----- GET -----
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self.filtro():
            return
        url = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(url.query)
        if url.path in ESTATICOS:
            archivo, tipo = ESTATICOS[url.path]
            with open(os.path.join(WEB, archivo), "rb") as f:
                return self.responder(200, f.read(), tipo, {"Cache-Control": "no-cache"})
        if url.path == "/pc":
            return self.pagina_pc()
        if url.path == "/api/estado":
            return self.responder(200, {"ok": True, "sesion": self.con_sesion()})
        if not self.con_sesion():
            return self.error(401, self.t("falta-pin"))
        if url.path == "/api/inicio":
            cfg, pu = self.puente.cfg, self.puente
            return self.responder(200, {"ok": True, "version": VERSION, "limites": {"imagen": cfg["limite_imagen_mb"], "video": cfg["limite_video_mb"]},
                                        "raiz": os.path.basename(pu.carpetas.raiz) or pu.carpetas.raiz,
                                        "destino": pu.carpetas.info(pu.destino) if pu.destino else None,
                                        "recientes": [pu.carpetas.info(r) for r in pu.recientes],
                                        "miniaturas_video": bool(FFMPEG)})
        if url.path == "/api/carpetas":
            return self.carpetas(q.get("c", [""])[0])
        if url.path == "/api/recientes":
            return self.recientes(q.get("c", [""])[0])
        if url.path == "/miniatura":
            return self.servir_miniatura(q.get("c", [""])[0], q.get("f", [""])[0])
        self.error(404, self.t("no-existe"))

    def carpetas(self, rel):
        """Las carpetas que hay dentro de una (para navegar desde el iPhone)."""
        cs = self.puente.carpetas
        ruta = cs.ruta(rel)
        if not ruta:
            return self.error(404, self.t("carpeta-mala"))
        rel = cs.relativa(ruta)
        try:
            hijas = cs.listar(ruta)
        except OSError:
            hijas = []
        self.responder(200, {"ok": True, **cs.info(rel), "carpetas": hijas, "raiz": os.path.basename(cs.raiz) or cs.raiz})

    def archivo_guardado(self, rel, nombre):
        """Ruta de un archivo que subió el puente, solo si el nombre tiene nuestro formato y existe en esa carpeta."""
        carpeta = self.puente.carpetas.ruta(rel)
        if not carpeta or not RE_GUARDADO.match(nombre):
            return None
        ruta = os.path.join(carpeta, nombre)
        return ruta if os.path.isfile(ruta) else None

    def recientes(self, rel):
        carpeta = self.puente.carpetas.ruta(rel)
        if not carpeta:
            return self.error(404, self.t("carpeta-mala"))
        try:
            # Lo último que llegó primero (los nombres van por la hora de la foto, no de la subida).
            nombres = sorted((n for n in os.listdir(carpeta) if RE_GUARDADO.match(n)),
                             key=lambda n: (os.path.getmtime(os.path.join(carpeta, n)), n), reverse=True)
        except OSError:
            nombres = []
        bases = {os.path.splitext(n)[0] for n in nombres if n.endswith(".jpg")}
        lista = [{"nombre": n, "video": n.rsplit(".", 1)[1] in EXT_VIDEO}
                 for n in nombres if not (n.endswith(".heic") and os.path.splitext(n)[0] in bases)]
        self.responder(200, {"ok": True, "archivos": lista[:24], "miniaturas_video": bool(FFMPEG)})

    def servir_miniatura(self, rel, nombre):
        ruta = self.archivo_guardado(rel, nombre)
        if not ruta:
            return self.error(404, self.t("sin-miniatura"))
        cache = os.path.join(self.puente.datos, "miniaturas", hashlib.sha256(os.path.normcase(ruta).encode()).hexdigest()[:24] + ".jpg")
        try:
            hecha = miniatura_video(ruta, cache) if nombre.rsplit(".", 1)[1] in EXT_VIDEO else miniatura(ruta, cache)
            if not hecha:
                return self.error(404, self.t("sin-miniatura"))
            with open(hecha, "rb") as f:
                self.responder(200, f.read(), "image/jpeg", {"Cache-Control": "private, max-age=86400"})
        except Exception:
            self.error(404, self.t("sin-miniatura"))

    def pagina_pc(self):
        """Pantalla del PC (solo desde este mismo equipo): dirección, PIN y QR para el celular."""
        if not es_local(self.ip()):
            return self.error(403, self.t("solo-pc"))
        tx = PC_TEXTOS[self.idioma()]
        dire = self.server.direccion
        try:
            import qrcode
            import qrcode.image.svg
            img = qrcode.make(dire, image_factory=qrcode.image.svg.SvgPathImage, box_size=12, border=2)
            qr = img.to_string(encoding="unicode")
        except Exception:
            qr = f"<p>{tx['sin_qr']}</p>"
        e = html.escape
        pu = self.puente
        filas = "".join(f"<li><code>{e(os.path.join(pu.carpetas.raiz, r))}</code></li>" for r in pu.recientes) or f"<li>{tx['ninguna']}</li>"
        destino = os.path.join(pu.carpetas.raiz, pu.destino) if pu.destino else tx["elige"]
        pagina = PAGINA_PC.format(**tx, dire=e(dire), pin=e(str(pu.cfg["pin"])), qr=qr, recientes=filas, raiz=e(pu.carpetas.raiz),
                                  llave_valor=e(pu.cfg["llave_atajo"]), subir=e(dire + "api/subir"), destino=e(destino),
                                  seguridad=tx["https" if self.server.https else "http"], seg_clase="ok" if self.server.https else "",
                                  version=VERSION)
        self.responder(200, pagina, "text/html; charset=utf-8", {"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:"})

    # ----- POST -----
    def do_POST(self):
        if not self.filtro():
            return
        # Un sitio ajeno no puede mandar este encabezado sin permiso del puente (y el puente nunca lo da).
        if self.headers.get("X-Puente") != "1":
            self.close_connection = True
            return self.error(403, self.t("pedido"))
        if self.path == "/api/entrar":
            return self.entrar()
        if self.path == "/api/salir":
            self.puente.cerrar_sesion(self.cookie("puente"))
            return self.responder(200, {"ok": True}, extra={"Set-Cookie": "puente=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict"})
        if self.path == "/api/subir" and self.headers.get("X-Llave"):
            # El atajo «Compartir → Puente» del iPhone: entra con su llave (no tiene la cookie de la página).
            estado, n = self.puente.probar_llave(self.ip(), self.headers["X-Llave"])
            if estado != "ok":
                self.close_connection = True
                if estado == "bloqueado":
                    return self.error(429, self.t("intentos", min=max(1, n // 60)))
                return self.error(401, self.t("llave-mala"))
            return self.subir(atajo=True)
        if not self.con_sesion():
            self.close_connection = True
            return self.error(401, self.t("falta-pin"))
        if self.path == "/api/subir":
            return self.subir()
        if self.path == "/api/destino":
            return self.cambiar_destino()
        if self.path == "/api/carpeta-nueva":
            return self.carpeta_nueva()
        self.close_connection = True
        self.error(404, self.t("no-existe"))

    def largo_cuerpo(self):
        try:
            return int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return -1

    def leer_json(self, maximo=1000):
        largo = self.largo_cuerpo()
        if not 0 < largo <= maximo:
            self.close_connection = True
            return None
        try:
            d = json.loads(self.rfile.read(largo))
            return d if isinstance(d, dict) else None
        except ValueError:
            return None

    def cambiar_destino(self):
        """La página del iPhone elige la carpeta: ahí llega lo que se mande (también lo del atajo)."""
        d = self.leer_json()
        if d is None:
            return self.error(400, self.t("pedido"))
        cs = self.puente.carpetas
        ruta = cs.ruta(d.get("carpeta"))
        if not ruta:
            return self.error(404, self.t("carpeta-mala"))
        rel = cs.relativa(ruta)
        if not rel:
            return self.error(400, self.t("raiz", raiz=os.path.basename(self.puente.carpetas.raiz) or self.puente.carpetas.raiz))
        self.puente.fijar_destino(rel)
        self.responder(200, {"ok": True, "destino": cs.info(rel), "recientes": [cs.info(r) for r in self.puente.recientes]})

    def carpeta_nueva(self):
        """Crea una carpeta dentro de otra (nunca fuera de la carpeta compartida; si ya existe, la usa)."""
        d = self.leer_json()
        if d is None:
            return self.error(400, self.t("pedido"))
        cs = self.puente.carpetas
        dentro = cs.ruta(d.get("dentro"))
        nombre = nombre_de_carpeta(d.get("nombre", ""))
        if not dentro:
            return self.error(404, self.t("carpeta-mala"))
        if not nombre or not cs.visible(nombre):
            return self.error(400, self.t("nombre-malo"))
        ruta = os.path.join(dentro, nombre)
        try:
            os.mkdir(ruta)
            self.puente.anotar(evento="carpeta-nueva", ip=self.ip(), carpeta=ruta)
        except FileExistsError:
            if not os.path.isdir(ruta):
                return self.error(409, self.t("ya-archivo"))
        except OSError:
            return self.error(500, self.t("no-creada"))
        self.responder(200, {"ok": True, **cs.info(cs.relativa(ruta))})

    def entrar(self):
        largo = self.largo_cuerpo()
        if not 0 < largo <= 200:
            self.close_connection = True
            return self.error(400, self.t("pedido"))
        try:
            pin = str(json.loads(self.rfile.read(largo)).get("pin", ""))
        except (ValueError, AttributeError):
            return self.error(400, self.t("pedido"))
        estado, n = self.puente.probar_pin(self.ip(), pin)
        if estado == "bloqueado":
            return self.error(429, self.t("intentos", min=max(1, n // 60)))
        if estado == "mal":
            return self.error(401, self.t("pin-malo", n=n))
        token = self.puente.nueva_sesion()
        dias = self.puente.cfg["sesion_dias"]
        self.puente.anotar(evento="entrada", ip=self.ip(), navegador=self.headers.get("User-Agent", "")[:120])
        segura = "; Secure" if self.server.https else ""
        self.responder(200, {"ok": True}, extra={"Set-Cookie": f"puente={token}; Max-Age={dias * 86400}; Path=/; HttpOnly; SameSite=Strict{segura}"})

    def subir(self, atajo=False):
        """Recibe UN archivo como cuerpo del pedido (así el iPhone muestra el avance de cada uno).
        Va a la carpeta del encabezado X-Carpeta o, si no viene (el atajo), a la elegida por última vez en la página."""
        cfg, pu = self.puente.cfg, self.puente
        rechazo = lambda codigo, msg, **ev: (pu.anotar(evento="rechazo", ip=self.ip(), motivo=msg, **ev),
                                             setattr(self, "close_connection", True), self.error(codigo, msg))
        if self.headers.get("Transfer-Encoding"):
            return rechazo(411, self.t("sin-tamano"))
        try:
            largo = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return rechazo(411, self.t("sin-tamano"))
        original = urllib.parse.unquote(self.headers.get("X-Nombre", ""))[:200]
        try:   # el atajo manda el nombre sin codificar: http.server lo lee como latin-1
            original = original.encode("latin-1").decode("utf-8")
        except UnicodeError:
            pass
        limite_video = cfg["limite_video_mb"] * 1048576
        if not 16 <= largo <= limite_video:
            return rechazo(413, self.t("limite", mb=cfg['limite_video_mb']), original=original, bytes=largo)
        pedida = urllib.parse.unquote(self.headers.get("X-Carpeta", ""))
        destino = pu.carpetas.ruta(pedida or pu.destino)
        rel = pu.carpetas.relativa(destino) if destino else ""
        if not destino or not rel:
            return rechazo(404, self.t("carpeta-otra"), original=original, pedida=pedida[:200])
        etiqueta = pu.carpetas.etiqueta(rel)
        lote = self.headers.get("X-Lote", "") or (secrets.token_hex(8) if atajo else "")
        if not RE_LOTE.match(lote):
            return rechazo(400, self.t("pedido"))
        libre = shutil.disk_usage(destino).free
        if libre - largo < cfg["espacio_minimo_mb"] * 1048576:
            return rechazo(507, self.t("disco"), original=original, bytes=largo)

        tmp = os.path.join(destino, f".subiendo-{secrets.token_hex(8)}.parcial")
        sha, tipo, cab, recibido, motivo = hashlib.sha256(), None, b"", 0, None
        try:
            with open(tmp, "wb") as f:
                while recibido < largo:
                    trozo = self.rfile.read(min(1 << 20, largo - recibido))
                    if not trozo:
                        raise ConnectionError("se cortó la subida")
                    if tipo is None:
                        cab += trozo
                        if len(cab) >= 16 or recibido + len(trozo) >= largo:
                            tipo = detectar(cab)
                            if tipo is None:
                                motivo = (415, self.t("tipo"), {"firma": cab[:12].hex()})
                                break
                            limite = (cfg["limite_video_mb"] if tipo in EXT_VIDEO else cfg["limite_imagen_mb"]) * 1048576
                            if largo > limite:
                                motivo = (413, self.t("limite-foto", mb=cfg['limite_imagen_mb']), {"bytes": largo})
                                break
                    sha.update(trozo)
                    f.write(trozo)
                    recibido += len(trozo)
            huella = sha.hexdigest()
            ya = None if motivo else pu.huellas.get((os.path.normcase(destino), huella))
            if motivo or (ya and os.path.exists(os.path.join(destino, ya))):
                os.remove(tmp)   # se borra antes de responder
                if motivo:
                    return rechazo(motivo[0], motivo[1], original=original, **motivo[2])
                pu.anotar(evento="repetida", ip=self.ip(), destino=rel, original=original, ya=ya)
                return self.responder(200, {"ok": True, "repetida": True, "guardado": ya, "ver": ver(rel, ya)})
            # Nombre por la hora en que se tomó (si el archivo la trae); si no, por la hora de la tanda.
            fecha = fecha_de_toma(tmp, tipo)
            if cfg.get("quitar_ubicacion", True):
                try:
                    quitar_ubicacion(tmp, tipo)
                except (OSError, ValueError, struct.error) as e:
                    pu.anotar(evento="ubicacion-sin-quitar", destino=rel, original=original, detalle=str(e)[:200])
            marca = fecha.strftime("%Y-%m-%d_%H%M%S") if fecha else pu.marca_de_lote(lote)
            prefijo = f"{marca}_{etiqueta}_"
            nombre = pu.reservar_nombre(destino, prefijo, tipo, tmp)
        except (ConnectionError, OSError, TimeoutError) as e:
            if os.path.exists(tmp):
                os.remove(tmp)
            pu.anotar(evento="error", ip=self.ip(), destino=rel, original=original, detalle=str(e)[:200])
            self.close_connection = True
            if not isinstance(e, ConnectionError):   # si el iPhone se desconectó, ya no hay a quién responder
                self.error(500, self.t("no-guardado"))
            return
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

        jpg, aviso = None, None
        if tipo == "heic" and cfg.get("convertir_heic", True):
            try:
                jpg = os.path.basename(convertir_heic(os.path.join(destino, nombre)))
            except Exception as e:
                aviso = self.t("heic")
                pu.anotar(evento="heic-sin-convertir", destino=rel, guardado=nombre, detalle=str(e)[:200])
        pu.huellas[(os.path.normcase(destino), huella)] = jpg or nombre
        pu.anotar(evento="subida", ip=self.ip(), destino=rel, etiqueta=etiqueta, original=original,
                  guardado=nombre, jpg=jpg, tipo=tipo, bytes=largo, sha256=huella, carpeta=destino,
                  tomada=fecha.isoformat() if fecha else None, via="atajo" if atajo else "pagina")
        avisar(f"  ✓ {rel} · {jpg or nombre} ({tamano(largo)})")
        self.responder(200, {"ok": True, "guardado": nombre, "jpg": jpg, "aviso": aviso, "ver": ver(rel, jpg or nombre),
                             "mensaje": self.t("en-pc", donde=rel.replace("/", " › "))})


def ver(rel, nombre):
    """Enlace de la miniatura (o None si es video y no hay ffmpeg para sacarle un cuadro)."""
    if nombre.rsplit(".", 1)[1] in EXT_VIDEO and not FFMPEG:
        return None
    return "/miniatura?" + urllib.parse.urlencode({"c": rel, "f": nombre})


PC_TEXTOS = {
    "es": {"lang": "es", "encendido": "encendido", "abre": "Ábrelo en el celular",
           "apunta": "Apunta la cámara del celular al código (mismo Wi-Fi que este computador).",
           "direccion": "Dirección", "pasos": "<li>Abre la dirección y escribe el PIN.</li><li>En el iPhone: Compartir → «Agregar a pantalla de inicio».</li>"
           "<li>En Windows, el puente vive en el ícono junto al reloj: clic derecho → «Apagar el puente».</li>",
           "compartida": "Carpeta compartida", "llega": "Lo que mandes llega a", "cambia": "Se cambia en el celular, tocando «Cambiar».",
           "atajo": "Atajo del iPhone (opcional)", "dir_atajo": "Dirección del atajo", "llave": "Llave del atajo (encabezado X-Llave)",
           "ultimas": "Últimas carpetas", "ninguna": "Ninguna todavía.", "elige": "(elige una carpeta en el celular)",
           "http": "Sin cifrar: úsalo solo en un Wi-Fi de confianza (ver SECURITY.md).", "https": "Conexión cifrada (HTTPS).",
           "sin_qr": "(Falta la librería qrcode: escribe la dirección a mano)"},
    "en": {"lang": "en", "encendido": "running", "abre": "Open it on your phone",
           "apunta": "Point your phone's camera at the code (same Wi-Fi as this computer).",
           "direccion": "Address", "pasos": "<li>Open the address and type the PIN.</li><li>On iPhone: Share → «Add to Home Screen».</li>"
           "<li>On Windows, Puente lives in the icon next to the clock: right click → «Stop Puente».</li>",
           "compartida": "Shared folder", "llega": "What you send goes to", "cambia": "Change it on your phone with «Change».",
           "atajo": "iPhone shortcut (optional)", "dir_atajo": "Shortcut address", "llave": "Shortcut key (X-Llave header)",
           "ultimas": "Recent folders", "ninguna": "None yet.", "elige": "(pick a folder on your phone)",
           "http": "Unencrypted: use it only on a trusted Wi-Fi (see SECURITY.md).", "https": "Encrypted connection (HTTPS).",
           "sin_qr": "(The qrcode library is missing: type the address by hand)"},
}

PAGINA_PC = """<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Puente by Typers</title><style>
:root{{--bg:#F4F5F7;--sf:#fff;--ink:#14171C;--ink2:#5B6472;--ac:#2563EB;--line:#DDE1E7;--aviso:#A15C07;color-scheme:light}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0E1116;--sf:#161B22;--ink:#E8ECF1;--ink2:#97A1AF;--ac:#6EA8FF;--line:#262D37;--aviso:#FBBF24;color-scheme:dark}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 'Segoe UI',system-ui,sans-serif}}
main{{max-width:880px;margin:0 auto;padding:32px 16px 8px;display:grid;gap:24px;grid-template-columns:minmax(0,1fr) minmax(0,1fr)}}
@media (max-width:700px){{main{{grid-template-columns:1fr}}}}
.card{{background:var(--sf);border:1px solid var(--line);border-radius:14px;padding:24px}}
h1{{margin:0 0 4px;font-size:28px}} .k{{font:600 12px/1.4 Consolas,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ac)}}
.dir{{font:600 24px Consolas,monospace;word-break:break-all}} .pin{{font:700 44px Consolas,monospace;letter-spacing:.2em}}
.qr{{background:#fff;border-radius:12px;padding:12px;display:grid;place-items:center}} .qr svg{{width:100%;max-width:340px;height:auto}}
.mini{{margin:12px 0 0;font-size:13px;color:var(--ink2)}} .dato{{margin:2px 0 0;font:600 18px Consolas,monospace;word-break:break-all}}
.seg{{font-size:14px;color:var(--aviso)}} .seg.ok{{color:var(--ink2)}}
ol,ul{{padding-left:20px}} li{{margin:4px 0}} code{{font-size:13px;color:var(--ink2);word-break:break-all}}
footer{{max-width:880px;margin:0 auto;padding:8px 16px 32px;font-size:13px;color:var(--ink2)}}
</style></head><body><main>
<div class="card"><span class="k">Puente by Typers · {encendido}</span><h1>{abre}</h1>
<p>{apunta}</p><div class="qr">{qr}</div><p class="seg {seg_clase}">{seguridad}</p></div>
<div class="card"><span class="k">{direccion}</span><p class="dir">{dire}</p><span class="k">PIN</span><p class="pin">{pin}</p>
<ol>{pasos}</ol>
<span class="k">{compartida}</span><p><code>{raiz}</code><br>{llega} <code>{destino}</code>. {cambia}</p>
<span class="k">{ultimas}</span><ul>{recientes}</ul>
<details><summary class="k">{atajo}</summary>
<p class="mini">{dir_atajo}</p><p class="dato">{subir}</p>
<p class="mini">{llave}</p><p class="dato">{llave_valor}</p></details></div>
</main><footer>Puente by Typers {version} · MIT · typersagency.com</footer></body></html>"""


class Servidor(http.server.ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16
    allow_reuse_address = False   # en Windows, «reuse» deja compartir el puerto con otro programa

    def handle_error(self, request, client_address):
        # Un celular que se desconecta (o un navegador que no acepta el certificado) no es un error del puente.
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError, ssl.SSLError)):
            return
        super().handle_error(request, client_address)

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def puerto_ocupado(puerto):
    """¿Otro programa ya atiende ese puerto en este PC? (Windows deja abrir 0.0.0.0 aunque 127.0.0.1 esté tomado)."""
    if not puerto:
        return False
    try:
        with socket.create_connection(("127.0.0.1", puerto), timeout=0.5):
            return True
    except OSError:
        return False


def crear_servidor(cfg, puerto=None, escuchar=None):
    puerto = cfg["puerto"] if puerto is None else puerto
    if puerto_ocupado(puerto):
        raise OSError(f"otro programa ya usa el puerto {puerto}")
    srv = Servidor((escuchar or cfg["escuchar"], puerto), Manejador)
    srv.puente = Puente(cfg)
    https = cfg.get("https") or {}
    srv.https = bool(https.get("cert"))
    if srv.https:
        # Con un certificado de confianza (ver SECURITY.md): el PIN y las fotos viajan cifrados por el Wi-Fi.
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(https["cert"], https["key"])
        # El saludo TLS se hace en el hilo de cada conexión, no en el que acepta (uno lento no frena a los demás).
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True, do_handshake_on_connect=False)
    ip = https.get("nombre") or cfg.get("ip") or ip_de_la_red()
    srv.direccion = f"{'https' if srv.https else 'http'}://{ip}:{srv.server_address[1]}/"
    return srv


def main():
    if "--version" in sys.argv:
        print(f"Puente by Typers {VERSION}")
        return
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    cfg = cargar_config()
    try:
        srv = crear_servidor(cfg)
    except OSError as e:
        raise SystemExit(f"No se pudo abrir el puerto {cfg['puerto']} ({e}). ¿Ya hay otro puente abierto? Si es otro programa, cambia «puerto» en config.local.json. / "
                         f"Could not open port {cfg['puerto']}: is another Puente running? If it is another program, change «puerto» in config.local.json.")
    print(f"\n  PUENTE BY TYPERS {VERSION} · encendido / running\n")
    print(f"  En el celular (mismo Wi-Fi) abre / On your phone (same Wi-Fi) open:  {srv.direccion}")
    print(f"  PIN: {cfg['pin']}")
    print(f"  Carpeta compartida / Shared folder: {cfg['carpetas']['raiz']}")
    print(f"  Llave del atajo / Shortcut key: {cfg['llave_atajo']}\n")
    try:
        import qrcode
        qr = qrcode.QRCode(border=2)
        qr.add_data(srv.direccion)
        qr.print_ascii(out=sys.stdout, invert=True)
    except Exception:
        pass
    print("\n  Deja esta ventana abierta mientras subes; para apagar, ciérrala o Ctrl+C. / Keep this window open; Ctrl+C to stop.")
    print(f"  Miniaturas de video / Video thumbnails: {'ffmpeg ✓' if FFMPEG else '— (ffmpeg no encontrado / not found)'}")
    if not srv.https:
        print("  Sin cifrar (http): úsalo solo en un Wi-Fi de confianza. / Unencrypted (http): use only on a trusted Wi-Fi. → SECURITY.md")
    print()
    if not {"--sin-navegador", "--no-browser"} & set(sys.argv):
        import webbrowser
        webbrowser.open(f"{'https' if srv.https else 'http'}://127.0.0.1:{srv.server_address[1]}/pc")
    srv.puente.anotar(evento="encendido", direccion=srv.direccion)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("  Puente apagado. / Stopped.")
    finally:
        srv.puente.anotar(evento="apagado")


if __name__ == "__main__":
    main()
