# Notro

<p align="center">
  <img src="docs/icon.png" width="96" alt="Icono de Notro">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows-blue.svg" alt="Platform: Windows">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT">
</p>

<p align="center"><a href="README.md">English</a> | <a href="README.ko.md">한국어</a> | <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <b>Español</b></p>

Una pequeña aplicación de bandeja para Windows para los usuarios gratuitos de Discord. **Comprime automáticamente las imágenes del portapapeles** que superan el límite de subida gratuito de Discord (10 MB) e incluye un **selector de emojis, stickers y GIF** (ventana emergente con atajo) que cubre lo que bloquea Nitro, **sin modificar el cliente de Discord**. Solo pega con <kbd>Ctrl</kbd>+<kbd>V</kbd>.

## Cómo funciona (compresión automática)

1. Reside en la bandeja del sistema y vigila el portapapeles.
2. Cuando se copia una imagen nueva, calcula el **tamaño del PNG que Discord generaría** al pegar.
3. **Si es 10 MB o menos, no hace nada** (pega el original como siempre).
4. Si supera el límite, recodifica a **WebP → JPEG** bajando la calidad hasta quedar por debajo de ~9,5 MB; si sigue siendo demasiado grande, **reduce la resolución** paso a paso.
5. La imagen comprimida se coloca en el portapapeles **como archivo**, de modo que <kbd>Ctrl</kbd>+<kbd>V</kbd> en Discord la sube como archivo adjunto. Una notificación en la bandeja confirma el resultado.

> Nunca se tocan los archivos de captura originales del disco: solo se reemplaza el portapapeles.

## El selector (v2.0)

Pulsa <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>E</kbd> (configurable desde la bandeja) mientras escribes en Discord: se abre una ventana emergente oscura al estilo de Discord cerca del cursor con tres pestañas: **Emojis / Stickers / GIF**.

- **Añadir elementos:** pulsa **＋** y pega una URL de emoji de *«Copiar enlace»* de Discord, o arrastra y suelta archivos de imagen en el selector, o añade **carpetas vigiladas** (⚙) cuyos archivos PNG/GIF/WebP/APNG aparecen automáticamente en la pestaña actual.
- **Usar elementos:** haz clic en uno: el selector se oculta, el foco vuelve a Discord y la imagen se pega en el cuadro de mensaje como adjunto. **Tú pulsas Enter para enviar.** Clic derecho para «pegar como enlace» (elementos CDN) o eliminar.
- Los stickers APNG animados se convierten a GIF al registrarlos, porque Discord no anima los APNG subidos.
- Busca por nombre o palabras clave; una fila de «Usados recientemente» mantiene cerca los habituales.
- Elementos que superan el límite: las imágenes estáticas se comprimen automáticamente; los GIF demasiado grandes se envían tal cual con una advertencia.

**Diseño respetuoso con los ToS:** Notro nunca parchea el cliente de Discord ni toca tu cuenta o token (nada de comportamiento de self-bot). Solo prepara el portapapeles y simula un <kbd>Ctrl</kbd>+<kbd>V</kbd> local, el mismo tipo de automatización de entrada que el panel de emojis de Windows (<kbd>Win</kbd>+<kbd>.</kbd>). El compromiso honesto: los destinatarios ven tus emojis/stickers como imágenes adjuntas o enlaces incrustados, no como emojis nativos en línea.

Requiere el **entorno de ejecución WebView2** (incluido en Windows 11). Sin él, el selector se desactiva y la compresión sigue funcionando.

## Descargar y ejecutar (recomendado)

Obtén el `NotroSetup.exe` más reciente desde la página de [**Releases**](../../releases) y ejecútalo. Se instala en `%LOCALAPPDATA%\Programs\Notro` (sin permisos de administrador) y añade accesos directos al menú Inicio y al escritorio. Desinstálalo cuando quieras desde **Configuración → Aplicaciones** o el menú Inicio.

- Se ejecuta en la bandeja. Haz clic derecho en el icono para: abrir el selector, cambiar su atajo, pausar/reanudar, ver el historial reciente, cambiar el límite de subida (10/50/500 MB), cambiar el idioma, abrir la carpeta de salida, activar el inicio automático y salir.
- **El inicio automático es opcional** y está *desactivado por defecto*. Actívalo con *«Ejecutar al iniciar Windows»* desde el menú de la bandeja si lo deseas.
- Solo se ejecuta una instancia a la vez.

> ⚠️ El EXE **no está firmado**, por lo que Windows SmartScreen o algunos antivirus pueden advertir o marcarlo como falso positivo. Haz clic en *«Más información → Ejecutar de todas formas»* en SmartScreen, o ejecútalo desde el código fuente (abajo).

## Primer arranque: ¿dónde está?

Notro **no tiene ventana principal**. Tras instalarlo se inicia en silencio y reside en la
**bandeja del sistema** (abajo a la derecha, junto al reloj).

> **Windows 11 oculta los iconos nuevos de la bandeja de forma predeterminada.** Si no ves
> Notro, haz clic en la flecha **`^`** junto al reloj y **arrastra el icono de Notro a la
> barra de tareas** para mantenerlo visible.

A partir de ahí:

- Pulsa <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>E</kbd> en cualquier lugar para abrir el selector.
- Copia una imagen demasiado grande para Discord: Notro la comprime automáticamente; solo
  tienes que pegar con <kbd>Ctrl</kbd>+<kbd>V</kbd>.
- **Haz clic derecho en el icono de la bandeja** para todos los ajustes (atajo, límite de
  subida, idioma…).

En el primer arranque aparece una **ventana de bienvenida** que explica todo esto y muestra
una imagen del icono de la bandeja que debes buscar. Al cerrarla, Notro sigue en la bandeja.

## Ejecutar desde el código fuente (desarrollo)

```sh
pip install -r requirements.txt
pythonw notro.py
```

Requiere **Python 3.10 o superior** en Windows.

## Compilar el EXE tú mismo

```sh
build.bat
```

Salida: `dist\Notro.exe`. Requiere Python 3.10+ (el script instala PyInstaller).

## Configuración

Edita los valores en `notro_app/config.py` (límites) y `notro_app/compress.py` (pasos de calidad):

| Ajuste | Predeterminado | Descripción |
|---|---|---|
| `LIMIT_MB` | 10 | Límite de subida predeterminado en MB — o elige 10/50/500 en el menú **Límite de subida** de la bandeja |
| `SAFETY` | 0.95 | Margen de seguridad (apunta a ~9,5 MB) |
| `WEBP_QUALITIES` | 90–50 | Pasos de calidad de WebP |
| `MIN_SCALE` | 0.4 | Límite inferior de reducción |

## Notas

- Los archivos comprimidos se escriben en `%TEMP%\Notro` y se eliminan automáticamente tras 1 día.
- Copiar un **archivo** de imagen (<kbd>Ctrl</kbd>+<kbd>C</kbd>) mayor que el límite se comprime de la misma forma.
- **Idiomas:** English, 한국어, 日本語, 中文(简体), Español. Notro detecta automáticamente el idioma de Windows y se puede cambiar en cualquier momento desde el menú **Idioma** de la bandeja.

## Desarrollo

```sh
pip install -r requirements-dev.txt
pytest
```

## Licencia

[MIT](LICENSE).

> Notro es una herramienta no oficial, **sin afiliación, respaldo ni patrocinio de Discord Inc.** «Discord» es una marca registrada de Discord Inc.
