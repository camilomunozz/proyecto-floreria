

import os
import json
import logging
import re
import unicodedata

from decimal import Decimal, InvalidOperation

from groq import (
    Groq,
    APITimeoutError,
    APIConnectionError,
    RateLimitError,
    APIStatusError,
)

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache

from tienda.models import Producto, Categoria, Tipo, Ocasion
from rapidfuzz import fuzz, process


logger = logging.getLogger(__name__)


def normalizar_texto(texto):
    """Elimina tildes y convierte el texto a minúsculas."""
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(
        caracter for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )


def buscar_coincidencias_inteligentes(
    consulta,
    opciones,
    limite=3,
    puntuacion_minima=75
):
    """Busca coincidencias aproximadas."""

    if not consulta or not opciones:
        return []

    consulta = normalizar_texto(consulta)

    opciones_normalizadas = {
        normalizar_texto(opcion): opcion
        for opcion in opciones
        if opcion
    }

    resultados = process.extract(
        consulta,
        list(opciones_normalizadas.keys()),
        scorer=fuzz.ratio,
        limit=limite,
        score_cutoff=puntuacion_minima
    )

    return [
        opciones_normalizadas[coincidencia]
        for coincidencia, puntuacion, indice in resultados
    ]


def extraer_presupuesto(mensaje):
    """Detecta presupuestos máximos, mínimos y exactos."""

    texto = normalizar_texto(mensaje)

    patrones = [
        (
            "exacto",
            r"(?:exactamente(?:\s+a)?|igual\s+a|por\s+un\s+valor\s+de)\s*\$?\s*([\d.,]+)"
        ),
        (
            "minimo",
            r"(?:mas\s+de|superior\s+a|sobre|desde|a\s+partir\s+de)\s*\$?\s*([\d.,]+)"
        ),
        (
            "maximo",
            r"(?:menos\s+de|inferior\s+a|bajo|hasta|como\s+maximo|maximo\s+de)\s*\$?\s*([\d.,]+)"
        ),
        (
            "maximo",
            r"\$\s*([\d.,]+)"
        ),
    ]

    for tipo, patron in patrones:
        coincidencia = re.search(patron, texto, re.IGNORECASE)

        if coincidencia:
            monto = re.sub(r"\D", "", coincidencia.group(1))

            if monto:
                try:
                    return tipo, Decimal(monto)
                except InvalidOperation:
                    return None, None

    return None, None


def obtener_filtros(mensaje):
    """
    Detecta características, categorías, tipos y ocasiones
    tolerando diferencias de escritura y singular/plural.
    """

    texto = normalizar_texto(mensaje)
    palabras_consulta = re.findall(r"\b[a-z]{4,}\b", texto)

    filtros = {
        "palabras": [],
        "categoria": [],
        "tipo": [],
        "ocasion": [],
    }

    caracteristicas = [
        "rojo", "blanco", "rosado", "amarillo",
        "azul", "morado", "lila",
        "tulipan", "rosa", "girasol",
        "orquidea", "lirio",
    ]

    for palabra in palabras_consulta:
        coincidencia = process.extractOne(
            palabra,
            caracteristicas,
            scorer=fuzz.ratio,
            score_cutoff=88
        )

        if coincidencia:
            caracteristica = coincidencia[0]

            if caracteristica not in filtros["palabras"]:
                filtros["palabras"].append(caracteristica)

    modelos = {
        "categoria": Categoria,
        "tipo": Tipo,
        "ocasion": Ocasion,
    }

    for clave, modelo in modelos.items():

        nombres = modelo.objects.values_list("nombre", flat=True)

        for nombre in nombres:
            nombre_normalizado = normalizar_texto(nombre)

            palabras_nombre = re.findall(
                r"\b[a-z]{4,}\b",
                nombre_normalizado
            )

            for palabra in palabras_consulta:

                coincidencia = process.extractOne(
                    palabra,
                    palabras_nombre,
                    scorer=fuzz.ratio,
                    score_cutoff=88
                )

                if coincidencia:
                    if nombre not in filtros[clave]:
                        filtros[clave].append(nombre)
                    break

    return filtros


