// Puente by Typers · página del celular (MIT).
// Sube los archivos de a uno (así se ve el avance de cada uno) al servidor del computador.
'use strict';
const $ = id => document.getElementById(id);

// ---------- Idioma: español si el celular está en español; si no, inglés ----------
const IDIOMA = /^es\b/i.test(navigator.language || '') ? 'es' : 'en';
const TX = {
  es: {
    lema: 'Del celular a tu computador por el Wi-Fi de la casa. Sin cables ni nube.', entrar: 'Entrar',
    pinDonde: 'El PIN aparece en la pantalla del computador.', conectado: 'Conectado al computador',
    tip1: 'Tenlo como app: toca', compartir: 'Compartir', agregarInicio: 'Agregar a pantalla de inicio', listo: 'Listo',
    galeria: 'Galería', camara: 'Cámara', vanA: 'Van a', cambiar: 'Cambiar', elegirCarpeta: 'Elegir carpeta', dondeEstas: 'Dónde estás',
    sinCarpetas: 'No hay más carpetas aquí.', nombreNueva: 'Nombre de la carpeta nueva', crear: 'Crear', nuevaCarpeta: '+ Nueva carpeta',
    guardarAqui: 'Guardar aquí', entraACarpeta: 'Entra a una carpeta',
    notaNombres: 'Se guardan con la hora en que se tomó cada foto, sin ubicación GPS. Lo que mandes con el atajo del iPhone también llega aquí.',
    loUltimo: 'Lo último', loUltimoEn: 'Lo último en {x}', nadaAun: 'Todavía no hay nada enviado a esta carpeta.', salir: 'Salir en este celular',
    eligeCarpeta: 'elige una carpeta', primeroElige: 'Primero elige dónde guardar.',
    respuestaRara: 'Respuesta rara del computador.', noEncuentro: 'No encuentro el computador. ¿Está encendido el Puente y estás en el mismo Wi-Fi?',
    soloFotos: 'Solo fotos y videos.', pesa: 'Pesa {x}: pasa del límite.', enEspera: 'En espera', reintentar: 'Reintentar',
    subiendo: 'Enviando {p} % · {a} de {b}', enviando: 'Enviando {n} de {t}… No bloquees el celular ni cierres esta página.',
    listoN: 'Listo: {n} en el computador', conProblema: ' · {n} con problema', sesion: 'Se cerró la sesión: vuelve a entrar con el PIN.',
    noAcepto: 'El computador no lo aceptó.', yaEstaba: 'Ya estaba: {x}', listoArchivo: 'Listo · {x}',
    cortado: 'Se cortó la conexión con el computador (o no aceptó el archivo).', archivo: 'archivo',
  },
  en: {
    lema: 'From your phone to your computer over your home Wi-Fi. No cables, no cloud.', entrar: 'Enter',
    pinDonde: 'The PIN is shown on the computer screen.', conectado: 'Connected to your computer',
    tip1: 'Use it like an app: tap', compartir: 'Share', agregarInicio: 'Add to Home Screen', listo: 'Got it',
    galeria: 'Gallery', camara: 'Camera', vanA: 'Saving to', cambiar: 'Change', elegirCarpeta: 'Choose a folder', dondeEstas: 'You are here',
    sinCarpetas: 'No more folders here.', nombreNueva: 'New folder name', crear: 'Create', nuevaCarpeta: '+ New folder',
    guardarAqui: 'Save here', entraACarpeta: 'Open a folder first',
    notaNombres: 'Files are named by the time each photo was taken, without GPS location. What you send with the iPhone shortcut lands here too.',
    loUltimo: 'Latest', loUltimoEn: 'Latest in {x}', nadaAun: 'Nothing sent to this folder yet.', salir: 'Sign out on this phone',
    eligeCarpeta: 'choose a folder', primeroElige: 'First choose where to save.',
    respuestaRara: 'Unexpected answer from the computer.', noEncuentro: "Can't reach the computer. Is Puente running and are you on the same Wi-Fi?",
    soloFotos: 'Photos and videos only.', pesa: '{x}: over the limit.', enEspera: 'Waiting', reintentar: 'Retry',
    subiendo: 'Sending {p} % · {a} of {b}', enviando: 'Sending {n} of {t}… Keep your phone unlocked and this page open.',
    listoN: 'Done: {n} on the computer', conProblema: ' · {n} with problems', sesion: 'Session ended: enter the PIN again.',
    noAcepto: 'The computer did not accept it.', yaEstaba: 'Already there: {x}', listoArchivo: 'Done · {x}',
    cortado: 'Lost the connection to the computer (or it did not accept the file).', archivo: 'file',
  },
};
const t = (clave, datos = {}) => (TX[IDIOMA][clave] || TX.es[clave] || clave).replace(/\{(\w+)\}/g, (_, k) => datos[k] ?? '');
document.documentElement.lang = IDIOMA;
for (const el of document.querySelectorAll('[data-t]')) el.textContent = t(el.dataset.t);
for (const el of document.querySelectorAll('[data-t-ph]')) el.placeholder = t(el.dataset.tPh);
for (const el of document.querySelectorAll('[data-t-aria]')) el.setAttribute('aria-label', t(el.dataset.tAria));

