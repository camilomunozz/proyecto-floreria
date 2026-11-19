from django import forms
from django.core.exceptions import ValidationError
from .models import *
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model


#registro usuario

User = get_user_model()

class RegistroForm(forms.ModelForm):
    # Definimos explícitamente los campos de contraseña aquí:
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'}),
        label="Contraseña"
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'}),
        label="Confirmar Contraseña"
    )

    class Meta:
        model = CustomUser
        fields = ['email']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.username = user.email  
        if commit:
            user.save()
        return user
    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        return email
######

class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Estilos y textos adaptados para pedir el correo
        self.fields['username'].widget.attrs.update({
            'class': 'form-control', 
            'placeholder': 'correo@ejemplo.com'
        })
        self.fields['username'].label = "Correo Electrónico"
        
        self.fields['password'].widget.attrs.update({
            'class': 'form-control', 
            'placeholder': '••••••••'
        })
        self.fields['password'].label = "Contraseña"

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'nombre', 'precio', 'descripcion', 'stock', 
            'tipo','categoria', 'ocasion',
            'imagen', 'disponible'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'stock': forms.NumberInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'ocasion': forms.Select(attrs={'class': 'form-select'}),
            'disponible': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'imagen': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'nombre': 'Nombre del Producto',
            'precio': 'Precio',
            'descripcion': 'Descripción', 
            'stock': 'Stock',
            'tipo': 'Tipo',
            'categoria': 'Categoría',
            'ocasion': 'Ocasión',
            'disponible': 'Disponible',
            'imagen': 'Imagen del Producto',
        }
    def clean_precio(self):
        precio = self.cleaned_data.get('precio')
        if precio is not None and precio <= 0:
            raise ValidationError("El precio debe ser un número positivo mayor que cero.")
        return precio

class TipoForm(forms.ModelForm):
    class Meta:
        model = Tipo
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class OcasionForm(forms.ModelForm):
    class Meta:
        model = Ocasion
        fields = ['nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
        }

User = get_user_model()

# Listado oficial de comunas de la Región Metropolitana
COMUNAS_RM = [
    ('', 'Selecciona tu comuna'),
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

class EditarPerfilForm(forms.ModelForm):
    comuna = forms.ChoiceField(
        choices=COMUNAS_RM,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'telefono', 'direccion', 'comuna']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tu nombre'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tu apellido'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+56912345678'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Calle y número de casa/depto'}),
        }
        labels = {
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo Electrónico',
            'telefono': 'Teléfono de Contacto',
            'direccion': 'Dirección de Despacho',
            'comuna': 'Comuna (Región Metropolitana)',
        }