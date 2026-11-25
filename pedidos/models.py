from django.db import models
from tienda.models import CustomUser

# Create your models here.
# Listado oficial de comunas de la Región Metropolitana
COMUNAS_RM = [
    ('', 'Selecciona una comuna'),
    # Provincia de Santiago
    ('Santiago', 'Santiago'),
    ('Cerrillos', 'Cerrillos'),
    ('Cerro Navia', 'Cerro Navia'),
    ('Conchalí', 'Conchalí'),
    ('El Bosque', 'El Bosque'),
    ('Estación Central', 'Estación Central'),
    ('Huechuraba', 'Huechuraba'),
    ('Independencia', 'Independencia'),
    ('La Cisterna', 'La Cisterna'),
    ('La Florida', 'La Florida'),
    ('La Granja', 'La Granja'),
    ('La Pintana', 'La Pintana'),
    ('La Reina', 'La Reina'),
    ('Las Condes', 'Las Condes'),
    ('Lo Barnechea', 'Lo Barnechea'),
    ('Lo Espejo', 'Lo Espejo'),
    ('Lo Prado', 'Lo Prado'),
    ('Macul', 'Macul'),
    ('Maipú', 'Maipú'),
    ('Ñuñoa', 'Ñuñoa'),
    ('Pedro Aguirre Cerda', 'Pedro Aguirre Cerda'),
    ('Peñalolén', 'Peñalolén'),
    ('Providencia', 'Providencia'),
    ('Pudahuel', 'Pudahuel'),
    ('Quilicura', 'Quilicura'),
    ('Quinta Normal', 'Quinta Normal'),
    ('Recoleta', 'Recoleta'),
    ('Renca', 'Renca'),
    ('San Joaquín', 'San Joaquín'),
    ('San Miguel', 'San Miguel'),
    ('San Ramón', 'San Ramón'),
    ('Vitacura', 'Vitacura'),
    
    # Provincia de Talagante
    ('Padre Hurtado', 'Padre Hurtado'),
    ('Talagante', 'Talagante'),
    ('El Monte', 'El Monte'),
    ('Isla de Maipo', 'Isla de Maipo'),
    ('Peñaflor', 'Peñaflor'),
    
    # Provincia de Maipo
    ('San Bernardo', 'San Bernardo'),
    ('Buin', 'Buin'),
    ('Paine', 'Paine'),
    ('Calera de Tango', 'Calera de Tango'),
    
    # Provincia de Cordillera
    ('Puente Alto', 'Puente Alto'),
    ('Pirque', 'Pirque'),
    ('San José de Maipo', 'San José de Maipo'),
    
    # Provincia de Chacabuco
    ('Colina', 'Colina'),
    ('Lampa', 'Lampa'),
    ('Tiltil', 'Tiltil'),
]

class TarifaComuna(models.Model):
    comuna = models.CharField(max_length=100, unique=True, choices=COMUNAS_RM, verbose_name="Comuna")
    precio_envio = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Costo de Envío ($)")

    def __str__(self):
        return f"{self.comuna} (${self.precio_envio:,.0f})"

    class Meta:
        verbose_name = "Tarifa de Comuna"
        verbose_name_plural = "Tarifas por Comuna"




class Orden(models.Model):
    usuario = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes')
    email_cliente = models.EmailField(verbose_name="Correo electrónico de contacto")
    # Datos de envío y dedicatoria
    nombre_destinatario = models.CharField(max_length=100)
    telefono_destinatario = models.CharField(max_length=20,blank=True,null=True,verbose_name="Teléfono del destinatario")
    direccion_envio = models.CharField(max_length=255)
    comuna = models.CharField(max_length=100)
    costo_envio = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    nota_tarjeta = models.TextField(blank=True, null=True, help_text="Mensaje personalizado para la tarjeta de las flores")
    fecha_entrega = models.DateField()
    
    # Metadatos del pedido y totales
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=0)
    
    # Campos de control y pasarela de pago (Listos para Webpay)
    pagado = models.BooleanField(default=False)
    token_ws = models.CharField(max_length=255, blank=True, null=True, help_text="Token de Transbank Webpay")
    codigo_autorizacion = models.CharField(max_length=50, blank=True, null=True, help_text="Código de autorización si el pago es exitoso")

    @property
    def nombre_cliente_correo(self):
        """
        Devuelve el nombre del usuario si está logueado, 
        o la parte previa al '@' si compró como invitado.
        """
        if self.usuario:
            return self.usuario.first_name or self.usuario.email.split('@')[0]
        elif self.email_cliente:
            return self.email_cliente.split('@')[0]
        return "Cliente"
    
    ESTADOS_ENVIO = [
        ('pendiente', 'Pendiente de preparación'),
        ('en_camino', 'En camino a destino'),
        ('entregado', 'Entregado'),
    ]
    estado_envio = models.CharField(max_length=20, choices=ESTADOS_ENVIO, default='pendiente')

    def __str__(self):
        return f"Orden #{self.id} - Destinatario: {self.nombre_destinatario} ({'Pagado' if self.pagado else 'Pendiente'})"


class ItemOrden(models.Model):
    orden = models.ForeignKey(Orden, related_name='items', on_delete=models.CASCADE)
    
    # Patrón Snapshot
    producto_nombre = models.CharField(max_length=255)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    cantidad = models.PositiveIntegerField(default=1, null=True, blank=True)
    categoria_nombre = models.CharField(max_length=100, blank=True, default="")
    ocasion_nombre = models.CharField(max_length=100, blank=True, default="")
    tipo_nombre = models.CharField(max_length=100, blank=True, default="")

    def __str__(self):
        return f"{self.cantidad}x {self.producto_nombre} (Orden #{self.orden.id})"
    
    @property
    def subtotal(self):
        # Protección contra valores nulos para evitar errores en el admin
        if self.precio_unitario is None or self.cantidad is None:
            return 0
        return self.precio_unitario * self.cantidad