const CABECERA = { 'X-Puente': '1', 'X-Idioma': IDIOMA };   // el servidor rechaza pedidos sin X-Puente (protege de sitios ajenos)
const guardar = (k, v) => { try { localStorage.setItem('puente-' + k, v); } catch (e) {} };
const leer = k => { try { return localStorage.getItem('puente-' + k); } catch (e) { return null; } };
const mb = n => (n / 1048576).toFixed(1).replace('.', IDIOMA === 'es' ? ',' : '.') + ' MB';

let limites = { imagen: 80, video: 4096 }, miniVideo = false;
let destino = null, recientes = [];   // destino: la carpeta elegida (ahí llega todo, también lo del atajo)
let aqui = '';                        // la carpeta que se está mirando en el explorador
const cola = [];          // { file, li, estado: 'espera'|'subiendo'|'ok'|'mal', lote }
let subiendo = false;

function ver(vista) { $('vEntrar').hidden = vista !== 'entrar'; $('vSubir').hidden = vista !== 'subir'; }

async function api(ruta, opciones = {}) {
  const r = await fetch(ruta, { credentials: 'same-origin', ...opciones, headers: { ...CABECERA, ...(opciones.headers || {}) } });
  const d = await r.json().catch(() => ({ ok: false, error: t('respuestaRara') }));
  if (r.status === 401 && ruta !== '/api/entrar') { ver('entrar'); throw new Error(d.error); }
  return d;
}

// ---------- Entrar ----------
$('fPin').addEventListener('submit', async e => {
  e.preventDefault();
  $('pinMsg').textContent = '';
  try {
    const d = await api('/api/entrar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pin: $('pin').value }) });
    if (!d.ok) { $('pinMsg').textContent = d.error; $('pin').select(); return; }
    $('pin').value = '';
    await iniciar();
  } catch (err) { $('pinMsg').textContent = t('noEncuentro'); }
});
$('salir').addEventListener('click', async () => { await api('/api/salir', { method: 'POST' }).catch(() => {}); ver('entrar'); });

// ---------- Carpeta de destino ----------
async function iniciar() {
  const d = await api('/api/inicio');
  if (d.limites) limites = d.limites;
  miniVideo = !!d.miniaturas_video;
  ver('subir');
  ponerDestino(d.destino, d.recientes);
  if (!destino) abrirExplorador('');   // la primera vez: que elija dónde guardar
}

function esc(s) { return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]); }
const camino = info => info.partes.slice(-3).join(' › ');
// En la ficha: el proyecto y, debajo, lo que va después («bitacora › imagenes») o, si es la última, la carpeta de arriba.
const sub = r => r.posicion < r.partes.length - 1 ? r.partes.slice(r.posicion + 1).join(' › ') : r.partes.slice(-2, -1).join('');

function ponerDestino(info, lista) {
  destino = info || null;
  if (lista) recientes = lista;
  $('destinoTxt').textContent = destino ? camino(destino) : t('eligeCarpeta');
  $('ultimoTit').textContent = destino ? t('loUltimoEn', { x: destino.nombre }) : t('loUltimo');
  // Las de siempre, a un toque (la elegida va marcada)
  $('rapidas').innerHTML = recientes.map((r, i) =>
    `<button type="button" class="rapida${destino && r.carpeta === destino.carpeta ? ' activa' : ''}" data-i="${i}" title="${esc(r.partes.join(' › '))}">` +
    `${esc(r.nombre)}${sub(r) ? `<small>${esc(sub(r))}</small>` : ''}</button>`).join('');
  $('rapidas').hidden = recientes.length < 2;
  pintarRecientes();
}

