
from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    PageBreak,
    KeepTogether,
)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart


# =====================================================
# PALETA VISUAL FLOWERVIEW
# =====================================================

NEGRO = colors.HexColor("#111111")
NEGRO_OSCURO = colors.HexColor("#000000")

FONDO = colors.HexColor("#f6f7f9")
GRIS = colors.HexColor("#4b5563")
GRIS_CLARO = colors.HexColor("#e5e7eb")
BLANCO = colors.white

AZUL = colors.HexColor("#2563eb")
AMARILLO = colors.HexColor("#f59e0b")
VERDE = colors.HexColor("#15803d")
ROJO = colors.HexColor("#b91c1c")
MORADO = colors.HexColor("#8b5cf6")
CELESTE = colors.HexColor("#06b6d4")


# =====================================================
# FUNCIONES AUXILIARES
# =====================================================

def formato_pesos(valor):
    try:
        numero = int(round(float(valor or 0)))
    except (ValueError, TypeError):
        numero = 0

    return "$" + format(numero, ",").replace(",", ".")


def formato_numero(valor):
    try:
        return format(int(valor or 0), ",").replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def formato_porcentaje(valor):

    if valor is None:
        return "Sin datos anteriores"

    return f"{float(valor):+.1f}%"


def texto_seguro(valor):
    return escape(str(valor or ""))