def obtener_productos(mensaje, request=None):
    """
    Busca productos reales aplicando coincidencias aproximadas
    y los criterios detectados en el mensaje.
    """

    tipo_presupuesto, presupuesto = extraer_presupuesto(mensaje)
    filtros = obtener_filtros(mensaje)

    productos = Producto.objects.filter(
        disponible=True,
        stock__gt=0
    ).select_related(
        "tipo",
        "categoria",
        "ocasion"
    )

    # Presupuesto.
    if presupuesto is not None:

        if tipo_presupuesto == "maximo":
            productos = productos.filter(precio__lte=presupuesto)

        elif tipo_presupuesto == "minimo":
            productos = productos.filter(precio__gte=presupuesto)

        elif tipo_presupuesto == "exacto":
            productos = productos.filter(precio=presupuesto)

    # Comparación aproximada entre palabras.
    def coincide_texto(consulta, contenido):

        consulta = normalizar_texto(consulta)
        contenido = normalizar_texto(contenido)

        palabras = re.findall(r"\b[a-z]{3,}\b", consulta)
        palabras_contenido = re.findall(
            r"\b[a-z]{3,}\b",
            contenido
        )

        return all(
            any(
                fuzz.ratio(palabra, palabra_producto) >= 88
                for palabra_producto in palabras_contenido
            )
            for palabra in palabras
        )

    productos_filtrados = []

    for producto in productos:

        contenido = " ".join([
            producto.nombre or "",
            producto.descripcion or "",
            producto.categoria.nombre if producto.categoria else "",
            producto.tipo.nombre if producto.tipo else "",
            producto.ocasion.nombre if producto.ocasion else "",
        ])

        coincide = True

        # Características y colores.
        for palabra in filtros["palabras"]:
            if not coincide_texto(palabra, contenido):
                coincide = False
                break

        # Categorías.
        if coincide:
            for categoria in filtros["categoria"]:
                if not coincide_texto(categoria, contenido):
                    coincide = False
                    break

        # Tipos.
        if coincide:
            for tipo in filtros["tipo"]:
                if not coincide_texto(tipo, contenido):
                    coincide = False
                    break

        # Ocasiones.
        if coincide:
            for ocasion in filtros["ocasion"]:
                if not coincide_texto(ocasion, contenido):
                    coincide = False
                    break

        if coincide:
            productos_filtrados.append(producto)

    productos = sorted(
        productos_filtrados,
        key=lambda producto: producto.precio
    )[:3]

    catalogo = []
    tarjetas = []

    for producto in productos:

        imagen_url = None

        if producto.imagen:
            imagen_url = producto.imagen.url

            if request:
                imagen_url = request.build_absolute_uri(imagen_url)

        descripcion = producto.descripcion or ""

        catalogo.append({
            "nombre": producto.nombre,
            "precio": str(producto.precio),
            "descripcion": descripcion,
            "tipo": producto.tipo.nombre if producto.tipo else None,
            "categoria": (
                producto.categoria.nombre
                if producto.categoria else None
            ),
            "ocasion": (
                producto.ocasion.nombre
                if producto.ocasion else None
            ),
        })

        tarjetas.append({
            "id": producto.id,
            "nombre": producto.nombre,
            "precio": str(producto.precio),
            "descripcion": descripcion[:140],
            "imagen": imagen_url,
        })

    return catalogo, tarjetas, filtros, tipo_presupuesto, presupuesto


