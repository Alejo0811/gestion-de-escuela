# Usarla desde móvil y ordenador

Ambos dispositivos deben abrir la **misma dirección web**. La aplicación guarda los cambios en una única base de datos del servidor. No hay que instalar otra copia en cada dispositivo ni sincronizar archivos con GitHub. Cada persona entra con su cuenta y ve los datos que le corresponden.

## Opción sencilla: Render con disco persistente

`render.yaml` describe un servicio web Python con un disco persistente. La modalidad con disco requiere un plan de pago; consulta el precio vigente antes de confirmar. No uses una instancia gratuita con almacenamiento efímero para guardar alumnos o pagos: puede perder su base de datos al reiniciar o desplegar.

1. Crea una cuenta en **https://render.com** y vincúlala con GitHub.
2. En el panel, elige **New → Blueprint** y selecciona `Alejo0811/gestion-de-escuela`, rama `main`, una vez que esta configuración esté subida a esa rama.
3. Revisa el servicio, el disco y su coste antes de crearlos. El fichero configura:
   - Runtime: Python.
   - Build: `python -m compileall -q server.py`.
   - Start: `python server.py --host 0.0.0.0 --port $PORT`.
   - Variable `TENNIS_DB`: `/var/data/tennis-private.sqlite3`.
   - Disco montado en `/var/data`.
4. Render asigna una dirección HTTPS. Abre **esa misma dirección** en el móvil y en el PC e inicia sesión. No necesitas comprar un dominio para empezar.
5. La configuración activa el modo privado. Abre la dirección y crea tu única cuenta personal con la clave inicial `TENNIS_SETUP_TOKEN`, disponible en las variables del servicio en Render. No compartas esa clave por chat ni la guardes en GitHub. Elige tu contraseña en el formulario y usa esa misma cuenta en PC y móvil. Consulta [WINDOWS.md](WINDOWS.md) para el proceso detallado.
6. Comprueba con datos de prueba que un cambio guardado desde un dispositivo aparece en el otro en unos cinco segundos. Al volver a una pestaña, la aplicación vuelve a consultar el servidor.

No se ha creado ningún servicio ni contratado ningún plan desde este repositorio. Render y el dominio público son distintos de la publicación del entorno de desarrollo de Codex.

## Datos y continuidad

El primer arranque privado prepara una base vacía y espera la creación de tu cuenta personal. No subimos la base de datos local a GitHub y el despliegue no importa automáticamente los datos del entorno de desarrollo. La base privada usa `/var/data/tennis-private.sqlite3` para conservar separada una base de demostración anterior. Debes preparar una migración y copias de seguridad antes de usar información real. Para SQLite, mantén **una sola instancia del servicio** y su disco persistente; no configures varias réplicas independientes ni varios discos con copias diferentes.

La actualización automática funciona mientras hay conexión y la pestaña está visible. Si se pierde la conexión se muestra un aviso. Los cambios requieren que el servidor confirme el guardado; no se guardan operaciones sin conexión para enviarlas después. Si una petición de guardado pierde la respuesta, actualiza y comprueba el resultado antes de repetirla.

Un formulario abierto no se sustituye al recibir cambios de otro dispositivo. Se indica que hay cambios disponibles y se consulta de nuevo al cerrarlo. Las ediciones del mismo registro siguen el orden de los guardados aceptados por el servidor; no hay combinación automática de campos. El servidor mantiene las validaciones de plazas y horarios para cada guardado.

## Antes de introducir datos reales

Esta configuración utiliza `TENNIS_PRIVATE=1` y `TENNIS_SECURE_COOKIE=1`: una sola cuenta personal, cookies HTTPS, límite de intentos y accesos de demostración bloqueados. Comprueba estas opciones si ya tienes un servicio anterior, pues subir un Blueprint no actualiza por sí solo un servicio creado manualmente. No existe recuperación de contraseña por correo; guarda tu contraseña en un gestor. Prepara copias de seguridad, revisa el despliegue y no expongas el fichero SQLite como archivo descargable ni lo guardes en el repositorio.
