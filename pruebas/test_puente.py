# Pruebas de Puente by Typers: python -m unittest discover -s pruebas -v
# Levantan un puente de verdad en 127.0.0.1 con un proyecto de mentira en una carpeta temporal.
import http.client
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import puente  # noqa: E402

from PIL import Image  # noqa: E402


def jpg_bytes(color=(200, 30, 30)):
    b = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(b, "JPEG")
    return b.getvalue()


def heic_bytes():
    import pillow_heif
    pillow_heif.register_heif_opener()
    b = io.BytesIO()
    Image.new("RGB", (64, 48), (20, 120, 220)).save(b, format="HEIF")
    return b.getvalue()


MOV = b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00qt  " + b"\x00" * 200


def jpg_con_gps(tomada="2025:03:04 05:06:07"):
    """Foto como las del iPhone: con fecha de toma y ubicación GPS en el EXIF."""
    exif = Image.Exif()
    exif.get_ifd(0x8769)[36867] = tomada
    exif.get_ifd(0x8825).update({1: "N", 2: (4.0, 21.0, 3.96), 3: "W", 4: (74.0, 22.0, 44.76)})
    b = io.BytesIO()
    Image.new("RGB", (64, 48), (90, 160, 60)).save(b, "JPEG", exif=exif.tobytes())
    return b.getvalue()


def mov_con_gps():
    """Video como los del iPhone: fecha y ubicación dentro del bloque «moov»."""
    datos = (b"keys com.apple.quicktime.location.ISO6709 com.apple.quicktime.creationdate "
             b"data+04.3511-074.3791+1496.537/data2025-03-04T05:06:07-0500")
    moov = (8 + len(datos)).to_bytes(4, "big") + b"moov" + datos
    mdat = b"\x00\x00\x00\x10mdat" + b"\x00" * 8
    return MOV[:20] + mdat + moov


def png_con_gps():
    exif = Image.Exif()
    exif.get_ifd(0x8825).update({1: "N", 2: (4.0, 21.0, 3.96), 3: "W", 4: (74.0, 22.0, 44.76)})
    b = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 100, 50)).save(b, "PNG", exif=exif.tobytes())
    return b.getvalue()


def jpg_con_xmp_gps():
    """JPG con el GPS repetido en un bloque XMP (como lo dejan algunos editores)."""
    xmp = (b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
           b'<rdf:Description xmlns:exif="http://ns.adobe.com/exif/1.0/" exif:GPSLatitude="4,21.066N" exif:GPSLongitude="74,22.746W">'
           b'<exif:GPSAltitude>1496/1</exif:GPSAltitude></rdf:Description></rdf:RDF></x:xmpmeta>')
    carga = b"http://ns.adobe.com/xap/1.0/\x00" + xmp
    base = jpg_bytes()
    return base[:2] + b"\xff\xe1" + (len(carga) + 2).to_bytes(2, "big") + carga + base[2:]


