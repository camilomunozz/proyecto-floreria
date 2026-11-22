from django.urls import path
from . import views
from pedidos.views import panel

urlpatterns = [
    path('checkout/', views.iniciar_checkout, name='checkout'),
    path('exito/', views.pago_exitoso, name='pago_exitoso'),
    path('preview-email/<int:orden_id>/', views.previsualizar_correo, name='preview_email'),

    path('iniciar-pago/', views.iniciar_pago, name='iniciar_pago'),
    path('webpay/retorno/', views.webpay_retorno, name='webpay_retorno'),   

    path('mis-pedidos/', views.mis_pedidos, name='mis_pedidos'),

    path("panel/", panel, name="panel"),
]
