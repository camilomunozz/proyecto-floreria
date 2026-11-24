
import os
import json
import logging

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


logger = logging.getLogger(__name__)


@require_POST
@csrf_protect
@never_cache
def chat(request):
    try:
        # Validar el JSON recibido
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

        # Obtener API Key de Groq
        api_key = os.environ.get("GROQ_API_KEY")

        if not api_key:
            logger.error("GROQ_API_KEY no está configurada.")

            return JsonResponse(
                {"error": "El servicio de recomendaciones no está configurado."},
                status=503
            )

        # Instrucciones del asistente FlowerView
        instrucciones = """
        Eres el asistente virtual de FlowerView,
        una tienda especializada en arreglos florales.

        Tu objetivo es ayudar a los clientes a elegir
        arreglos florales adecuados para sus necesidades.

        REGLAS DE COMPORTAMIENTO:

        1. Responde siempre en español.
        2. Mantén un tono amable, cercano y profesional.
        3. Ayuda a identificar preferencias como:
           - Tipo de flores.
           - Colores.
           - Ocasiones especiales.
           - Presupuesto.
           - Estilo del arreglo.
           - Persona a quien va dirigido.

        4. Puedes hacer recomendaciones generales de flores,
           combinaciones de colores y estilos.

        5. Si el cliente indica un presupuesto, procura
           orientar las recomendaciones a ese monto.

        6. No inventes nombres, precios, stock ni disponibilidad
           de productos de FlowerView.

        7. Si no tienes acceso al catálogo, aclara que tus
           recomendaciones son orientativas y que los productos
           disponibles deben verificarse en la tienda.

        8. Si necesitas más información para recomendar,
           realiza preguntas breves al cliente.

        9. No inventes promociones, descuentos ni condiciones
           de compra.

        10. Mantén las respuestas claras, útiles y relativamente
            breves.

        Recuerda que FlowerView ofrece compra online
        y retiro en tienda. No prometas despacho a domicilio.
        """

        # Crear cliente Groq
        cliente = Groq(
            api_key=api_key,
            timeout=30.0,
            max_retries=1
        )

        # Enviar solicitud al modelo
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
            max_completion_tokens=1024
        )

        texto_respuesta = respuesta.choices[0].message.content

        if not texto_respuesta or not texto_respuesta.strip():
            logger.warning("Groq devolvió una respuesta vacía.")

            return JsonResponse(
                {"error": "No recibimos una respuesta. Inténtalo nuevamente."},
                status=502
            )

        return JsonResponse({
            "respuesta": texto_respuesta.strip()
        })

    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "La solicitud no contiene JSON válido."},
            status=400
        )

    except APITimeoutError:
        logger.warning("Tiempo de espera agotado al consultar Groq.")

        return JsonResponse(
            {"error": "El asistente está tardando demasiado. Inténtalo nuevamente."},
            status=504
        )

    except APIConnectionError:
        logger.exception("No se pudo establecer conexión con Groq.")

        return JsonResponse(
            {"error": "No pudimos conectar con el asistente. Inténtalo nuevamente."},
            status=503
        )

    except RateLimitError:
        logger.warning("Groq alcanzó el límite de solicitudes.")

        return JsonResponse(
            {"error": "El asistente ha alcanzado temporalmente su límite de solicitudes. Inténtalo más tarde."},
            status=429
        )

    except APIStatusError as e:
        logger.exception("Groq respondió con un error HTTP: %s", e.status_code)

        return JsonResponse(
            {"error": "El servicio de recomendaciones presentó un problema. Inténtalo nuevamente."},
            status=502
        )

    except Exception as e:
        logger.exception(
            "Error inesperado al consultar Groq: %s",
            type(e).__name__
        )

        return JsonResponse(
            {"error": "No pudimos procesar tu mensaje. Inténtalo nuevamente."},
            status=502
        )
