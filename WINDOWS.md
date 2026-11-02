# Escuela de Tenis para uso personal en PC y móvil

## Qué hace el ejecutable

`EscuelaTenis.exe` es un lanzador nativo para **Windows 10/11 de 64 bits (x64)**. No necesitas instalar Python ni Go para utilizarlo. Al abrirlo, inicia tu aplicación privada en el navegador predeterminado. No instala un navegador propio.

El PC y el móvil usan **el mismo servidor y la misma cuenta personal**. Así mantienen los datos compartidos. El ejecutable necesita conexión y alojamiento; no incluye un servidor en la nube, no crea una suscripción y no funciona como una copia independiente sin conexión.

El control de acceso lo proporciona tu cuenta y contraseña. El archivo no es una licencia ligada físicamente a tu identidad: alguien puede copiarlo, pero no podrá entrar en tus datos sin tus credenciales. No compartas la contraseña, la clave inicial ni tu cuenta de Windows. No contiene contraseñas ni la base de datos del club.

## Primer paso: dirección privada compartida

1. Crea una cuenta en Render y conecta este repositorio de GitHub.
2. Selecciona **New → Blueprint**, rama `main`. Revisa el servicio y su coste: usa un disco persistente de pago. No necesitas comprar un dominio.
3. `render.yaml` activa el modo personal (`TENNIS_PRIVATE=1`), cookies HTTPS (`TENNIS_SECURE_COOKIE=1`), una base nueva en `/var/data/tennis-private.sqlite3` y una clave inicial generada por Render (`TENNIS_SETUP_TOKEN`). No introduzcas esa clave en GitHub ni en este chat.
4. Cuando Render muestre la dirección HTTPS del servicio, ábrela. En los ajustes de variables del servicio, consulta la clave `TENNIS_SETUP_TOKEN` y úsala en la pantalla **Crea tu cuenta privada**. Introduce tu nombre, correo y una contraseña personal de al menos 12 caracteres. Estos datos se introducen en la aplicación; no debes enviarlos por chat.
5. La primera cuenta es la única cuenta de gestor del modo personal. Una vez creada, el alta inicial queda cerrada. No funcionan las cuentas públicas de demostración ni los accesos de familias, incluso si creas fichas de tutores. Guarda tu contraseña en un gestor de contraseñas: esta versión no ofrece recuperación por correo.

El modo privado comienza sin alumnos ficticios y **no importa automáticamente** los datos del entorno local. Si ya existe una base de demostración, se conserva en su ubicación anterior. El servidor rechaza utilizar una base con las cuentas públicas de demostración en modo privado. Revisa una migración y configura copias de seguridad antes de guardar datos reales.

## Abrirlo en Windows

1. Descarga `downloads/EscuelaTenis-Windows.zip` desde tu repositorio y extrae todos los archivos.
2. Abre `EscuelaTenis.exe` con doble clic.
3. La primera vez aparece un asistente: pega la dirección **HTTPS del servicio de Render** y pulsa **Guardar y abrir mi aplicación**. No pegues una dirección de GitHub, del panel de Render ni una contraseña.
4. Entra con la cuenta personal que creaste. Las siguientes veces el .exe abrirá directamente esa dirección.

Solo se guarda la dirección en `%APPDATA%\EscuelaTenis\launcher.json`. Para cambiarla, mantén pulsada **Ctrl** al abrir el ejecutable o ejecútalo con `--configurar`. El asistente local escucha únicamente en el propio PC y se cierra al guardar o a los diez minutos. Los alumnos, grupos y pagos permanecen en el servidor compartido.

El ejecutable no está firmado con un certificado comercial; Windows puede mostrar un aviso de editor desconocido. Comprueba la procedencia y el SHA-256 del archivo con `downloads/SHA256SUMS.txt`. No desactives las protecciones de Windows.

## En el móvil

Abre la misma dirección HTTPS en Safari o Chrome e inicia sesión con tu cuenta personal. Puedes usar **Añadir a pantalla de inicio** desde el navegador. Un teléfono no ejecuta archivos `.exe`.

Los cambios aceptados por el servidor aparecen en el otro dispositivo aproximadamente cada cinco segundos. Un formulario abierto conserva lo que estás escribiendo y recibe la actualización al cerrarlo. Para cambiar tu contraseña, entra en **Configuración → Cambiar mi contraseña**; esto cierra tus otras sesiones, incluido el móvil.

## Compilar y comprobar

El código del lanzador está en `launcher/`, sin dependencias externas. Se puede compilar en Linux, macOS o Windows con el compilador oficial Go 1.24+ y Python 3.11+ para empaquetar:

```sh
go test ./launcher
python tools/build_windows.py
```

`GO_BIN` permite indicar otra ruta al compilador. Se genera `dist/EscuelaTenis.exe` y el ZIP descargable con sus sumas SHA-256. El archivo `GO-LICENSE.txt` del ZIP corresponde al runtime de Go.

En Windows, `EscuelaTenis.exe --self-test` comprueba la lectura, escritura y sustitución de la configuración sin abrir el navegador ni conectar con servicios externos. La compilación cruzada en Linux genera un PE de Windows, pero no equivale a ejecutarlo en Windows; el workflow `Windows executable` ejecuta esa comprobación en un runner Windows.