$('rapidas').addEventListener('click', e => {
  const b = e.target.closest('.rapida');
  if (b && !b.classList.contains('activa')) elegirCarpeta(recientes[+b.dataset.i].carpeta);
});

async function elegirCarpeta(rel) {
  try {
    const d = await api('/api/destino', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ carpeta: rel }) });
    if (!d.ok) { $('explMsg').textContent = d.error; return; }
    ponerDestino(d.destino, d.recientes);
    cerrarExplorador();
  } catch (e) { /* sin sesión: ya se mostró el PIN */ }
}

// Explorador: las carpetas de la carpeta compartida, entrando y saliendo como en el computador.
async function abrirExplorador(rel) {
  $('destinoCaja').hidden = false;
  $('destinoBtn').setAttribute('aria-expanded', 'true');
  $('explMsg').textContent = '';
  $('fNueva').hidden = true;
  let d;
  try { d = await api('/api/carpetas?c=' + encodeURIComponent(rel)); } catch (e) { return; }
  if (!d.ok) { if (rel) return abrirExplorador(''); $('explMsg').textContent = d.error; return; }
  aqui = d.carpeta;
  const migas = [`<button type="button" data-c="">${esc(d.raiz)}</button>`];
  d.partes.forEach((x, i) => migas.push(`<span aria-hidden="true">›</span><button type="button" data-c="${esc(d.partes.slice(0, i + 1).join('/'))}">${esc(x)}</button>`));
  $('migas').innerHTML = migas.join('');
  $('carpetas').innerHTML = d.carpetas.map(n =>
    `<li><button type="button" data-c="${esc((aqui ? aqui + '/' : '') + n)}"><span class="ico-carpeta" aria-hidden="true"></span>${esc(n)}<span class="flecha" aria-hidden="true">›</span></button></li>`).join('');
  $('carpetasVacio').hidden = d.carpetas.length > 0;
  $('guardarAqui').disabled = !aqui;
  $('guardarAqui').textContent = aqui ? t('guardarAqui') : t('entraACarpeta');
}
function cerrarExplorador() {
  $('destinoCaja').hidden = true;
  $('destinoBtn').setAttribute('aria-expanded', 'false');
}
$('destinoBtn').addEventListener('click', () => {
  if ($('destinoCaja').hidden) abrirExplorador(destino ? destino.carpeta : ''); else cerrarExplorador();
});
for (const id of ['migas', 'carpetas']) $(id).addEventListener('click', e => {
  const b = e.target.closest('button[data-c]');
  if (b) abrirExplorador(b.dataset.c);
});
$('guardarAqui').addEventListener('click', () => { if (aqui) elegirCarpeta(aqui); });
$('nuevaBtn').addEventListener('click', () => { $('fNueva').hidden = false; $('nuevaNombre').focus(); });
$('fNueva').addEventListener('submit', async e => {
  e.preventDefault();
  const nombre = $('nuevaNombre').value.trim();
  if (!nombre) return;
  try {
    const d = await api('/api/carpeta-nueva', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ dentro: aqui, nombre }) });
    if (!d.ok) { $('explMsg').textContent = d.error; return; }
    $('nuevaNombre').value = '';
    abrirExplorador(d.carpeta);
  } catch (err) { /* sin sesión */ }
});

async function pintarRecientes() {
  if (!destino) { $('recientes').innerHTML = ''; $('recientesVacio').hidden = true; return; }
  const c = destino.carpeta;
  try {
    const d = await api('/api/recientes?c=' + encodeURIComponent(c));
    const lista = d.archivos || [];
    $('recientesVacio').hidden = lista.length > 0;
    const mini = a => `<img loading="lazy" alt="${esc(a.nombre)}" src="/miniatura?c=${encodeURIComponent(c)}&f=${encodeURIComponent(a.nombre)}">`;
    $('recientes').innerHTML = lista.map(a => a.video
      ? (d.miniaturas_video ? `<li class="con-video" title="${esc(a.nombre)}">${mini(a)}<b class="play" aria-hidden="true">▶</b></li>`
                            : `<li title="${esc(a.nombre)}"><span class="vid"><b>▶</b>${esc(a.nombre.slice(18))}</span></li>`)
      : `<li title="${esc(a.nombre)}">${mini(a)}</li>`).join('');
  } catch (e) { /* sin sesión: ya se mostró el PIN */ }
}

