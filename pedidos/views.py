import json
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Min, Q, Sum
from django.db.models.functions import ExtractWeekDay, TruncDate
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from carrito.carrito import Carrito
from tienda.decorators import role_required
from .forms import CheckoutForm
from .models import ItemOrden, Orden, TarifaComuna
from .services import WebpayService
from .utils import enviar_correo_orden_exitosa
from datetime import date, timedelta
from django.db.models import (
    Avg, Count, DecimalField, ExpressionWrapper,
    F, Q, Sum
)
from django.db.models.functions import TruncDate, ExtractWeekDay
from django.utils.dateparse import parse_date

def iniciar_checkout(request):
    carrito = Carrito(request)
    
    if len(carrito) == 0:
        return redirect('carrito_detalle')

    # Verificamos qué datos tiene guardados el usuario
    tiene_direccion = request.user.is_authenticated and bool(getattr(request.user, 'direccion', None)) and bool(getattr(request.user, 'comuna', None))
    
    tipo_envio = 'registrada' if tiene_direccion else 'otra'

    if request.method == 'POST':
        tipo_envio = request.POST.get('tipo_envio', 'registrada')
        form = CheckoutForm(request.POST)
        
        if request.user.is_authenticated:
            form.data = form.data.copy()
            form.data['email_cliente'] = request.user.email
            
            # Si eligió usar su dirección registrada, inyectamos la dirección y comuna del perfil
            if tipo_envio == 'registrada' and tiene_direccion:
                form.data['calle'] = getattr(request.user, 'direccion', '')
                form.data['comuna'] = getattr(request.user, 'comuna', '')
            
            # Si el usuario ya tiene nombre o teléfono en su perfil, los auto-completamos si vinieron vacíos
            if not form.data.get('nombre_destinatario') and getattr(request.user, 'first_name', None):
                form.data['nombre_destinatario'] = request.user.get_full_name()
            if not form.data.get('telefono_destinatario') and getattr(request.user, 'telefono', None):
                form.data['telefono_destinatario'] = request.user.telefono

        if form.is_valid():
            orden = form.save(commit=False)
            
            if request.user.is_authenticated:
                orden.usuario = request.user

            comuna_elegida = form.cleaned_data.get('comuna')
            try:
                tarifa = TarifaComuna.objects.get(comuna=comuna_elegida)
                orden.costo_envio = tarifa.precio_envio
            except TarifaComuna.DoesNotExist:
                orden.costo_envio = 0

            orden.total = carrito.total() + orden.costo_envio
            orden.pagado = False
            orden.save()

            for item in carrito:
                producto = item['producto']
                ItemOrden.objects.create(
                    orden=orden,
                    producto_nombre=producto.nombre,
                    categoria_nombre=producto.categoria.nombre if producto.categoria else "",
                    ocasion_nombre=producto.ocasion.nombre if producto.ocasion else "",
                    tipo_nombre=producto.tipo.nombre if producto.tipo else "",
                    precio_unitario=item['precio'],
                    cantidad=item['cantidad'],
                )

            request.session['orden_id'] = orden.id
            return redirect('iniciar_pago')
    else:
        # Pre-llenamos el formulario con lo que el usuario tenga en su cuenta
        initial_data = {}
        if request.user.is_authenticated:
            initial_data['email_cliente'] = request.user.email
            if getattr(request.user, 'first_name', None):
                initial_data['nombre_destinatario'] = request.user.get_full_name()
            if getattr(request.user, 'telefono', None):
                initial_data['telefono_destinatario'] = request.user.telefono
        
        form = CheckoutForm(initial=initial_data)

    tarifas_qs = TarifaComuna.objects.all()
    tarifas_dict = {t.comuna: float(t.precio_envio) for t in tarifas_qs}

    context = {
        'form': form,
        'carrito': carrito,
        'tiene_perfil': tiene_direccion,
        'tipo_envio_seleccionado': tipo_envio, 
        'tarifas_json': json.dumps(tarifas_dict),
        'comuna_usuario': getattr(request.user, 'comuna', '') if request.user.is_authenticated else '',
        # Pasamos variables para saber qué le falta exactamente al usuario
        'user_tiene_nombre': bool(getattr(request.user, 'first_name', None)),
        'user_tiene_telefono': bool(getattr(request.user, 'telefono', None)),
    }
    return render(request, 'pedidos/checkout.html', context)
    
