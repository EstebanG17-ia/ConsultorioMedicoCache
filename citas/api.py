"""Endpoint JSON de solo lectura con caché (Actividad de caché en Django).

GET /api/citas/?estado=Pendiente&page=1&page_size=50

* Si el resultado ya está en caché -> se reutiliza (encabezado X-Cache: HIT).
* Si no está -> se consulta la base de datos, se guarda y se responde
  (encabezado X-Cache: MISS).

Estrategia de actualización: INVALIDACIÓN AL CAMBIAR LOS DATOS.
Cada clave incluye un "número de versión". Cuando se crea, edita o elimina una
Cita o un Paciente (ver signals.py) se incrementa la versión, por lo que todas
las claves anteriores dejan de usarse y la siguiente solicitud vuelve a
consultar la base de datos.
"""
import logging

from django.core.cache import cache
from django.core.paginator import EmptyPage, Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Cita

logger = logging.getLogger("citas.cache")

VERSION_KEY = "citas_api:version"
TIMEOUT_SEGURIDAD = 60 * 60  # 1 h: solo evita que queden claves viejas para siempre
PAGE_SIZE_POR_DEFECTO = 50
PAGE_SIZE_MAXIMO = 200


def _version_actual():
    version = cache.get(VERSION_KEY)
    if version is None:
        cache.add(VERSION_KEY, 1, timeout=None)
        version = cache.get(VERSION_KEY, 1)
    return version


def invalidar_cache_citas():
    """Se llama cuando cambia una Cita o un Paciente."""
    _version_actual()  # asegura que la clave exista
    nueva = cache.incr(VERSION_KEY)
    logger.info("Caché de citas invalidado (nueva versión: %s)", nueva)
    return nueva


def _entero(valor, por_defecto):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None
    return numero if numero > 0 else None


def _construir_clave(estado, page, page_size):
    return (
        f"citas_api:v{_version_actual()}:estado={estado or 'todos'}"
        f":page={page}:size={page_size}"
    )


def _consultar_bd(estado, page, page_size):
    citas = Cita.objects.select_related("paciente").all()
    if estado:
        citas = citas.filter(estado=estado)
    paginador = Paginator(citas, page_size)
    pagina = paginador.page(page)  # puede lanzar EmptyPage
    return {
        "count": paginador.count,
        "page": pagina.number,
        "page_size": page_size,
        "total_pages": paginador.num_pages,
        "results": [
            {
                "id": c.id,
                "paciente": {
                    "id": c.paciente_id,
                    "nombre": c.paciente.nombre,
                    "apellido": c.paciente.apellido,
                },
                "fecha": c.fecha.isoformat(),
                "hora": c.hora.strftime("%H:%M"),
                "motivo": c.motivo,
                "estado": c.estado,
            }
            for c in pagina.object_list
        ],
    }


@require_GET
def api_citas(request):
    estado = request.GET.get("estado", "").strip()
    if estado and estado not in dict(Cita.ESTADOS):
        return JsonResponse({"error": "Estado no válido."}, status=400)

    page = _entero(request.GET.get("page", 1), 1)
    page_size = _entero(
        request.GET.get("page_size", PAGE_SIZE_POR_DEFECTO), PAGE_SIZE_POR_DEFECTO
    )
    if page is None or page_size is None:
        return JsonResponse({"error": "page y page_size deben ser enteros positivos."}, status=400)
    page_size = min(page_size, PAGE_SIZE_MAXIMO)

    clave = _construir_clave(estado, page, page_size)
    datos = cache.get(clave)
    if datos is not None:
        origen = "HIT"
    else:
        try:
            datos = _consultar_bd(estado, page, page_size)
        except EmptyPage:
            return JsonResponse({"error": "Página fuera de rango."}, status=404)
        cache.set(clave, datos, TIMEOUT_SEGURIDAD)
        origen = "MISS"

    logger.info("GET /api/citas/ [%s] clave=%s", origen, clave)
    respuesta = JsonResponse(datos)
    respuesta["X-Cache"] = origen
    return respuesta
