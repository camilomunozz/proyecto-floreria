from django.urls import path

from tienda.forms import CustomAuthenticationForm
from . import views
from django.contrib.auth import views as auth_views
from pedidos import views as pedidos_views

urlpatterns = [
    path('', views.inicio, name='inicio'),

    #catalogo
    path('catalogo/', views.catalogo_productos, name='catalogo_productos'),
    #barra de busqueda
    path('busqueda/', views.barra_busqueda, name='busqueda'),
    #productos
    path('productos/', views.lista_productos, name='lista_productos'),
    path('detalle_producto/<int:id>/', views.detalle_producto, name='detalle_producto'),
    #admin
    path('gestion/', views.admin_lista_productos, name='admin_lista_productos'),
    path('gestion/crear/', views.crear_producto, name='crear_producto'),
    path('gestion/editar/<int:id>/', views.editar_producto, name='editar_producto'),
    path('gestion/eliminar/<int:id>/', views.eliminar_producto, name='eliminar_producto'),
    path('gestion/crear_tipo/', views.crear_tipo, name='crear_tipo'),
    path('gestion/crear_categoria/', views.crear_categoria, name='crear_categoria'),
    path('gestion/crear_ocasion/', views.crear_ocasion, name='crear_ocasion'),
    path('gestion/dashboard/', views.admin_dashboard, name='admin_dashboard'),

    path('gestion/pedidos/', pedidos_views.gestion_pedidos, name='gestion_pedidos'),
    path('gestion/pedidos/<int:orden_id>/estado/', pedidos_views.actualizar_estado_envio, name='actualizar_estado_envio'),

    #PRUEBA
    

    #PRUEBA NAVBAR Y FOOTER
    path('componentes/', views.prueba_global_componentes, name='prueba_global_componentes'),

    #PRUEBA DETALLE PRODUCTO
    path('detalle_producto/', views.detalle_producto, name='detalle_producto'),
    #login y logout
    path('login/', auth_views.LoginView.as_view(
        template_name='usuarios/login.html', # Ajusta según la ruta real de tu HTML
        authentication_form=CustomAuthenticationForm
    ), name='login'),
    
    path('logout/', auth_views.LogoutView.as_view(next_page='inicio'), name='logout'), # Redirige al inicio al salir
    
    path('registro/', views.registro_view, name='registro'),
    
    path('perfil/editar/', views.editar_perfil_view, name='editar_perfil'),

]