def pago_exitoso(request):
    orden_id = request.session.get('orden_id')
    orden = None
    if orden_id:
        try:
            orden = Orden.objects.get(id=orden_id)
        except Orden.DoesNotExist:
            pass

    context = {
        'orden': orden,
    }
    return render(request, 'pedidos/exito.html', context)


def previsualizar_correo(request, orden_id):
    """
    Vista temporal para renderizar el correo en el navegador web
    y ver cómo queda el diseño HTML.
    URL de prueba: http://127.0.0.1:8000/pedidos/preview-email/1/
    """
    # Buscamos una orden existente (por ejemplo, la orden ID 1)
    orden = Orden.objects.get(id=orden_id)
    
    # Renderizamos directamente la plantilla del correo pasando la orden
    return render(request, 'pedidos/email_confirmacion.html', {'orden': orden})

#WEBPAY

def iniciar_pago(request):
    orden_id = request.session.get('orden_id')
    if not orden_id:
        return redirect('carrito_detalle')

    try:
        orden = Orden.objects.get(id=orden_id, pagado=False)
    except Orden.DoesNotExist:
        return redirect('carrito_detalle')

    buy_order = f"ORD-{orden.id}"
    session_id = request.session.session_key or f"SES-{orden.id}"
    amount = int(orden.total)
    return_url = request.build_absolute_uri(reverse('webpay_retorno'))

    # Llamada limpia al servicio
    response = WebpayService.crear_transaccion(buy_order, session_id, amount, return_url)

    orden.token_ws = response['token']
    orden.save(update_fields=['token_ws'])

    return render(request, 'pedidos/redirigir_webpay.html', {
        'url_webpay': response['url'],
        'token_ws': response['token']
    })

@csrf_exempt
def webpay_retorno(request):
    token_ws = request.GET.get('token_ws') or request.POST.get('token_ws')
    tbk_token = request.GET.get('TBK_TOKEN') or request.POST.get('TBK_TOKEN')

    if tbk_token and not token_ws:
        return render(request, 'pedidos/pago_fallido.html', {
            'motivo': 'Has anulado el pago en Webpay. Tu carrito sigue intacto por si deseas intentarlo nuevamente.'
        })

    if not token_ws:
        return redirect('carrito_detalle')

    try:
        orden = Orden.objects.get(token_ws=token_ws)
    except Orden.DoesNotExist:
        return redirect('carrito_detalle')

    if orden.pagado:
        return redirect('pago_exitoso')

    # Confirmación limpia a través del servicio
    response = WebpayService.confirmar_transaccion(token_ws)

    if response.get('status') == 'AUTHORIZED' and response.get('response_code') == 0:
        orden.pagado = True
        orden.codigo_autorizacion = response.get('authorization_code')
        orden.save(update_fields=['pagado', 'codigo_autorizacion'])

        enviar_correo_orden_exitosa(orden)

        request.session['session_key'] = {}
        request.session.modified = True
        if request.user.is_authenticated:
            request.user.carrito_guardado = {}
            request.user.save(update_fields=['carrito_guardado'])

        request.session['orden_id'] = orden.id
        return redirect('pago_exitoso')
    else:
        return render(request, 'pedidos/pago_fallido.html', {
            'motivo': 'El pago fue rechazado por el banco o tarjeta. Por favor, intenta con otro medio de pago.'
        })



