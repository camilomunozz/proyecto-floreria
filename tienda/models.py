from django.db import models
from django.conf import settings

from django.contrib.auth.models import AbstractUser


# Create your models here.

class CustomUser(AbstractUser):
    # El username pasa a ser opcional para la BD, ya que usaremos el email
    username = models.CharField(max_length=150, unique=True, blank=True, null=True)
    email = models.EmailField(unique=True, verbose_name="Correo electrónico")
    
    role = models.CharField(max_length=20, default='cliente', verbose_name="Rol")
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    direccion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Dirección")
    comuna = models.CharField(max_length=100, blank=True, null=True, verbose_name="Comuna")
    
    #Carrito
    carrito_guardado = models.JSONField(default=dict, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username'] # Ya no pedirá username extra al crear superusuario

    def save(self, *args, **kwargs):
        # Asigna automáticamente el correo como username por debajo
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email

class Tipo(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name ='Tipo'
        verbose_name_plural = 'Tipos'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre
    
class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class Ocasion(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Ocasión"
        verbose_name_plural = "Ocasiones"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class Producto(models.Model):
    nombre= models.CharField(max_length=150)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    descripcion = models.TextField(blank=True, null=True)
    stock = models.PositiveIntegerField(default=0)

    tipo = models.ForeignKey(Tipo, on_delete=models.SET_NULL, null=True, blank=True, related_name='productos')
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name='productos')
    ocasion = models.ForeignKey(Ocasion, on_delete=models.SET_NULL, null=True, blank=True, related_name='productos')

    imagen = models.ImageField(upload_to='productos/', blank=True, null=True)
    disponible = models.BooleanField(default=True)
    creado_el = models.DateTimeField(auto_now_add=True)
    actualizado_el = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['-creado_el']

    def __str__(self):
        return self.nombre
    