def crear_tabla(datos, anchos, encabezado=True):

    tabla = Table(
        datos,
        colWidths=anchos,
        repeatRows=1 if encabezado else 0,
        hAlign="LEFT"
    )

    estilos = [
        ("GRID", (0, 0), (-1, -1), 0.4, GRIS_CLARO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        (
            "ROWBACKGROUNDS",
            (0, 1 if encabezado else 0),
            (-1, -1),
            [BLANCO, FONDO]
        ),
    ]

    if encabezado:
        estilos.extend([
            ("BACKGROUND", (0, 0), (-1, 0), NEGRO),
            ("TEXTCOLOR", (0, 0), (-1, 0), BLANCO),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])

    tabla.setStyle(TableStyle(estilos))

    return tabla


def crear_grafico_barras(
    labels,
    valores,
    titulo,
    color_barras=AZUL
):

    if not labels or not valores:
        return None

    drawing = Drawing(480, 210)

    grafico = VerticalBarChart()

    grafico.x = 45
    grafico.y = 45
    grafico.width = 405
    grafico.height = 135

    valores_limpios = []

    for valor in valores:
        try:
            valores_limpios.append(float(valor or 0))
        except (ValueError, TypeError):
            valores_limpios.append(0)

    grafico.data = [valores_limpios]

    grafico.categoryAxis.categoryNames = [
        str(label)[:18] for label in labels
    ]

    grafico.categoryAxis.labels.fontName = "Helvetica"
    grafico.categoryAxis.labels.fontSize = 7
    grafico.categoryAxis.labels.angle = 35
    grafico.categoryAxis.labels.boxAnchor = "ne"
    grafico.categoryAxis.labels.dy = -5

    grafico.valueAxis.labels.fontName = "Helvetica"
    grafico.valueAxis.labels.fontSize = 7
    grafico.valueAxis.valueMin = 0

    maximo = max(valores_limpios, default=0)

    grafico.valueAxis.valueMax = (
        maximo * 1.15 if maximo > 0 else 1
    )

    grafico.bars[0].fillColor = color_barras
    grafico.bars[0].strokeColor = color_barras

    grafico.barWidth = min(
        25,
        max(5, 300 / max(len(labels), 1))
    )

    grafico.groupSpacing = 8

    drawing.add(grafico)

    estilo_titulo = ParagraphStyle(
        "TituloGrafico",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=NEGRO,
        spaceBefore=8,
        spaceAfter=3
    )

    return KeepTogether([
        Paragraph(texto_seguro(titulo), estilo_titulo),
        drawing
    ])


def agregar_seccion(elementos, titulo, descripcion=None):

    estilos = getSampleStyleSheet()

    estilo_seccion = ParagraphStyle(
        "SeccionFlowerView",
        parent=estilos["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=NEGRO,
        spaceBefore=12,
        spaceAfter=7,
        keepWithNext=True
    )

    elementos.append(
        Paragraph(texto_seguro(titulo), estilo_seccion)
    )

    if descripcion:
        elementos.append(
            Paragraph(
                texto_seguro(descripcion),
                estilos["Normal"]
            )
        )

        elementos.append(Spacer(1, 5))


def tabla_segmento(registros, normal):

    datos = [
        [
            "Segmento",
            "Unidades",
            "Ingresos",
            "Participación"
        ]
    ]

    for registro in registros:

        datos.append([
            Paragraph(
                texto_seguro(registro.get("nombre")),
                normal
            ),
            formato_numero(registro.get("unidades")),
            formato_pesos(registro.get("ingresos")),
            f"{registro.get('participacion', 0):.2f}%"
        ])

    if len(datos) == 1:
        datos.append([
            "Sin información",
            "-",
            "-",
            "-"
        ])

    return crear_tabla(
        datos,
        [65 * mm, 25 * mm, 43 * mm, 41 * mm]
    )


# =====================================================
# GENERADOR PRINCIPAL DEL INFORME
# =====================================================

def generar_pdf_reporte(contexto):

    buffer = BytesIO()

    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title="Informe técnico BI - FlowerView",
        author="FlowerView",
        subject="Análisis comercial y operacional"
    )

    estilos = getSampleStyleSheet()

    titulo = ParagraphStyle(
        "TituloFlowerView",
        parent=estilos["Title"],
        fontName="Helvetica-Bold",
        fontSize=25,
        leading=30,
        textColor=NEGRO,
        alignment=TA_CENTER,
        spaceAfter=12
    )

    subtitulo = ParagraphStyle(
        "SubtituloFlowerView",
        parent=estilos["Normal"],
        fontSize=11,
        leading=15,
        textColor=GRIS,
        alignment=TA_CENTER,
        spaceAfter=10
    )

    normal = ParagraphStyle(
        "NormalFlowerView",
        parent=estilos["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#333333"),
        alignment=TA_LEFT
    )

    destacado = ParagraphStyle(
        "DestacadoFlowerView",
        parent=normal,
        fontName="Helvetica-Bold",
        textColor=NEGRO
    )

    elementos = []

    datos = contexto.get("datos", {})

    # =====================================================
    # PORTADA
    # =====================================================

    elementos.append(Spacer(1, 35 * mm))

    elementos.append(
        Paragraph("FLOWERVIEW", titulo)
    )

    elementos.append(
        Paragraph(
            "INFORME TÉCNICO DE INTELIGENCIA DE NEGOCIOS",
            subtitulo
        )
    )

    elementos.append(
        HRFlowable(
            width="75%",
            thickness=2,
            color=NEGRO,
            hAlign="CENTER",
            spaceBefore=10,
            spaceAfter=25
        )
    )

    desde = contexto.get("desde", "No definido")
    hasta = contexto.get("hasta", "No definido")

    fecha_generacion = timezone.localtime().strftime(
        "%d/%m/%Y %H:%M"
    )

    portada = [
        ["PARÁMETRO", "VALOR"],
        ["Periodo analizado", f"{desde} al {hasta}"],
        [
            "Periodo de comparación",
            f"{contexto.get('desde_anterior', '-')}"
            f" al {contexto.get('hasta_anterior', '-')}"
        ],
        ["Fecha de generación", fecha_generacion],
        ["Sistema", "FlowerView"],
        ["Tipo de informe", "Análisis comercial y operacional"],
    ]

    elementos.append(
        crear_tabla(portada, [55 * mm, 105 * mm])
    )

    elementos.append(Spacer(1, 20 * mm))

    elementos.append(
        Paragraph(
            "Documento generado automáticamente a partir "
            "de los registros históricos de pedidos y ventas "
            "de FlowerView.",
            ParagraphStyle(
                "NotaPortada",
                parent=normal,
                alignment=TA_CENTER,
                textColor=GRIS,
                fontSize=9
            )
        )
    )

    elementos.append(PageBreak())

    # =====================================================
    # 1. RESUMEN EJECUTIVO
    # =====================================================

    agregar_seccion(
        elementos,
        "1. Resumen ejecutivo",
        "Indicadores generales del comportamiento comercial "
        "durante el periodo seleccionado."
    )

    ingresos = contexto.get("ingresos", 0)
    ventas_productos = contexto.get("ventas_productos", 0)
    envios = contexto.get("envios", 0)
    pedidos = contexto.get("pedidos", 0)
    ticket = contexto.get("ticket", 0)
    unidades = contexto.get("unidades", 0)
    tasa_pagadas = contexto.get("conversion", 0)

    resumen = [
        ["Indicador", "Resultado"],
        ["Ingresos totales de pedidos pagados", formato_pesos(ingresos)],
        ["Ventas de productos", formato_pesos(ventas_productos)],
        ["Ingresos por envío", formato_pesos(envios)],
        ["Pedidos pagados", formato_numero(pedidos)],
        ["Unidades vendidas", formato_numero(unidades)],
        ["Ticket promedio por pedido", formato_pesos(ticket)],
        ["Tasa de órdenes pagadas", f"{tasa_pagadas}%"],
    ]

    elementos.append(
        crear_tabla(resumen, [100 * mm, 60 * mm])
    )

    elementos.append(Spacer(1, 8))

    elementos.append(
        Paragraph(
            "<b>Interpretación:</b> los ingresos totales "
            "corresponden al monto de las órdenes pagadas. "
            "Las ventas de productos y los ingresos por envío "
            "se presentan por separado para distinguir ambos "
            "componentes.",
            normal
        )
    )

    # =====================================================
    # 2. COMPARACIÓN CON EL PERIODO ANTERIOR
    # =====================================================

    agregar_seccion(
        elementos,
        "2. Comparación con el periodo anterior",
        "Se compara el periodo seleccionado con el periodo "
        "inmediatamente anterior de igual duración."
    )

    comparacion = [
        ["Indicador", "Variación"],
        ["Ingresos totales", formato_porcentaje(contexto.get("var_ingresos"))],
        ["Ventas de productos", formato_porcentaje(contexto.get("var_ventas_productos"))],
        ["Pedidos pagados", formato_porcentaje(contexto.get("var_pedidos"))],
        ["Ingresos por envío", formato_porcentaje(contexto.get("var_envios"))],
        ["Ticket promedio", formato_porcentaje(contexto.get("var_ticket"))],
        ["Unidades vendidas", formato_porcentaje(contexto.get("var_unidades"))],
    ]

    elementos.append(
        crear_tabla(comparacion, [100 * mm, 60 * mm])
    )

    elementos.append(Spacer(1, 6))

    elementos.append(
        Paragraph(
            "Una variación positiva representa un aumento "
            "respecto del periodo anterior; una variación "
            "negativa representa una disminución. Cuando "
            "el periodo anterior no registra valores, la "
            "variación se indica como no disponible.",
            normal
        )
    )

    # =====================================================
    # 3. EVOLUCIÓN TEMPORAL
    # =====================================================

    agregar_seccion(
        elementos,
        "3. Evolución temporal de las ventas",
        "Comportamiento diario de los ingresos correspondientes "
        "a pedidos pagados."
    )

    dias = datos.get("dias", {})

    grafico_dias = crear_grafico_barras(
        dias.get("labels", []),
        dias.get("ingresos", []),
        "Ingresos diarios",
        color_barras=AZUL
    )

    if grafico_dias:
        elementos.append(grafico_dias)

    datos_diarios = [
        ["Fecha", "Ingresos", "Pedidos"]
    ]

    labels_dias = dias.get("labels", [])
    ingresos_dias = dias.get("ingresos", [])
    pedidos_dias = dias.get("pedidos", [])

    for i, fecha in enumerate(labels_dias):

        datos_diarios.append([
            fecha,
            formato_pesos(
                ingresos_dias[i]
                if i < len(ingresos_dias) else 0
            ),
            formato_numero(
                pedidos_dias[i]
                if i < len(pedidos_dias) else 0
            )
        ])

    if len(datos_diarios) == 1:
        datos_diarios.append(["Sin registros", "-", "-"])

    elementos.append(
        crear_tabla(
            datos_diarios,
            [55 * mm, 65 * mm, 40 * mm]
        )
    )

    # =====================================================
    # 4. RENDIMIENTO POR DÍA DE LA SEMANA
    # =====================================================

    agregar_seccion(
        elementos,
        "4. Rendimiento por día de la semana",
        "Distribución de pedidos pagados según el día "
        "de creación de la orden."
    )

    semana = datos.get("semana", {})

    grafico_semana = crear_grafico_barras(
        semana.get("labels", []),
        semana.get("pedidos", []),
        "Pedidos por día de la semana",
        color_barras=AMARILLO
    )

    if grafico_semana:
        elementos.append(grafico_semana)

    tabla_semana = [
        ["Día", "Pedidos"]
    ]

    for i, dia in enumerate(semana.get("labels", [])):

        valores = semana.get("pedidos", [])

        tabla_semana.append([
            dia,
            formato_numero(
                valores[i] if i < len(valores) else 0
            )
        ])

    if len(tabla_semana) == 1:
        tabla_semana.append(["Sin información", "0"])

    elementos.append(
        crear_tabla(
            tabla_semana,
            [100 * mm, 60 * mm]
        )
    )

    # =====================================================
    # 5. ANÁLISIS DE PRODUCTOS
    # =====================================================

    agregar_seccion(
        elementos,
        "5. Análisis de productos",
        "Ranking de productos según las unidades vendidas "
        "durante el periodo."
    )

    productos = contexto.get("top_productos", [])

    tabla_productos = [
        ["Producto", "Unidades", "Ingresos"]
    ]

    for producto in productos:

        tabla_productos.append([
            Paragraph(
                texto_seguro(
                    producto.get("producto_nombre") or "Sin nombre"
                ),
                normal
            ),
            formato_numero(producto.get("unidades")),
            formato_pesos(producto.get("ingresos"))
        ])

    if len(tabla_productos) == 1:
        tabla_productos.append([
            "No hay ventas registradas", "-", "-"
        ])

    elementos.append(
        crear_tabla(
            tabla_productos,
            [90 * mm, 30 * mm, 40 * mm]
        )
    )

    # =====================================================
    # 6. CONCENTRACIÓN COMERCIAL
    # =====================================================

    agregar_seccion(
        elementos,
        "6. Concentración comercial",
        "Identifica cuánto representan los productos "
        "principales dentro de las ventas totales de productos."
    )

    concentracion = contexto.get(
        "concentracion_productos", []
    )

    tabla_concentracion = [
        [
            "Producto",
            "Ingresos",
            "Participación",
            "Acumulada"
        ]
    ]

    for producto in concentracion[:10]:

        tabla_concentracion.append([
            Paragraph(
                texto_seguro(producto.get("producto")),
                normal
            ),
            formato_pesos(producto.get("ingresos")),
            f"{producto.get('participacion', 0):.2f}%",
            f"{producto.get('participacion_acumulada', 0):.2f}%"
        ])

    if len(tabla_concentracion) == 1:
        tabla_concentracion.append([
            "Sin información", "-", "-", "-"
        ])

    elementos.append(
        crear_tabla(
            tabla_concentracion,
            [60 * mm, 38 * mm, 32 * mm, 30 * mm]
        )
    )

    elementos.append(Spacer(1, 7))

    elementos.append(
        Paragraph(
            f"<b>Concentración del Top 5:</b> "
            f"{contexto.get('concentracion_top_5', 0):.2f}% "
            "de los ingresos por productos.",
            destacado
        )
    )

    # =====================================================
    # 7. CATEGORÍAS
    # =====================================================

    agregar_seccion(
        elementos,
        "7. Análisis por categorías",
        "Participación de cada categoría sobre el total "
        "de ventas de productos."
    )

    elementos.append(
        tabla_segmento(
            contexto.get("analisis_categorias", []),
            normal
        )
    )

    # =====================================================
    # 8. OCASIONES
    # =====================================================

    agregar_seccion(
        elementos,
        "8. Análisis por ocasiones",
        "Distribución de las ventas según la ocasión "
        "asociada a los productos."
    )

    elementos.append(
        tabla_segmento(
            contexto.get("analisis_ocasiones", []),
            normal
        )
    )

    # =====================================================
    # 9. TIPOS
    # =====================================================

    agregar_seccion(
        elementos,
        "9. Análisis por tipos de producto",
        "Participación de los tipos de producto en los "
        "ingresos comerciales."
    )

    elementos.append(
        tabla_segmento(
            contexto.get("analisis_tipos", []),
            normal
        )
    )

    # =====================================================
    # 10. PRODUCTOS POR OCASIÓN
    # =====================================================

    agregar_seccion(
        elementos,
        "10. Productos más vendidos por ocasión"
    )

    ocasion = contexto.get("ocasion_sel") or "Todas las ocasiones"

    elementos.append(
        Paragraph(
            f"<b>Filtro aplicado:</b> {texto_seguro(ocasion)}",
            normal
        )
    )

    elementos.append(Spacer(1, 5))

    productos_ocasion = [
        ["Producto", "Categoría", "Unidades", "Ingresos"]
    ]

    for producto in contexto.get("top_por_ocasion", []):

        productos_ocasion.append([
            Paragraph(
                texto_seguro(producto.get("producto_nombre")),
                normal
            ),
            Paragraph(
                texto_seguro(producto.get("categoria_nombre")),
                normal
            ),
            formato_numero(producto.get("unidades")),
            formato_pesos(producto.get("ingresos"))
        ])

    if len(productos_ocasion) == 1:
        productos_ocasion.append([
            "No hay resultados", "-", "-", "-"
        ])

    elementos.append(
        crear_tabla(
            productos_ocasion,
            [55 * mm, 45 * mm, 25 * mm, 35 * mm]
        )
    )

    # =====================================================
    # 11. ANÁLISIS GEOGRÁFICO
    # =====================================================

    agregar_seccion(
        elementos,
        "11. Análisis geográfico de ventas",
        "Distribución de pedidos e ingresos según comuna."
    )

    comunas = datos.get("comunas", {})

    tabla_comunas = [
        ["Comuna", "Pedidos", "Ingresos"]
    ]

    labels_comunas = comunas.get("labels", [])
    pedidos_comunas = comunas.get("pedidos", [])
    ingresos_comunas = comunas.get("ingresos", [])

    for i, comuna in enumerate(labels_comunas):

        tabla_comunas.append([
            Paragraph(texto_seguro(comuna), normal),
            formato_numero(
                pedidos_comunas[i]
                if i < len(pedidos_comunas) else 0
            ),
            formato_pesos(
                ingresos_comunas[i]
                if i < len(ingresos_comunas) else 0
            )
        ])

    if len(tabla_comunas) == 1:
        tabla_comunas.append([
            "Sin información", "-", "-"
        ])

    elementos.append(
        crear_tabla(
            tabla_comunas,
            [75 * mm, 35 * mm, 50 * mm]
        )
    )

    # =====================================================
    # 12. ESTADOS DE PEDIDOS
    # =====================================================

    agregar_seccion(
        elementos,
        "12. Análisis operacional de pedidos",
        "Distribución de pedidos pagados según su estado "
        "de envío registrado."
    )

    estados = datos.get("estados", {})

    grafico_estados = crear_grafico_barras(
        estados.get("labels", []),
        estados.get("valores", []),
        "Pedidos por estado de envío",
        color_barras=VERDE
    )

    if grafico_estados:
        elementos.append(grafico_estados)

    tabla_estados = [
        ["Estado", "Cantidad"]
    ]

    for i, estado in enumerate(estados.get("labels", [])):

        valores = estados.get("valores", [])

        tabla_estados.append([
            estado,
            formato_numero(
                valores[i] if i < len(valores) else 0
            )
        ])

    if len(tabla_estados) == 1:
        tabla_estados.append(["Sin información", "0"])

    elementos.append(
        crear_tabla(
            tabla_estados,
            [100 * mm, 60 * mm]
        )
    )

    # =====================================================
    # 13. PRÓXIMAS ENTREGAS
    # =====================================================

    agregar_seccion(
        elementos,
        "13. Próximas entregas",
        "Pedidos pagados con fecha de entrega dentro "
        "de los próximos días y que no figuran como entregados."
    )

    proximas = contexto.get("proximas", [])

    tabla_entregas = [
        ["N.º de orden", "Fecha de entrega", "Estado"]
    ]

    for orden in proximas:

        fecha = getattr(orden, "fecha_entrega", None)

        fecha_texto = (
            fecha.strftime("%d/%m/%Y")
            if fecha else "Sin fecha"
        )

        tabla_entregas.append([
            str(getattr(orden, "id", "-")),
            fecha_texto,
            texto_seguro(
                getattr(orden, "estado_envio", "Sin estado")
            )
        ])

    if len(tabla_entregas) == 1:
        tabla_entregas.append([
            "No hay entregas próximas", "-", "-"
        ])

    elementos.append(
        crear_tabla(
            tabla_entregas,
            [45 * mm, 55 * mm, 60 * mm]
        )
    )

    # =====================================================
    # 14. INDICADORES OPERACIONALES
    # =====================================================

    agregar_seccion(
        elementos,
        "14. Indicadores operacionales"
    )

    indicadores_operacionales = [
        ["Indicador", "Cantidad"],
        [
            "Pedidos pendientes de preparación",
            formato_numero(contexto.get("por_preparar"))
        ],
        [
            "Pedidos en camino",
            formato_numero(contexto.get("en_camino"))
        ],
        [
            "Entregas programadas para hoy",
            formato_numero(contexto.get("entregas_hoy"))
        ],
        [
            "Órdenes sin pagar",
            formato_numero(contexto.get("sin_pagar"))
        ],
    ]

    elementos.append(
        crear_tabla(
            indicadores_operacionales,
            [100 * mm, 60 * mm]
        )
    )

    # =====================================================
    # 15. CONCLUSIONES Y RECOMENDACIONES
    # =====================================================

    agregar_seccion(
        elementos,
        "15. Conclusiones y recomendaciones"
    )

    conclusiones = []

    var_ingresos = contexto.get("var_ingresos")
    var_pedidos = contexto.get("var_pedidos")
    var_unidades = contexto.get("var_unidades")

    if var_ingresos is not None:

        if var_ingresos > 0:
            conclusiones.append(
                "Los ingresos totales aumentaron respecto "
                "del periodo anterior."
            )

        elif var_ingresos < 0:
            conclusiones.append(
                "Los ingresos totales disminuyeron respecto "
                "del periodo anterior. Se recomienda revisar "
                "la evolución de la demanda y el desempeño "
                "de los productos."
            )

        else:
            conclusiones.append(
                "Los ingresos totales se mantuvieron estables "
                "respecto del periodo anterior."
            )

    else:
        conclusiones.append(
            "No existe una base anterior suficiente para "
            "comparar los ingresos."
        )

    if var_pedidos is not None:

        if var_pedidos > 0:
            conclusiones.append(
                "La cantidad de pedidos pagados aumentó "
                "respecto del periodo anterior."
            )

        elif var_pedidos < 0:
            conclusiones.append(
                "La cantidad de pedidos pagados disminuyó. "
                "Conviene revisar la actividad comercial."
            )

    if var_unidades is not None and var_unidades < 0:

        conclusiones.append(
            "Las unidades vendidas disminuyeron. "
            "Se recomienda revisar la disponibilidad "
            "y rotación del inventario."
        )

    if contexto.get("concentracion_productos"):

        top5 = contexto.get("concentracion_top_5", 0)

        if top5 >= 70:
            conclusiones.append(
                "Existe una concentración elevada de ingresos "
                "en los cinco productos principales. Se "
                "recomienda evaluar estrategias para diversificar "
                "las ventas."
            )

        elif top5 >= 40:
            conclusiones.append(
                "Los cinco productos principales representan "
                "una proporción importante de los ingresos. "
                "Conviene monitorear su disponibilidad."
            )

        else:
            conclusiones.append(
                "Los ingresos presentan una distribución "
                "relativamente diversificada entre los productos."
            )

    if tasa_pagadas < 70:
        conclusiones.append(
            "La tasa de órdenes pagadas es inferior al 70%. "
            "Se recomienda revisar las órdenes pendientes "
            "y posibles dificultades durante el proceso de pago."
        )

    if contexto.get("por_preparar", 0) > 0:
        conclusiones.append(
            "Existen pedidos pendientes de preparación. "
            "Se recomienda priorizar su revisión para mantener "
            "el cumplimiento de las entregas."
        )

    if not conclusiones:
        conclusiones.append(
            "No se dispone de suficientes datos para formular "
            "conclusiones comerciales adicionales."
        )

    for conclusion in conclusiones:

        elementos.append(
            Paragraph(
                "• " + texto_seguro(conclusion),
                normal
            )
        )

        elementos.append(Spacer(1, 5))

    elementos.append(Spacer(1, 8))

    elementos.append(
        Paragraph(
            "<b>Consideraciones metodológicas:</b> "
            "el análisis utiliza los registros de órdenes "
            "pagadas y los datos históricos de sus artículos. "
            "La tasa de órdenes pagadas corresponde a la "
            "proporción de órdenes pagadas respecto del total "
            "de órdenes creadas en el periodo; no representa "
            "la conversión de visitantes del sitio web. "
            "El informe no estima tiempos de preparación "
            "ni de entrega, ya que esos tiempos requieren "
            "marcas temporales específicas.",
            normal
        )
    )

    # =====================================================
    # PIE DE PÁGINA
    # =====================================================

    def pie_pagina(canvas, doc):

        canvas.saveState()

        ancho, alto = A4

        canvas.setStrokeColor(GRIS_CLARO)
        canvas.setLineWidth(0.5)

        canvas.line(
            18 * mm,
            15 * mm,
            ancho - 18 * mm,
            15 * mm
        )

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GRIS)

        canvas.drawString(
            18 * mm,
            10 * mm,
            "FlowerView | Informe técnico BI"
        )

        canvas.drawRightString(
            ancho - 18 * mm,
            10 * mm,
            f"Página {doc.page}"
        )

        canvas.restoreState()

    # =====================================================
    # GENERAR DOCUMENTO
    # =====================================================

    documento.build(
        elementos,
        onFirstPage=pie_pagina,
        onLaterPages=pie_pagina
    )

    pdf = buffer.getvalue()

    buffer.close()

    return pdf