#GESTION PEDIDO
@role_required('admin')
def gestion_pedidos(request):
    # Por defecto mostramos solo pedidos pagados (los fallidos/abandonados no estorban)
    ordenes = Orden.objects.filter(pagado=True).prefetch_related('items').order_by('fecha_entrega', '-id')

    # 1. Filtro por estado de envío
    estado_filtro = request.GET.get('estado', '')
    if estado_filtro in ['pendiente', 'en_camino', 'entregado']:
        ordenes = ordenes.filter(estado_envio=estado_filtro)

    # 2. Filtro por fecha de entrega (ej: ?fecha=hoy o ?fecha=2026-11-17)
    fecha_filtro = request.GET.get('fecha', '')
    hoy = timezone.localdate()
    if fecha_filtro == 'hoy':
        ordenes = ordenes.filter(fecha_entrega=hoy)
    elif fecha_filtro:
        ordenes = ordenes.filter(fecha_entrega=fecha_filtro)

    # 3. Buscador rápido por ID, destinatario, comuna o código Webpay
    busqueda = request.GET.get('q', '').strip()
    if busqueda:
        ordenes = ordenes.filter(
            Q(id__icontains=busqueda.replace('#', '')) |
            Q(nombre_destinatario__icontains=busqueda) |
            Q(comuna__icontains=busqueda) |
            Q(codigo_autorizacion__icontains=busqueda)
        )

    # Contadores rápidos para las tarjetas de resumen superior
    total_pendientes = Orden.objects.filter(pagado=True, estado_envio='pendiente').count()
    total_en_camino = Orden.objects.filter(pagado=True, estado_envio='en_camino').count()
    entregas_hoy = Orden.objects.filter(pagado=True, fecha_entrega=hoy).count()

    context = {
        'ordenes': ordenes,
        'estados_envio': Orden.ESTADOS_ENVIO,
        'estado_filtro': estado_filtro,
        'fecha_filtro': fecha_filtro,
        'busqueda': busqueda,
        'total_pendientes': total_pendientes,
        'total_en_camino': total_en_camino,
        'entregas_hoy': entregas_hoy,
        'hoy': hoy,
    }
    return render(request, 'admin/gestion_pedidos.html', context)


@role_required('admin')
def actualizar_estado_envio(request, orden_id):
    if request.method == 'POST':
        orden = get_object_or_404(Orden, id=orden_id, pagado=True)
        nuevo_estado = request.POST.get('estado_envio')
        
        estados_validos = dict(Orden.ESTADOS_ENVIO).keys()
        if nuevo_estado in estados_validos:
            orden.estado_envio = nuevo_estado
            orden.save(update_fields=['estado_envio'])
            messages.success(
            request,
            f"Orden #{orden.id} actualizada a '{orden.get_estado_envio_display()}'.",
            extra_tags='admin_pedidos'
        )
        else:
            messages.error(request, "Estado de envío no válido.")

    # Redirige manteniendo los filtros que el administrador tenía activos
    return redirect(request.META.get('HTTP_REFERER', 'gestion_pedidos'))

@login_required
def mis_pedidos(request):
    ordenes = Orden.objects.filter(
        usuario=request.user, 
        pagado=True
    ).prefetch_related('items').order_by('-fecha_creacion')
    
    return render(request, 'pedidos/mis_pedidos.html', {'ordenes': ordenes})

# BI 


