
from django.urls import path
from . import views

urlpatterns = [
    # Checkout
    path('checkout/', views.iniciar_checkout, name='checkout'),
    path('exito/', views.pago_exitoso, name='pago_exitoso'),
    path(
        'preview-email/<int:orden_id>/',
        views.previsualizar_correo,
        name='preview_email'
    ),

    # Webpay
    path('iniciar-pago/', views.iniciar_pago, name='iniciar_pago'),
    path('webpay/retorno/', views.webpay_retorno, name='webpay_retorno'),

    # Pedidos
    path('mis-pedidos/', views.mis_pedidos, name='mis_pedidos'),

    # Inteligencia de negocios (BI)
    path("panel/", views.panel, name="panel"),

    # Reportes
    path(
        'panel/reporte-pdf/',
        views.exportar_reporte_pdf,
        name='exportar_reporte_pdf'
    ),
]