class PruebasSueltas(unittest.TestCase):
    def test_limpiar_parte(self):
        self.assertEqual(puente.limpiar_parte("M.11"), "M.11")
        self.assertEqual(puente.limpiar_parte("../../Windows"), "Windows")
        self.assertEqual(puente.limpiar_parte("Pintura ÁGUILA/222"), "Pintura-AGUILA-222")
        self.assertEqual(puente.limpiar_parte(".."), "")
        self.assertNotIn("\\", puente.limpiar_parte("a\\b:c"))

    def test_detectar(self):
        self.assertEqual(puente.detectar(jpg_bytes()), "jpg")
        self.assertEqual(puente.detectar(heic_bytes()), "heic")
        self.assertEqual(puente.detectar(MOV), "mov")
        self.assertEqual(puente.detectar(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20), "mp4")
        self.assertIsNone(puente.detectar(b"MZ\x90\x00" + b"\x00" * 20))   # un .exe
        self.assertIsNone(puente.detectar(b"<html><script>alert(1)</script>"))

    def test_quita_gps_de_la_foto_sin_tocar_la_imagen(self):
        ruta = os.path.join(tempfile.mkdtemp(prefix="puente-"), "f.jpg")
        with open(ruta, "wb") as f:
            f.write(jpg_con_gps())
        with Image.open(ruta) as im:
            pixeles = im.tobytes()
        tam = os.path.getsize(ruta)
        self.assertTrue(puente.quitar_ubicacion(ruta, "jpg"))
        self.assertEqual(os.path.getsize(ruta), tam)   # mismo tamaño: no se recomprime nada
        with Image.open(ruta) as im:
            self.assertEqual(im.tobytes(), pixeles)
            self.assertFalse(dict(im.getexif().get_ifd(0x8825)))
        self.assertEqual(puente.fecha_de_toma(ruta, "jpg").isoformat(), "2025-03-04T05:06:07")
        shutil.rmtree(os.path.dirname(ruta), ignore_errors=True)

    def test_quita_gps_del_video_y_lee_su_fecha(self):
        ruta = os.path.join(tempfile.mkdtemp(prefix="puente-"), "v.mov")
        with open(ruta, "wb") as f:
            f.write(mov_con_gps())
        self.assertEqual(puente.fecha_de_toma(ruta, "mov").isoformat(), "2025-03-04T05:06:07")
        self.assertTrue(puente.quitar_ubicacion(ruta, "mov"))
        with open(ruta, "rb") as f:
            datos = f.read()
        self.assertNotIn(b"074.3791", datos)
        self.assertEqual(len(datos), len(mov_con_gps()))
        shutil.rmtree(os.path.dirname(ruta), ignore_errors=True)

    def test_quita_gps_de_png_y_xmp(self):
        tmp = tempfile.mkdtemp(prefix="puente-")
        try:
            png = os.path.join(tmp, "f.png")
            with open(png, "wb") as f:
                f.write(png_con_gps())
            self.assertTrue(puente.quitar_ubicacion(png, "png"))
            with Image.open(png) as im:
                im.load()   # las sumas de control del PNG siguen buenas
                self.assertFalse(dict(im.getexif().get_ifd(0x8825)))
            jpg = os.path.join(tmp, "x.jpg")
            with open(jpg, "wb") as f:
                f.write(jpg_con_xmp_gps())
            self.assertTrue(puente.quitar_ubicacion(jpg, "jpg"))
            with open(jpg, "rb") as f:
                datos = f.read()
            for dato in (b"4,21.066N", b"74,22.746W", b"1496/1"):
                self.assertNotIn(dato, datos)
            with Image.open(jpg) as im:
                im.load()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_carpeta_por_defecto_nunca_es_toda_la_casa(self):
        casa = os.path.normcase(os.path.realpath(os.path.expanduser("~")))
        self.assertNotEqual(os.path.normcase(os.path.realpath(puente.carpeta_por_defecto())), casa)

    def test_ip_permitida(self):
        for ip in ("192.168.1.20", "10.0.0.5", "172.16.3.4", "127.0.0.1", "::1", "::ffff:192.168.1.8"):
            self.assertTrue(puente.ip_permitida(ip), ip)
        for ip in ("8.8.8.8", "181.50.3.2", "0.0.0.0", "basura"):
            self.assertFalse(puente.ip_permitida(ip), ip)


