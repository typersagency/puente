# Atajo del iPhone: Compartir → Puente

[English](shortcut-iphone.md)

Con este atajo mandas fotos y videos al computador desde el botón **Compartir** de cualquier app (Fotos, WhatsApp, Archivos), sin abrir la página del Puente. Llegan a la carpeta que tengas elegida en la página.

Se arma una sola vez en la app **Atajos**, que ya viene en el iPhone, y toma unos 5 minutos.

## Antes de empezar

En el computador, abre la pantalla del Puente (clic en el ícono junto al reloj, o la página que se abre al encenderlo). Despliega **«Atajo del iPhone»** y deja a la vista la **dirección del atajo** y la **llave del atajo**.

## Pasos

1. Abre **Atajos** → pestaña **Atajos** → **+**. Toca el nombre de arriba y ponle **Puente**.
2. Toca **ⓘ** y activa **Mostrar en hoja de compartir**. En «Recibir … de Hoja de compartir», deja solo **Imágenes** y **Multimedia**.
3. Agrega **Repetir con cada elemento**. Debe decir «de **Entrada del atajo**».
4. Dentro del repetir, agrega **Obtener contenido de URL**:
   - **URL:** la dirección del atajo, por ejemplo `http://192.168.1.20:8850/api/subir`.
   - Toca **›** y pon **Método: POST**.
   - **Encabezados:**
     - `X-Puente` = `1`
     - `X-Llave` = tu llave
     - `X-Nombre` = **Elemento repetido** → **Nombre**
   - **Cuerpo de la solicitud:** **Archivo** → **Elemento repetido**.
5. Debajo de **Fin de repetir**, agrega **Mostrar notificación** con el texto «Listo, enviado al computador».
6. Prueba: en Fotos elige unas fotos → **Compartir** → **Puente**. La primera vez el iPhone pregunta si dejas que Atajos se conecte: toca **Permitir siempre**.

## Si pierdes el celular

Borra `llave_atajo` de `config.local.json` y reinicia el Puente. Se crea una llave nueva, la vieja deja de servir y se cierra la sesión en todos los celulares.

## Tip: abrir la Fototeca de un toque

Una página web no puede abrir la Fototeca sin que el iPhone muestre antes su menú. Un atajo sí puede. Haz otro atajo igual, pero que empiece con la acción **Seleccionar fotos** (activa «Seleccionar varios») en lugar de recibir de la hoja de compartir. Luego agrégalo a la pantalla de inicio desde su menú.