@role_required('admin')
def panel(request):
    hoy = timezone.localdate()

    # =====================================================
    # 1. FILTROS DE FECHAS
    # =====================================================

    opciones = [
        (7, 'Últimos 7 días'),
        (30, 'Últimos 30 días'),
        (90, 'Últimos 90 días'),
        (365, 'Último año'),
    ]

    desde_param = parse_date(request.GET.get('desde', ''))
    hasta_param = parse_date(request.GET.get('hasta', ''))
    dias_param = request.GET.get('dias', '30')

    if desde_param and hasta_param and desde_param <= hasta_param:
        desde = desde_param
        hasta = hasta_param
        rango = 'personalizado'
    else:
        try:
            dias = int(dias_param)
            if dias not in [7, 30, 90, 365]:
                dias = 30
        except (ValueError, TypeError):
            dias = 30

        desde = hoy - timedelta(days=dias - 1)
        hasta = hoy
        rango = str(dias)

    duracion = (hasta - desde).days + 1

    # Periodo anterior de igual duración
    hasta_anterior = desde - timedelta(days=1)
    desde_anterior = hasta_anterior - timedelta(days=duracion - 1)

    # =====================================================
    # 2. CONSULTAS PRINCIPALES
    # =====================================================

    ordenes_periodo = Orden.objects.filter(
        fecha_creacion__date__range=(desde, hasta)
    )

    pagadas = ordenes_periodo.filter(pagado=True)

    pagadas_anterior = Orden.objects.filter(
        pagado=True,
        fecha_creacion__date__range=(desde_anterior, hasta_anterior)
    )

    resumen = pagadas.aggregate(
        ingresos=Sum('total'),
        pedidos=Count('id'),
        ticket=Avg('total'),
        envios=Sum('costo_envio')
    )

    resumen_anterior = pagadas_anterior.aggregate(
        ingresos=Sum('total'),
        pedidos=Count('id')
    )

    # Función para calcular variación porcentual
    def variacion(actual, anterior):
        if not anterior:
            return None

        return round(
            ((float(actual or 0) - float(anterior)) / float(anterior)) * 100,
            1
        )

    var_ingresos = variacion(
        resumen['ingresos'],
        resumen_anterior['ingresos']
    )

    var_pedidos = variacion(
        resumen['pedidos'],
        resumen_anterior['pedidos']
    )

    # =====================================================
    # 3. PRODUCTOS Y UNIDADES
    # =====================================================

    items = ItemOrden.objects.filter(
        orden__in=pagadas
    )

    subtotal_expr = ExpressionWrapper(
        F('precio_unitario') * F('cantidad'),
        output_field=DecimalField(max_digits=20, decimal_places=0)
    )

    items_validos = items.filter(
        precio_unitario__isnull=False,
        cantidad__isnull=False
    ).annotate(subtotal_calculado=subtotal_expr)

    unidades = items.aggregate(
        total=Sum('cantidad')
    )['total'] or 0

    # Ranking de productos
    top_productos = list(
        items_validos.values('producto_nombre')
        .annotate(
            unidades=Sum('cantidad'),
            ingresos=Sum('subtotal_calculado')
        )
        .order_by('-unidades')[:10]
    )

    # =====================================================
    # 4. VENTAS POR DÍA
    # =====================================================

    ventas_dia = pagadas.annotate(
        dia=TruncDate('fecha_creacion')
    ).values('dia').annotate(
        ingresos=Sum('total'),
        pedidos=Count('id')
    ).order_by('dia')

    ventas_dia_dict = {
        v['dia']: v for v in ventas_dia
    }

    dias_lista = [
        desde + timedelta(days=i)
        for i in range(duracion)
    ]

    datos_dias = {
        'labels': [d.strftime('%d/%m') for d in dias_lista],
        'ingresos': [
            int(ventas_dia_dict[d]['ingresos'] or 0)
            if d in ventas_dia_dict else 0
            for d in dias_lista
        ],
        'pedidos': [
            ventas_dia_dict[d]['pedidos']
            if d in ventas_dia_dict else 0
            for d in dias_lista
        ]
    }

    # =====================================================
    # 5. PEDIDOS POR DÍA DE LA SEMANA
    # =====================================================

    semana_qs = pagadas.annotate(
        dia_semana=ExtractWeekDay('fecha_creacion')
    ).values('dia_semana').annotate(
        pedidos=Count('id')
    )

    semana_dict = {
        (v['dia_semana'] + 5) % 7: v['pedidos']
        for v in semana_qs
    }

    nombres_semana = [
        'Lunes', 'Martes', 'Miércoles',
        'Jueves', 'Viernes', 'Sábado', 'Domingo'
    ]

    datos_semana = {
        'labels': nombres_semana,
        'pedidos': [
            semana_dict.get(i, 0) for i in range(7)
        ]
    }

    # =====================================================
    # 6. ESTADOS DE ENVÍO
    # =====================================================

    estados = ['pendiente', 'en_camino', 'entregado']

    datos_estados = {
        'labels': [
            dict(Orden.ESTADOS_ENVIO).get(e, e)
            for e in estados
        ],
        'valores': [
            pagadas.filter(estado_envio=e).count()
            for e in estados
        ]
    }

    # =====================================================
    # 7. CONVERSIÓN
    # =====================================================

    pedidos_pagados = pagadas.count()
    sin_pagar = ordenes_periodo.filter(pagado=False).count()
    total_ordenes = pedidos_pagados + sin_pagar

    conversion = round(
        (pedidos_pagados / total_ordenes) * 100, 1
    ) if total_ordenes else 0

    datos_conversion = {
        'labels': ['Pagados', 'Sin pagar'],
        'valores': [pedidos_pagados, sin_pagar]
    }

    # =====================================================
    # 8. VENTAS POR COMUNA
    # =====================================================

    comunas_qs = pagadas.values('comuna').annotate(
        pedidos=Count('id'),
        ingresos=Sum('total')
    ).order_by('-pedidos')[:10]

    datos_comunas = {
        'labels': [c['comuna'] for c in comunas_qs],
        'pedidos': [c['pedidos'] for c in comunas_qs],
        'ingresos': [int(c['ingresos'] or 0) for c in comunas_qs]
    }

    # =====================================================
    # 9. ENTREGAS PRÓXIMOS 14 DÍAS
    # =====================================================

    fecha_limite = hoy + timedelta(days=13)

    carga_qs = (
        Orden.objects.filter(
            pagado=True,
            fecha_entrega__range=(hoy, fecha_limite)
        )
        .values('fecha_entrega')
        .annotate(total=Count('id'))
    )

    carga_dict = {
        v['fecha_entrega']: v['total']
        for v in carga_qs
    }

    fechas_carga = [
        hoy + timedelta(days=i)
        for i in range(14)
    ]

    datos_carga = {
        'labels': [
            f.strftime('%d/%m') for f in fechas_carga
        ],
        'valores': [
            carga_dict.get(f, 0) for f in fechas_carga
        ]
    }

    # =====================================================
    # 10. CATEGORÍAS, OCASIONES Y TIPOS
    # =====================================================

    def ranking_campo(campo):
        return list(
            items_validos.exclude(**{campo: ''})
            .values(campo)
            .annotate(
                unidades=Sum('cantidad'),
                ingresos=Sum('subtotal_calculado')
            )
            .order_by('-unidades')[:10]
        )

    def datos_ranking(campo):
        resultados = ranking_campo(campo)

        return {
            'labels': [r[campo] for r in resultados],
            'unidades': [
                int(r['unidades'] or 0) for r in resultados
            ],
            'ingresos': [
                int(r['ingresos'] or 0) for r in resultados
            ]
        }

    datos_categorias = datos_ranking('categoria_nombre')
    datos_ocasiones = datos_ranking('ocasion_nombre')
    datos_tipos = datos_ranking('tipo_nombre')

    # =====================================================
    # 11. MATRIZ CATEGORÍAS VS OCASIONES
    # =====================================================

    matriz_qs = (
        items_validos
        .exclude(categoria_nombre='')
        .exclude(ocasion_nombre='')
        .values('categoria_nombre', 'ocasion_nombre')
        .annotate(unidades=Sum('cantidad'))
    )

    matriz_dict = {
        (r['categoria_nombre'], r['ocasion_nombre']): r['unidades']
        for r in matriz_qs
    }

    categorias = sorted({
        k[0] for k in matriz_dict
    })

    ocasiones = sorted({
        k[1] for k in matriz_dict
    })

    max_matriz = max(matriz_dict.values(), default=1)

    mapa = []
    for cat in categorias:
        celdas = []
        for oca in ocasiones_cols:
            v = cruce.get((cat, oca), 0)
            proporcion = v / maximo if maximo else 0
            nivel = 0 if v == 0 else min(5, int(proporcion * 5) + 1)
            celdas.append({"valor": v, "nivel": nivel})
        mapa.append({"categoria": cat, "celdas": celdas})

    for categoria in categorias:
        celdas = []

        for ocasion in ocasiones:
            valor = matriz_dict.get((categoria, ocasion), 0)

            alpha = round(
                0.08 + (valor / max_matriz) * 0.77, 2
            ) if valor else 0

            celdas.append({
                'valor': valor,
                'alpha': alpha,
                'oscuro': alpha > 0.45
            })

        mapa.append({
            'categoria': categoria,
            'celdas': celdas
        })

    # =====================================================
    # 12. PRODUCTOS MÁS VENDIDOS POR OCASIÓN
    # =====================================================

    opciones_ocasion = sorted({
        r['ocasion_nombre']
        for r in items.exclude(ocasion_nombre='')
        .values('ocasion_nombre').distinct()
    })

    ocasion_sel = request.GET.get('ocasion', '')

    items_ocasion = items_validos

    if ocasion_sel in opciones_ocasion:
        items_ocasion = items_ocasion.filter(
            ocasion_nombre=ocasion_sel
        )
    else:
        ocasion_sel = ''

    top_por_ocasion = list(
        items_ocasion.values(
            'producto_nombre', 'categoria_nombre'
        )
        .annotate(
            unidades=Sum('cantidad'),
            ingresos=Sum('subtotal_calculado')
        )
        .order_by('-unidades')[:10]
    )

    # =====================================================
    # 13. PRÓXIMAS ENTREGAS
    # =====================================================

    proximas = (
        Orden.objects.filter(
            pagado=True,
            fecha_entrega__range=(hoy, fecha_limite)
        )
        .exclude(estado_envio='entregado')
        .order_by('fecha_entrega', 'id')[:10]
    )

    # =====================================================
    # 14. INDICADORES OPERATIVOS
    # =====================================================

    por_preparar = pagadas.filter(
        estado_envio='pendiente'
    ).count()

    en_camino = pagadas.filter(
        estado_envio='en_camino'
    ).count()

    entregas_hoy = Orden.objects.filter(
        pagado=True,
        fecha_entrega=hoy
    ).count()

    # =====================================================
    # 15. CONTEXTO PARA HTML
    # =====================================================

    datos = {
        'dias': datos_dias,
        'semana': datos_semana,
        'estados': datos_estados,
        'conversion': datos_conversion,
        'productos': {
            'labels': [p['producto_nombre'] for p in top_productos],
            'unidades': [int(p['unidades'] or 0) for p in top_productos],
            'ingresos': [int(p['ingresos'] or 0) for p in top_productos],
        },
        'comunas': datos_comunas,
        'carga': datos_carga,
        'categorias': datos_categorias,
        'ocasiones': datos_ocasiones,
        'tipos': datos_tipos,
    }

    contexto = {
        'datos': datos,

        'ingresos': int(resumen['ingresos'] or 0),
        'pedidos': pedidos_pagados,
        'ticket': int(resumen['ticket'] or 0),
        'unidades': int(unidades),
        'envios': int(resumen['envios'] or 0),

        'conversion': conversion,
        'sin_pagar': sin_pagar,

        'por_preparar': por_preparar,
        'en_camino': en_camino,
        'entregas_hoy': entregas_hoy,

        'var_ingresos': var_ingresos,
        'var_pedidos': var_pedidos,

        'opciones': opciones,
        'rango': rango,
        'desde': desde.isoformat(),
        'hasta': hasta.isoformat(),

        'top_productos': top_productos,
        'top_por_ocasion': top_por_ocasion,
        'opciones_ocasion': opciones_ocasion,
        'ocasion_sel': ocasion_sel,

        'mapa': mapa,
        'ocasiones_cols': ocasiones,
        'proximas': proximas,
    }

    return render(
        request,
        'admin/panel.html',
        contexto
    )