class PruebasServidor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="puente-")
        raiz = os.path.join(self.tmp, "Proyectos")
        for c in ("Uno/bitacora/imagenes", "Dos", ".git", "node_modules", "Viejo"):
            os.makedirs(os.path.join(raiz, c))
        conf = os.path.join(self.tmp, "conf")
        os.makedirs(conf)
        with io.open(os.path.join(conf, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"puerto": 0, "escuchar": "127.0.0.1", "limite_imagen_mb": 1, "limite_video_mb": 2,
                       "espacio_minimo_mb": 0, "sesion_dias": 1, "convertir_heic": True,
                       "carpetas": {"raiz": raiz, "ocultar": ["Viejo"], "inicial": "Uno/bitacora/imagenes"}}, f)
        with io.open(os.path.join(conf, "config.local.json"), "w", encoding="utf-8") as f:
            json.dump({"pin": "246810", "carpetas": {"raiz": raiz}}, f)   # solo «raiz»: lo demás de «carpetas» sale de config.json
        self.destino = os.path.join(raiz, "Uno", "bitacora", "imagenes")
        self.raiz = raiz
        self.srv = puente.crear_servidor(puente.cargar_config(conf))
        self.puerto = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.cookie = None

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def pedir(self, metodo, ruta, cuerpo=None, cab=None):
        c = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        h = {"X-Puente": "1", **(cab or {})}
        if self.cookie:
            h["Cookie"] = self.cookie
        c.request(metodo, ruta, body=cuerpo, headers=h)
        r = c.getresponse()
        datos = r.read()
        galleta = r.getheader("Set-Cookie")
        if galleta:
            self.cookie = galleta.split(";")[0]
        c.close()
        try:
            return r.status, json.loads(datos)
        except ValueError:
            return r.status, datos

    def entrar(self):
        s, d = self.pedir("POST", "/api/entrar", json.dumps({"pin": "246810"}))
        self.assertEqual(s, 200, d)

    def subir(self, cuerpo, carpeta="Uno/bitacora/imagenes", lote="abcdef0123456789", nombre="IMG_0001.HEIC"):
        return self.pedir("POST", "/api/subir", cuerpo, {"X-Carpeta": carpeta, "X-Lote": lote, "X-Nombre": nombre})

    def mandar_json(self, ruta, datos):
        return self.pedir("POST", ruta, json.dumps(datos), {"Content-Type": "application/json"})

    def test_sin_pin_no_deja_nada(self):
        self.assertEqual(self.pedir("GET", "/api/inicio")[0], 401)
        self.assertEqual(self.pedir("GET", "/api/carpetas")[0], 401)
        self.assertEqual(self.subir(jpg_bytes())[0], 401)
        self.assertFalse(os.path.exists(self.destino) and os.listdir(self.destino))

    def test_pin_equivocado_bloquea(self):
        for _ in range(4):
            self.assertEqual(self.pedir("POST", "/api/entrar", json.dumps({"pin": "000000"}))[0], 401)
        self.assertEqual(self.pedir("POST", "/api/entrar", json.dumps({"pin": "000000"}))[0], 429)
        # Bloqueado: ni con el PIN bueno entra
        self.assertEqual(self.pedir("POST", "/api/entrar", json.dumps({"pin": "246810"}))[0], 429)

    def test_sin_encabezado_x_puente(self):
        c = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        c.request("POST", "/api/entrar", body=json.dumps({"pin": "246810"}), headers={"Content-Type": "application/json"})
        self.assertEqual(c.getresponse().status, 403)

    def test_host_raro_rechazado(self):
        self.assertEqual(self.pedir("GET", "/api/estado", cab={"Host": "malo.example.com"})[0], 421)

    def test_carpetas_solo_dentro_de_proyectos(self):
        self.entrar()
        s, d = self.pedir("GET", "/api/carpetas?c=")
        self.assertEqual(d["carpetas"], ["Dos", "Uno"])   # sin .git, node_modules ni las de «ocultar»
        s, d = self.pedir("GET", "/api/carpetas?c=Uno")
        self.assertEqual((d["carpetas"], d["partes"]), (["bitacora"], ["Uno"]))
        for mala in ("..", "../conf", "Uno/../..", ".git", "Viejo", "node_modules", "C:/Windows", "Uno/no-existe"):
            self.assertEqual(self.pedir("GET", "/api/carpetas?c=" + mala)[0], 404, mala)
        s, d = self.pedir("GET", "/api/inicio")
        self.assertEqual(d["destino"]["carpeta"], "Uno/bitacora/imagenes")
        self.assertEqual(d["destino"]["etiqueta"], "Uno")   # salta «bitacora» e «imagenes»

    def test_sube_jpg_heic_y_video_con_nombres_ordenados(self):
        self.entrar()
        s, d = self.subir(jpg_bytes())
        self.assertEqual(s, 200, d)
        self.assertRegex(d["guardado"], r"^\d{4}-\d\d-\d\d_\d{6}_Uno_01\.jpg$")
        s, d = self.subir(heic_bytes())
        self.assertTrue(d["guardado"].endswith("_02.heic"), d)
        self.assertEqual(d["jpg"], d["guardado"][:-5] + ".jpg")
        s, d = self.subir(MOV, nombre="IMG_0003.MOV")
        self.assertTrue(d["guardado"].endswith("_03.mov"), d)
        archivos = sorted(os.listdir(self.destino))
        self.assertEqual(len(archivos), 4, archivos)   # jpg, heic + su jpg, mov
        with Image.open(os.path.join(self.destino, d["guardado"][:-6] + "02.jpg")) as im:
            self.assertEqual(im.format, "JPEG")
        # Registro
        with io.open(os.path.join(self.srv.puente.datos, "registro", "subidas.log"), encoding="utf-8") as f:
            subidas = [json.loads(l) for l in f if '"subida"' in l]
        self.assertEqual(len(subidas), 3)
        # Recientes y miniatura
        s, d = self.pedir("GET", "/api/recientes?c=Uno/bitacora/imagenes")
        self.assertEqual(len(d["archivos"]), 3)   # el HEIC no se repite junto a su JPG
        foto = next(a["nombre"] for a in d["archivos"] if not a["video"])
        s, img = self.pedir("GET", "/miniatura?c=Uno/bitacora/imagenes&f=" + foto)
        self.assertEqual(s, 200)

    def test_repetida_no_se_guarda_dos_veces(self):
        self.entrar()
        foto = jpg_bytes((1, 2, 3))
        self.subir(foto)
        s, d = self.subir(foto, lote="1111111111111111")
        self.assertTrue(d.get("repetida"), d)
        self.assertEqual(len(os.listdir(self.destino)), 1, os.listdir(self.destino))

    def test_rechaza_lo_que_no_es_foto_ni_video(self):
        self.entrar()
        s, d = self.subir(b"MZ\x90\x00" + b"\x00" * 500, nombre="foto.jpg")
        self.assertEqual(s, 415)
        self.assertEqual([n for n in os.listdir(self.destino) if not n.startswith(".")], [])
        self.assertEqual(os.listdir(self.destino), [])   # ni el temporal queda

    def test_limite_de_tamano(self):
        self.entrar()
        grande = jpg_bytes()[:3] + b"\x00" * (1024 * 1024 + 10)   # pasa de 1 MB (límite de fotos en esta prueba)
        self.assertEqual(self.subir(grande)[0], 413)

    def test_salir_cierra_la_sesion_de_verdad(self):
        self.entrar()
        galleta = self.cookie
        self.assertEqual(self.pedir("POST", "/api/salir")[0], 200)
        self.cookie = galleta   # aunque alguien guarde la cookie vieja, ya no sirve
        self.assertEqual(self.pedir("GET", "/api/inicio")[0], 401)

    def test_cambiar_pin_cierra_todas_las_sesiones(self):
        self.entrar()
        conf = os.path.join(self.tmp, "conf")
        with io.open(os.path.join(conf, "config.local.json"), encoding="utf-8") as f:
            local = json.load(f)
        local["pin"] = "97531086"
        with io.open(os.path.join(conf, "config.local.json"), "w", encoding="utf-8") as f:
            json.dump(local, f)
        nuevo = puente.Puente(puente.cargar_config(conf))   # como si se reiniciara el puente
        self.assertFalse(nuevo.sesion_valida(self.cookie.split("=", 1)[1]))

    def test_freno_para_toda_la_red(self):
        pu = self.srv.puente
        for i in range(puente.FALLOS_RED):
            pu.probar_pin(f"192.168.1.{i + 2}", "000000")
        self.assertEqual(pu.probar_pin("192.168.1.250", "246810")[0], "bloqueado")

    def test_largo_raro(self):
        c = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        c.putrequest("POST", "/api/entrar")
        c.putheader("X-Puente", "1")
        c.putheader("Content-Length", "abc")
        c.endheaders()
        self.assertEqual(c.getresponse().status, 400)

    def test_mezcla_de_configuracion_por_clave(self):
        cfg = self.srv.puente.cfg
        self.assertEqual(cfg["carpetas"]["ocultar"], ["Viejo"])   # vino de config.json aunque local también traiga «carpetas»

    @unittest.skipUnless(os.name == "nt", "nombres y atributos de Windows")
    def test_trucos_de_nombres_de_windows(self):
        self.entrar()
        for mala in ("Viejo.", "Viejo%20", "node_modules.", "NODE_M~1", "VIEJO~1"):
            self.assertEqual(self.pedir("GET", "/api/carpetas?c=" + mala)[0], 404, mala)
        oculta = os.path.join(self.raiz, "Oculta")
        os.makedirs(oculta)
        import subprocess
        subprocess.run(["attrib", "+h", oculta], check=True, capture_output=True)
        self.assertEqual(self.pedir("GET", "/api/carpetas?c=Oculta")[0], 404)
        s, d = self.pedir("GET", "/api/carpetas?c=")
        self.assertNotIn("Oculta", d["carpetas"])

    def test_carpeta_fuera_o_escondida(self):
        self.entrar()
        for mala in ("..%2F..%2Fconf", "..", ".git", "Viejo", "Uno%2F..%2F..", "C%3A%2FWindows"):
            self.assertEqual(self.subir(jpg_bytes(), carpeta=mala)[0], 404, mala)
        self.assertEqual(os.listdir(self.destino), [])

    def test_miniatura_no_sale_de_la_carpeta(self):
        self.entrar()
        self.assertEqual(self.pedir("GET", "/miniatura?c=Uno/bitacora/imagenes&f=..%2F..%2F..%2F..%2Fconf%2Fconfig.local.json")[0], 404)
        self.assertEqual(self.pedir("GET", "/miniatura?c=..%2Fconf&f=config.local.json")[0], 404)

    def test_nombre_por_fecha_de_toma_y_sin_gps(self):
        self.entrar()
        s, d = self.subir(jpg_con_gps(), nombre="IMG_5587.jpeg")
        self.assertEqual(d["guardado"], "2025-03-04_050607_Uno_01.jpg", d)
        with Image.open(os.path.join(self.destino, d["guardado"])) as im:
            self.assertFalse(dict(im.getexif().get_ifd(0x8825)))
        s, d = self.subir(mov_con_gps(), nombre="IMG_5590.MOV")
        self.assertEqual(d["guardado"], "2025-03-04_050607_Uno_02.mov", d)   # mismo segundo: 02

    def test_atajo_con_llave(self):
        llave = self.srv.puente.cfg["llave_atajo"]
        atajo = lambda cuerpo, k: self.pedir("POST", "/api/subir", cuerpo, {"X-Llave": k, "X-Nombre": "IMG_1.JPG"})
        self.assertEqual(atajo(jpg_bytes(), "AAAA-BBBB-CCCC-DDDD-EEEE")[0], 401)
        self.assertEqual(os.listdir(self.destino) if os.path.exists(self.destino) else [], [])
        # Llega a la carpeta elegida (aquí: la inicial de la configuración)
        s, d = atajo(jpg_bytes(), llave.lower().replace("-", " "))
        self.assertEqual(s, 200, d)
        self.assertIn("_Uno_01.jpg", d["guardado"])
        # La página elige otra carpeta: el atajo ya manda ahí, y queda en las recientes
        self.entrar()
        s, d = self.mandar_json("/api/destino", {"carpeta": "Dos"})
        self.assertEqual(s, 200, d)
        self.assertEqual([r["carpeta"] for r in d["recientes"]], ["Dos", "Uno/bitacora/imagenes"])
        self.assertEqual(self.mandar_json("/api/destino", {"carpeta": "../conf"})[0], 404)
        self.assertEqual(self.mandar_json("/api/destino", {"carpeta": ""})[0], 400)   # la raíz no
        self.cookie = None
        s, d = atajo(jpg_bytes((5, 5, 5)), llave)
        self.assertTrue(os.path.exists(os.path.join(self.raiz, "Dos", d["guardado"])), d)
        self.assertEqual(d["mensaje"], "On the computer: Dos")   # sin idioma pedido: inglés

    def test_llave_equivocada_bloquea(self):
        for _ in range(4):
            self.assertEqual(self.pedir("POST", "/api/subir", jpg_bytes(), {"X-Llave": "MALA"})[0], 401)
        self.assertEqual(self.pedir("POST", "/api/subir", jpg_bytes(), {"X-Llave": "MALA"})[0], 429)
        self.assertEqual(self.pedir("POST", "/api/subir", jpg_bytes(), {"X-Llave": self.srv.puente.cfg["llave_atajo"]})[0], 429)

    def test_carpeta_nueva(self):
        self.entrar()
        s, d = self.mandar_json("/api/carpeta-nueva", {"dentro": "Uno", "nombre": "Pruebas impresora"})
        self.assertEqual((s, d["carpeta"]), (200, "Uno/Pruebas impresora"))
        self.assertTrue(os.path.isdir(os.path.join(self.raiz, "Uno", "Pruebas impresora")))
        s, d = self.mandar_json("/api/carpeta-nueva", {"dentro": "Uno", "nombre": "../../afuera"})
        self.assertEqual(d["carpeta"], "Uno/afuera")   # las barras se quitan: nunca sale de donde está
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "afuera")))
        self.assertEqual(self.mandar_json("/api/carpeta-nueva", {"dentro": "Uno", "nombre": "CON"})[0], 400)
        self.assertEqual(self.mandar_json("/api/carpeta-nueva", {"dentro": "..", "nombre": "x"})[0], 404)

    def test_responde_en_el_idioma_del_celular(self):
        s, d = self.pedir("GET", "/api/inicio", cab={"Accept-Language": "es-CO,es;q=0.9"})
        self.assertEqual(d["error"], "Falta el PIN.")
        s, d = self.pedir("GET", "/api/inicio", cab={"Accept-Language": "en-US"})
        self.assertEqual(d["error"], "PIN required.")
        s, d = self.pedir("GET", "/api/inicio", cab={"Accept-Language": "en-US", "X-Idioma": "es"})   # la página manda
        self.assertEqual(d["error"], "Falta el PIN.")
        s, html = self.pedir("GET", "/pc", cab={"Accept-Language": "es"})
        self.assertIn("Ábrelo en el celular".encode(), html)

    def test_pantalla_pc_solo_local(self):
        s, html = self.pedir("GET", "/pc")
        self.assertEqual(s, 200)
        self.assertIn(b"246810", html)


