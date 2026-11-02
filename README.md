# Escuela de tenis

Aplicación autónoma en español para gestionar una escuela y ofrecer un espacio a sus alumnos y familias. Python 3.11+ y SQLite; no requiere instalar paquetes ni servicios externos. Interfaz adaptable a móvil y escritorio.

Móvil y ordenador consultan los mismos datos si abren la misma dirección del servidor. Las pantallas se actualizan automáticamente aproximadamente cada cinco segundos, al recuperar conexión y al volver a la pestaña. Los formularios abiertos se conservan hasta cerrarlos. El indicador superior muestra el estado de actualización y permite consultar de nuevo manualmente.

Para obtener una dirección compartida fuera de la red local, consulta [DEPLOY.md](DEPLOY.md). Incluye la configuración de Render con disco persistente en `render.yaml`; guardar o subir estos archivos no crea un alojamiento ni despliega la aplicación.

## Ejecutar

Desde la raíz del repositorio:

```sh
python3 server.py --host 0.0.0.0 --port 8000
```

El primer inicio crea `data/tennis.sqlite3` con datos ficticios. Los siguientes conservan los cambios. `TENNIS_DB` permite indicar otra ruta de base de datos. No crear un worktree: cada tarea en la nube ya está aislada y puede utilizar este checkout.

Accesos de demostración (también hay botones en la pantalla de entrada):

| Perfil | Correo | Contraseña local de demostración |
| --- | --- | --- |
| Gestor | gestor@demo.local | TenisDemo2026! |
| Familia García | familia@demo.local | TenisDemo2026! |

La cuenta familiar permite cambiar entre Lucas y Sofía. El gestor puede crear otras cuentas de clientes/tutores y vincularlas a los alumnos, como tutor o como acceso propio para un adulto.

## Funciones

- Grupos recurrentes semanales con temporada, entrenador, pista, nivel, edades, tarifa, capacidad y coste mensual. Crear, editar, duplicar sin alumnos, cerrar y consultar historial.
- Ocupación visual: completo, casi completo (desde el 80 %) y baja ocupación (hasta el 50 %). Filtros por nombre, nivel, edad, entrenador, día, hora, ocupación y tarifa.
- Matrículas, bajas y traslados atómicos. Se comprueban capacidad, nivel, edad y conflictos del alumno. Un traslado fallido conserva la matrícula de origen.
- Comprobación de solapamientos de pista, entrenador y alumnos al modificar grupos. Fechas de temporada, días comunes y horas se consideran; sesiones consecutivas no se solapan.
- Solicitudes de alta, cambio y baja siempre pendientes de gestor. Una solicitud dirigida a un grupo completo se muestra en lista de espera y se aprueba manualmente cuando haya plaza. No hay adjudicación automática ni reserva de plaza por solicitud.
- Registro de asistencia por sesión celebrada. Ausencias generan una recuperación que el gestor puede programar en una sesión posterior del mismo grupo y marcar como realizada.
- Panel familiar con grupo, entrenador, pista, días, horario, nivel, cuota, próximas sesiones, asistencia, recuperaciones y recibos. La API restringe los datos personales a los alumnos vinculados.
- Ingresos estimados, coste imputable y margen mensual por grupo, más punto de equilibrio. El coste es una imputación manual mensual.
- Generación mensual de recibos sin duplicados y registro manual de cobros. El cambio de tarifa no altera recibos existentes. Las bajas conservan el historial y los recibos.

## Validación

```sh
python3 -m unittest discover -s tests -v
node --check web/app.js
node --check web/sync.js
```

Las pruebas HTTP usan bases SQLite temporales y cubren permisos, privacidad familiar, aprobación/rechazo, lista de espera, traslados, cupos, aprobaciones concurrentes de la última plaza, incompatibilidades, duplicación, asistencia, recuperaciones, recibos e idempotencia. No modifican los datos de desarrollo. El entorno debe permitir sockets locales para ejecutarlas.

La prueba opcional `node tests/sync_browser.cjs` requiere Node, Playwright y Chromium instalados en la máquina de desarrollo (no son dependencias del servidor). `CHROMIUM_PATH` permite elegir el ejecutable de Chromium. Arranca su propio servidor y una base temporal: comprueba sincronización en ambas direcciones entre dos sesiones, diseño móvil, conservación de borradores, desconexión y recuperación.

## Alcance de esta versión

Preparada para desarrollo local con datos de demostración. Las sesiones de acceso duran 12 horas, usan cookies HttpOnly/SameSite y las contraseñas se almacenan con PBKDF2. Las operaciones de matrícula se serializan mediante transacciones SQLite para evitar exceder plazas.

Antes de usar datos reales se debe sustituir la entrada de demostración y sus cuentas públicas, desplegar detrás de HTTPS con cookies Secure y un servidor apropiado, y añadir recuperación de contraseñas, límites de intentos y copias de seguridad. No se integra una pasarela de pago ni se envían correos: los pagos se registran manualmente y los avisos se consultan dentro del módulo.

No se contemplan festivos, cancelación de sesiones individuales, descuentos, prorrateos, impuestos ni reservas de recuperación en otro grupo. El cierre de un grupo es definitivo en esta versión; conserva los registros históricos. Las incompatibilidades bloquean el guardado y se explican en el formulario.
