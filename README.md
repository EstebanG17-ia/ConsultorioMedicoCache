# Actividad: caché en un endpoint GET de Django

Proyecto `consultorio_medico` (app `citas`, SQLite). Se agregó un endpoint JSON con caché.

## Funcionalidad elegida
Listado de citas médicas (con datos básicos del paciente), con filtro por estado y paginación.

- **Endpoint:** `GET http://127.0.0.1:8000/api/citas/?page_size=200`
- **Parámetros opcionales:** `estado` (Pendiente, Confirmada, Cancelada), `page`, `page_size` (máx. 200)
- **Respuesta:** `{count, page, page_size, total_pages, results: [{id, paciente:{id,nombre,apellido}, fecha, hora, motivo, estado}]}` con código `200 OK`
- **Indicador de caché:** encabezado `X-Cache: HIT` (reutilizado) o `X-Cache: MISS` (consultó la BD); también se imprime en la consola del servidor.

## Tipo de caché
Caché en memoria local de Django (`LocMemCache`), configurado en `settings.py` (`CACHES`).
Clave: `citas_api:v<versión>:estado=<estado>:page=<n>:size=<n>`, así cada combinación de filtro y paginación tiene su propia entrada.

## Estrategia de actualización: invalidación al cambiar los datos
`citas/signals.py` escucha `post_save` y `post_delete` de **Cita** y **Paciente** (el JSON incluye el nombre del paciente).
Cada cambio incrementa el número de versión incluido en la clave, por lo que las entradas anteriores dejan de usarse y la siguiente solicitud
consulta la base de datos (`MISS`) y vuelve a llenar el caché. Cancelar, editar, crear o eliminar desde la web, el Admin o el Shell activan la invalidación.
(`bulk_create` no dispara señales; el comando de carga masiva invalida el caché manualmente.)

## Cómo ejecutar
```bash
python -m venv venv && venv\Scripts\activate      # Windows
pip install django
python manage.py migrate
python manage.py cargar_datos                     # 10 pacientes y 8 citas
python manage.py cargar_datos_cache --total 2000  # citas extra para que el tiempo sea medible
python manage.py runserver
```
Pruebas automáticas: `python manage.py test citas`

## Cómo reproducir las pruebas en Postman
1. **Sin caché:** el MISS siempre consulta la BD. Para medir el "sin caché" reinicia el servidor antes de cada solicitud
   (o mide con el caché vacío), registra 5 tiempos y promedia.
2. **Primera solicitud con caché:** reinicia el servidor, envía el GET → `X-Cache: MISS`. Anota su tiempo aparte.
3. **Cinco solicitudes siguientes:** misma URL → `X-Cache: HIT`. Registra los 5 tiempos.
4. **Actualización:** edita una cita (Admin o `/citas/<id>/editar/`), repite el GET → `X-Cache: MISS` y el JSON muestra el cambio; la siguiente vuelve a ser `HIT`.