// ---------- Elegir y subir ----------
// Galería (varias, se van solas al elegirlas) y Cámara (la foto o el video que tomes).
for (const id of ['galeria', 'camara']) $(id).addEventListener('change', () => elegidos($(id)));

function elegidos(entrada) {
  const archivos = Array.from(entrada.files || []);
  entrada.value = '';
  if (!archivos.length) return;
  if (!destino) { abrirExplorador(''); $('explMsg').textContent = t('primeroElige'); return; }
  // Tanda nueva: lo ya enviado sale de la lista (queda en «Lo último»).
  if (!cola.some(it => it.estado === 'espera' || it.estado === 'subiendo')) {
    for (const it of cola.splice(0)) if (it.estado === 'ok') it.li.remove(); else cola.push(it);
  }
  cerrarExplorador();
  const lote = Array.from(crypto.getRandomValues(new Uint8Array(8)), b => b.toString(16).padStart(2, '0')).join('');
  for (const file of archivos) cola.push(nuevoItem(file, lote, destino.carpeta));
  resumen();
  siguiente();
}

function nuevoItem(file, lote, carpeta) {
  const li = document.createElement('li');
  li.className = 'item';
  li.innerHTML = `<div class="pre" aria-hidden="true">${/^video/.test(file.type) ? '▶' : '🖼'}</div>
    <div><div class="nom"></div><div class="barra"><i></i></div><div class="est">${t('enEspera')}</div></div><div class="acc"></div>`;
  li.querySelector('.nom').textContent = file.name || t('archivo');
  $('cola').prepend(li);
  const it = { file, li, lote, carpeta, estado: 'espera' };
  vistaPrevia(it);
  // Revisión antes de enviar (el PC vuelve a revisar todo; esto solo ahorra tiempo y datos).
  const esVideo = /^video\//.test(file.type) || /\.(mov|mp4|m4v)$/i.test(file.name);
  const esImagen = /^image\//.test(file.type) || /\.(jpe?g|png|gif|webp|heic|heif)$/i.test(file.name);
  if (!(esVideo || esImagen)) marcar(it, 'mal', t('soloFotos'));
  else if (file.size > (esVideo ? limites.video : limites.imagen) * 1048576) marcar(it, 'mal', t('pesa', { x: mb(file.size) }));
  return it;
}

function vistaPrevia(it) {
  const caja = it.li.querySelector('.pre');
  const url = URL.createObjectURL(it.file);
  if (/^video\//.test(it.file.type)) {
    const v = document.createElement('video');
    v.muted = true; v.playsInline = true; v.preload = 'metadata'; v.src = url;
    v.addEventListener('loadeddata', () => { try { v.currentTime = Math.min(0.1, v.duration || 0); } catch (e) {} }, { once: true });
    v.addEventListener('seeked', () => {
      const c = document.createElement('canvas'); c.width = 112; c.height = 112;
      const s = Math.min(v.videoWidth, v.videoHeight);
      try { c.getContext('2d').drawImage(v, (v.videoWidth - s) / 2, (v.videoHeight - s) / 2, s, s, 0, 0, 112, 112); caja.replaceChildren(c); } catch (e) {}
      URL.revokeObjectURL(url);
    }, { once: true });
    v.addEventListener('error', () => URL.revokeObjectURL(url), { once: true });
  } else {
    const img = new Image();
    img.alt = '';
    img.onload = () => { caja.replaceChildren(img); URL.revokeObjectURL(url); };
    img.onerror = () => URL.revokeObjectURL(url);
    img.src = url;
  }
}

function marcar(it, estado, texto, pct) {
  it.estado = estado === 'aviso' ? 'ok' : estado;
  it.pct = estado === 'subiendo' ? (pct || 0) : 0;
  it.li.className = 'item ' + estado;
  it.li.querySelector('.est').textContent = texto;
  if (pct !== undefined) it.li.querySelector('.barra i').style.width = pct + '%';
  else if (estado === 'ok' || estado === 'aviso') it.li.querySelector('.barra i').style.width = '100%';
  const acc = it.li.querySelector('.acc');
  acc.replaceChildren();
  if (estado === 'mal' && it.reintentable) {
    const b = document.createElement('button');
    b.type = 'button'; b.textContent = t('reintentar');
    b.onclick = () => { it.estado = 'espera'; marcar(it, 'espera', t('enEspera'), 0); resumen(); siguiente(); };
    acc.append(b);
  }
}