@require_POST
@csrf_protect
@never_cache
def chat(request):

    try:
        data = json.loads(request.body)

        if not isinstance(data, dict):
            return JsonResponse(
                {"error": "La solicitud debe contener un objeto JSON."},
                status=400
            )

        mensaje = data.get("mensaje", "")

        if not isinstance(mensaje, str):
            return JsonResponse(
                {"error": "El mensaje debe ser texto."},
                status=400
            )

        mensaje = mensaje.strip()

        if not mensaje:
            return JsonResponse(
                {"error": "Debes escribir un mensaje."},
                status=400
            )

        if len(mensaje) > 1000:
            return JsonResponse(
                {"error": "El mensaje es demasiado largo."},
                status=400
            )

        api_key = os.environ.get("GROQ_API_KEY")

        if not api_key:
            logger.error("GROQ_API_KEY no está configurada.")

            return JsonResponse(
                {
                    "error": "El servicio de recomendaciones no está configurado."
                },
                status=503
            )

        (
            catalogo,
            tarjetas,
            filtros,
            tipo_presupuesto,
            presupuesto
        ) = obtener_productos(
            mensaje=mensaje,
            request=request
        )

        if catalogo:

            productos_json = json.dumps(
                catalogo,
                ensure_ascii=False,
                indent=2
            )

            informacion_catalogo = f"""
PRODUCTOS REALES ENCONTRADOS:

{productos_json}

Recomienda exclusivamente productos de esta lista.
"""

        else:

            informacion_catalogo = """
NO SE ENCONTRARON PRODUCTOS QUE CUMPLAN LOS CRITERIOS.

No inventes productos ni precios.
Comunica amablemente que no encontramos coincidencias.
Puedes preguntar si desea cambiar algún criterio.
"""

        instrucciones = f"""
Eres el asistente virtual de FlowerView,
una tienda especializada en arreglos florales.

REGLAS:

1. Responde siempre en español.
2. Utiliza un tono amable y profesional.
3. Responde con un máximo de 80 palabras.
4. Recomienda exclusivamente productos del catálogo.
5. Nunca inventes nombres, precios ni disponibilidad.
6. Respeta todos los criterios solicitados.
7. Si no hay coincidencias, comunícalo amablemente.
8. Si necesitas información adicional, realiza una sola pregunta breve.
9. FlowerView ofrece compra online y retiro en tienda.
10. No prometas despacho a domicilio.
11. Cuando recomiendes productos, menciona sus nombres.
12. No describas características que no estén respaldadas
    por la información del catálogo.

CRITERIOS DETECTADOS:

Características: {filtros["palabras"]}
Categorías: {filtros["categoria"]}
Tipos: {filtros["tipo"]}
Ocasiones: {filtros["ocasion"]}
Presupuesto: {tipo_presupuesto} - {presupuesto}

{informacion_catalogo}
"""

        cliente = Groq(
            api_key=api_key,
            timeout=30.0,
            max_retries=1
        )

        respuesta = cliente.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": instrucciones
                },
                {
                    "role": "user",
                    "content": mensaje
                }
            ],
            max_completion_tokens=300
        )

        texto_respuesta = respuesta.choices[0].message.content

        if not texto_respuesta or not texto_respuesta.strip():

            logger.warning("Groq devolvió una respuesta vacía.")

            return JsonResponse(
                {
                    "error": "No recibimos una respuesta. Inténtalo nuevamente."
                },
                status=502
            )

        return JsonResponse({
            "respuesta": texto_respuesta.strip(),
            "productos": tarjetas
        })

    except json.JSONDecodeError:

        return JsonResponse(
            {"error": "La solicitud no contiene JSON válido."},
            status=400
        )

    except APITimeoutError:

        logger.warning("Tiempo de espera agotado al consultar Groq.")

        return JsonResponse(
            {
                "error": "El asistente está tardando demasiado. Inténtalo nuevamente."
            },
            status=504
        )

    except APIConnectionError:

        logger.exception("No se pudo establecer conexión con Groq.")

        return JsonResponse(
            {
                "error": "No pudimos conectar con el asistente. Inténtalo nuevamente."
            },
            status=503
        )

    except RateLimitError:

        logger.warning("Groq alcanzó el límite de solicitudes.")

        return JsonResponse(
            {
                "error": "El asistente ha alcanzado temporalmente su límite de solicitudes."
            },
            status=429
        )

    except APIStatusError as e:

        logger.exception(
            "Groq respondió con un error HTTP: %s",
            e.status_code
        )

        return JsonResponse(
            {
                "error": "El servicio de recomendaciones presentó un problema."
            },
            status=502
        )

    except Exception as e:

        logger.exception(
            "Error inesperado en el chatbot: %s",
            type(e).__name__
        )

        return JsonResponse(
            {
                "error": "No pudimos procesar tu mensaje. Inténtalo nuevamente."
            },
            status=502
        )