class PruebasConfiguracion(unittest.TestCase):
    def test_carpeta_por_defecto_existe(self):
        self.assertTrue(os.path.isdir(puente.carpeta_por_defecto()))

    @unittest.skipUnless(shutil.which("openssl"), "falta openssl para crear un certificado de prueba")
    def test_https_con_certificado_propio(self):
        import ssl
        import subprocess
        tmp = tempfile.mkdtemp(prefix="puente-")
        try:
            cert, key = os.path.join(tmp, "c.pem"), os.path.join(tmp, "k.pem")
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=localhost",
                            "-keyout", key, "-out", cert], check=True, capture_output=True)
            os.makedirs(os.path.join(tmp, "raiz", "Fotos"))
            with io.open(os.path.join(tmp, "config.json"), "w", encoding="utf-8") as f:
                json.dump({"puerto": 0, "escuchar": "127.0.0.1", "limite_imagen_mb": 1, "limite_video_mb": 2, "espacio_minimo_mb": 0,
                           "sesion_dias": 1, "carpetas": {"raiz": os.path.join(tmp, "raiz")},
                           "https": {"cert": cert, "key": key, "nombre": "localhost"}}, f)
            srv = puente.crear_servidor(puente.cargar_config(tmp))
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                self.assertTrue(srv.direccion.startswith("https://localhost:"))
                ctx = ssl.create_default_context()   # se prueba el cifrado y la cookie, no la cadena de confianza
                ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
                c = http.client.HTTPSConnection("localhost", srv.server_address[1], context=ctx, timeout=10)
                c.request("POST", "/api/entrar", body=json.dumps({"pin": srv.puente.cfg["pin"]}),
                          headers={"X-Puente": "1", "Content-Type": "application/json"})
                r = c.getresponse()
                self.assertEqual(r.status, 200)
                self.assertIn("Secure", r.getheader("Set-Cookie"))
                c.close()
            finally:
                srv.shutdown()
                srv.server_close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