function resumen() {
  const n = c => cola.filter(it => it.estado === c).length;
  const ok = n('ok'), mal = n('mal'), falta = n('espera') + n('subiendo');
  const avance = cola.reduce((a, it) => a + (it.estado === 'ok' || it.estado === 'mal' ? 100 : it.pct || 0), 0);
  $('progreso').hidden = !cola.length;
  $('progreso').classList.toggle('listo', !falta);
  $('progresoBarra').style.width = (cola.length ? avance / cola.length : 0) + '%';
  $('resumen').textContent = !cola.length ? '' : falta
    ? t('enviando', { n: Math.min(ok + mal + 1, cola.length), t: cola.length })
    : t('listoN', { n: ok }) + (mal ? t('conProblema', { n: mal }) : '') + '.';
}

function siguiente() {
  if (subiendo) return;
  const it = cola.find(x => x.estado === 'espera');
  if (!it) { resumen(); pintarRecientes(); return; }
  subiendo = true;
  it.estado = 'subiendo';
  marcar(it, 'subiendo', t('subiendo', { p: 0, a: mb(0), b: mb(it.file.size) }), 0);
  const x = new XMLHttpRequest();
  x.open('POST', '/api/subir');
  for (const [k, v] of Object.entries(CABECERA)) x.setRequestHeader(k, v);
  x.setRequestHeader('X-Carpeta', encodeURIComponent(it.carpeta));
  x.setRequestHeader('X-Lote', it.lote);
  x.setRequestHeader('X-Nombre', encodeURIComponent(it.file.name || ''));
  x.setRequestHeader('Content-Type', 'application/octet-stream');
  x.upload.onprogress = e => {
    if (!e.lengthComputable) return;
    const pct = Math.round(100 * e.loaded / e.total);
    marcar(it, 'subiendo', t('subiendo', { p: pct, a: mb(e.loaded), b: mb(e.total) }), pct);
    resumen();
  };
  const fin = () => { subiendo = false; resumen(); siguiente(); };
  x.onload = () => {
    let d = {};
    try { d = JSON.parse(x.responseText); } catch (e) {}
    if (x.status === 401) { it.reintentable = true; marcar(it, 'mal', t('sesion')); ver('entrar'); subiendo = false; resumen(); return; }
    if (!d.ok) { it.reintentable = x.status >= 500; marcar(it, 'mal', d.error || t('noAcepto')); return fin(); }
    if (d.ver) { const img = new Image(); img.alt = ''; img.onload = () => it.li.querySelector('.pre').replaceChildren(img); img.src = d.ver; }
    const nombre = d.jpg || d.guardado;
    if (d.repetida) marcar(it, 'aviso', t('yaEstaba', { x: nombre }));
    else if (d.aviso) marcar(it, 'aviso', d.aviso + ' ' + d.guardado);
    else marcar(it, 'ok', t('listoArchivo', { x: nombre }));
    fin();
  };
  x.onerror = () => { it.reintentable = true; marcar(it, 'mal', t('cortado')); fin(); };
  x.ontimeout = x.onerror;
  x.send(it.file);
}

window.addEventListener('beforeunload', e => { if (subiendo) { e.preventDefault(); e.returnValue = ''; } });

// ---------- Tenerlo como app ----------
// Si se abrió en el navegador (no desde el ícono), recuerda cómo ponerlo en la pantalla de inicio.
const comoApp = navigator.standalone || matchMedia('(display-mode: standalone)').matches;
if (!comoApp && !leer('tip-inicio')) $('tipInicio').hidden = false;
$('tipCerrar').addEventListener('click', () => { $('tipInicio').hidden = true; guardar('tip-inicio', '1'); });

// ---------- Arranque ----------
(async () => {
  try {
    const d = await api('/api/estado');
    if (d.sesion) await iniciar(); else ver('entrar');
  } catch (e) { ver('entrar'); $('pinMsg').textContent = t('noEncuentro'); }
})();
