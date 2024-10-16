from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from django.urls import reverse
from urllib.parse import urlencode
from django.core.exceptions import ObjectDoesNotExist

from django.db.models import Q

#Para sacar totales de eventos.
from django.db.models import Sum
from django.shortcuts import render
import locale



from django.db.models import F
from collections import defaultdict

from django.utils import timezone
from datetime import timedelta

# Para tomar el from desde el settings
from django.conf import settings
from django.core.mail import EmailMessage, send_mail
import threading

# Para que muestre más detalles de un error
import traceback

# Importamos todos los modelos de la base de datos
from django.db import IntegrityError, transaction
from django.http import JsonResponse
import json

from django.utils import timezone

#APIVIEW
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny


#PARA EL PDF
from xhtml2pdf import pisa
from django.template.loader import render_to_string
import os
import tempfile
from django.core.files import File

from django.urls import reverse


from rest_framework import viewsets

from .serializers import *
from rest_framework import viewsets


#Importar el crypt
from .crypt import *

#Importar todos los modelos de la base de datos.
from .models import *

#Validar la fecha de Nacimiento
from datetime import datetime

# Para restringir las vistas
from .decorators import rol_requerido

#Enviar emails por un hilo separado
class EmailThread(threading.Thread):
    def __init__(self, subject, message, recipient_list):
        self.subject = subject
        self.message = message
        self.recipient_list = recipient_list
        threading.Thread.__init__(self)

    def run(self):
        # El correo ahora se envía como HTML
        send_mail(
            subject=self.subject,
            message='Este correo requiere un cliente compatible con HTML.',
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=self.recipient_list,
            html_message=self.message
        )

def calcular_edad(fecha_nacimiento):
    hoy = datetime.today()
    fecha_nac = datetime.strptime(fecha_nacimiento, '%Y-%m-%d')
    edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
    return edad


def index(request):
    logueo = request.session.get("logueo", False)
    menu = Categoria.objects.all()
    galeria = Galeria.objects.all()
    contexto = {'menu': menu, 'galeria': galeria, 'user': logueo}
    if logueo == False:
        return render(request, "Oasis/index.html", contexto)
    else:
        return redirect("inicio")

def login(request):
    if request.method == "POST":
        user = request.POST.get("correo")
        password = request.POST.get("clave")
		#Select * from Usuario where correo = "user" and clave = "passw"
        try:
            q = Usuario.objects.get(email = user)
            if verify_password(password, q.password):
                # Crear variable de sesión.
                request.session["logueo"] = {
                    "id": q.id,
                    "nombre": q.nombre,
                    "rol": q.rol,
                    "nombre_rol":q.get_rol_display()
                }
                messages.success(request, f"Bienvendido {q.nombre}!!")
            else:
                messages.error(request, 'Error: Usuario o contraseña incorrectos...')
            return redirect("inicio")
        except Exception as e:
            messages.error(request, f"Error: Usuario o contraseña incorrectos {e}")
            return redirect("index")
    else:
        messages.warning(request, "Error: No se enviaron datos.")
        return redirect("index")


def logout(request):
	try:
		del request.session["logueo"]
		del request.session["carrito"]
		messages.success(request, "Sesión cerrada correctamente")
		return redirect("index")
	except Exception as e:
		#messages.warning(request, "No se pudo cerrar sesión")
		return redirect("inicio")
    
def inicio(request):
    logueo = request.session.get("logueo", False)
    if logueo:
        try:
            usuario_id = request.session['logueo']['id']
            usuario = Usuario.objects.get(pk=usuario_id)
            menu = Categoria.objects.all()
            galeria = Galeria.objects.all()
            contexto = {'user': usuario, 'menu': menu, 'galeria':galeria}
            return render(request, "Oasis/index.html", contexto)
        except Usuario.DoesNotExist:
            messages.error(request, "El usuario no existe")
    else:
        return redirect("index")
    

def recuperar_contrasena_template(request):
    logueo = request.session.get("logueo", False)
    user = None
    if logueo:
        user = Usuario.objects.get(pk=logueo["id"])

    contexto = {'user': user}
    return render(request, 'Oasis/recuperar_contrasena/recuperar_contrasena.html', contexto)


def enviar_correo_recuperar(usuario, codigo, link):
    try:
        destinatario = usuario.email
        contexto = {'usuario': usuario, 'codigo': codigo, 'link': link}
        mensaje_html = render_to_string('Oasis/emails/plantillas/recuperar_contrasena_template.html', contexto)
        
        email = EmailMessage(
            subject='Recuperar Contraseña en Oasis Night Club',
            body=mensaje_html,
            from_email=settings.EMAIL_HOST_USER,
            to=[destinatario],
        )
        email.content_subtype = 'html'
        email.send()
    except Exception as e:
        print(f"Error al enviar el correo de reserva: {e}")


def recuperar_contrasena(request):
    if request.method == "POST":
        correo = request.POST.get("email")
        try:
            q = Usuario.objects.get(email=correo)
            from random import randint
            import base64
            codigo = base64.b64encode(str(randint(100000, 999999)).encode("ascii")).decode("ascii")
            q.token_recuperar = codigo
            q.save()

            link = "http://127.0.0.1:8000/verificar_recuperar/?correo="+q.email

            threading.Thread(target=enviar_correo_recuperar, args=(q,codigo,link)).start()

            messages.success(request, "El correo para recuperar contraseña ¡ya fué enviado!")

        except Usuario.DoesNotExist:
            messages.error(request, "No existe el usuario....")
        
        return redirect("form_recuperar_contrasena")
    else:
        return redirect("form_recuperar_contrasena")


def verificar_recuperar(request):
    logueo = request.session.get("logueo", False)
    user = None
    if logueo:
        user = Usuario.objects.get(pk=logueo["id"])

    if request.method == "POST":
        if request.POST.get("check"):
            correo = request.POST.get("correo")
            q = Usuario.objects.get(email=correo)

            c1 = request.POST.get("nueva1")
            c2 = request.POST.get("nueva2")

            if c1 == c2:
                q.password = hash_password(c1)
                q.token_recuperar = ""
                q.save()

                messages.success(request, "Contraseña guardada correctamente.")
                return redirect("index")
            
            else:
                messages.warning(request, "Las contraseñas nuevas no coinciden.")

                url = reverse("verificar_recuperar")
                query_params = urlencode({"correo": correo})
                full_url = f"{url}?{query_params}"
                
                return redirect(full_url)
        else:
            correo = request.POST.get("correo")
            codigo = request.POST.get("codigo")
            q = Usuario.objects.get(email=correo)
            if (q.token_recuperar == codigo) and q.token_recuperar != "":
                contexto = {"check": "ok", "correo":correo, 'user': user}
                return render(request, "Oasis/recuperar_contrasena/verificar_recuperar.html", contexto)
            else:
                messages.error(request, "Código incorrecto")
                
                url = reverse("verificar_recuperar")
                query_params = urlencode({"correo": correo})
                full_url = f"{url}?{query_params}"
                
                return redirect(full_url)
    else:
        correo = request.GET.get("correo")
        contexto = {"correo":correo, 'user': user}
        return render(request, "Oasis/recuperar_contrasena/verificar_recuperar.html", contexto)










def registro(request):
    logueo = request.session.get("logueo", False)
    user = None
    if logueo:
        user = Usuario.objects.get(pk=logueo["id"])

    contexto = {'user': user}
    return render(request, 'Oasis/registro/registro.html', contexto)



def crear_usuario_registro(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        email = request.POST.get('email')
        cedula = request.POST.get('cedula')
        fecha_nacimiento = request.POST.get('fechaNacimiento')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.warning(request, "Las contraseñas no coinciden")
            return redirect("registro")

        if Usuario.objects.filter(email=email).exists():
            messages.warning(request, "El correo ya está registrado")
            return redirect("registro")

        if Usuario.objects.filter(cedula=cedula).exists():
            messages.warning(request, "La cédula ya está registrada")
            return redirect("registro")

        edad = calcular_edad(fecha_nacimiento)
        if edad < 18:
            messages.warning(request, "Debes ser mayor de 18 años para registrarte")
            return redirect("registro")
        
        try:
            q = Usuario.objects.create(
                nombre=nombre,
                fecha_nacimiento=fecha_nacimiento,
                email=email,
                cedula=cedula,
                password=hash_password(password1)
            )
            q.save()
            messages.success(request, "Usuario creado exitosamente")
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return redirect("registro")


#TÉRMINOS Y CONDICIONES
def terminos_condiciones(request):
    return render(request, 'Oasis/terminos_condiciones/tyc.html')



#PERFIL
def ver_perfil(request):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])

    ruta = ""
    if user.rol == 4:
        ruta = "Oasis/front_usuario/front_usuario_perfil.html"
    else:
        ruta = "Oasis/login/perfil.html"

    #Consultamos en base de datos el ID del usuario logueado
    q = Usuario.objects.get(pk = logueo["id"])
    roles = Usuario.ROLES
    estado = Usuario.ESTADO
    contexto = {'user': q, 'roles': roles, 'estado':estado, 'user':user, 'url': 'Perfil'}
    return render(request, ruta, contexto)

def editar_perfil(request, id):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        fecha_nacimiento = request.POST.get('fechaNacimiento')
        email = request.POST.get('email')
        cedula = request.POST.get('cedula')
        foto_nueva = request.FILES.get('foto_nueva')

        if Usuario.objects.filter(email=email).exclude(pk=id).exists():
            messages.warning(request, "Ya existe otro usuario con ese correo.")
            return redirect("ver_perfil")

        if Usuario.objects.filter(cedula=cedula).exclude(pk=id).exists():
            messages.warning(request, "Ya existe otro usuario con esa cedula.")
            return redirect("ver_perfil")

        edad = calcular_edad(fecha_nacimiento)
        if edad < 18:
            messages.warning(request, "Debes ser mayor de 18 años.")
            return redirect("ver_perfil")

        try:
            q = Usuario.objects.get(pk = id)
            q.nombre = nombre
            q.email = email
            q.fecha_nacimiento = fecha_nacimiento
            q.cedula = cedula
            
            if foto_nueva:
                q.foto = foto_nueva

            q.save()
            messages.success(request, "Usuario actualizado correctamente")
        except Exception as e:
            messages.error(request,f'Error: {e}')
    else:
        messages.warning(request,'No se enviaron datos')

    return redirect('ver_perfil')


#CAMBIAR CONTRASEÑA

def cambiar_clave(request):
    if request.method == "POST":
        logueo = request.session.get("logueo", False)
        q = Usuario.objects.get(pk=logueo["id"])

        c1 = request.POST.get("nueva1")
        c2 = request.POST.get("nueva2")

        #Puedes intentar cambiando "Clave" por "Password" - Sale un error diferente. JAJAJA
        if verify_password(request.POST.get("clave"), q.password):
            if c1 == c2:
                #Cambiar clave en DB
                q.password = hash_password(c1)
                q.save()
                messages.success(request, "Contraseña cambiada correctamente!")
                return redirect("ver_perfil")
            else:
               messages.info(request, "Las contraseñas nuevas no coinciden...")
        else:
            messages.error(request, "Contraseña actual inválida...")
    else:
        messages.warning(request, "Error: No se enviaron datos...")
    
    return redirect('ver_perfil')


@rol_requerido([4])
def entradas_usuario(request):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    entrada = CompraEntrada.objects.filter(usuario = logueo["id"])

    if not entrada:
        contexto = {'entrada_info': None, 'user': user, 'url': 'entradas'}
        return render(request, "Oasis/front_usuario/front_usuario_entradas.html", contexto)

    evento_info = [Evento.objects.get(id=entrada.evento.id) for entrada in entrada]
    
    entradas_info = []
    for entrada, evento in zip(entrada, evento_info):
        entradas_info.append({'entrada': entrada, 'evento': evento})

    contexto = {'entrada_info': entradas_info, 'user': user, 'url':'entradas'}
    return render(request, "Oasis/front_usuario/front_usuario_entradas.html", contexto)

def entradas_usuario_info(request, id):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk=logueo["id"])
    
    try:
        compra_entrada = CompraEntrada.objects.get(pk=id, usuario=logueo["id"])
        qr_entradas = EntradasQR.objects.filter(compra=compra_entrada.id)

        evento = Evento.objects.get(pk=compra_entrada.evento.id)
        
        contexto = {'compra': compra_entrada, 'qr_entradas': qr_entradas, 'evento': evento, 'user': user, 'url':'entradas_info'}
        return render(request, "Oasis/front_usuario/front_usuario_entradas_info.html", contexto)
    
    except CompraEntrada.DoesNotExist:
        messages.error(request, f'La compra de entrada con el ID {id} no existe o no pertenece al usuario actual.')
        return redirect('entradas_usuario')
    

@rol_requerido([4])
def reservas_usuario(request):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    reserva = Reserva.objects.filter(usuario = logueo["id"])

    if not reserva:
        contexto = {'reservas_info': None, 'user': user, 'url': 'reservas'}
        return render(request, "Oasis/front_usuario/front_usuario_reservas.html", contexto)

    evento_info = [Evento.objects.get(id=reserva.evento.id) for reserva in reserva]
    
    reservas_info = []
    for reserva, evento in zip(reserva, evento_info):
        reservas_info.append({'reserva': reserva, 'evento': evento})

    contexto = {'reservas_info': reservas_info, 'user': user, 'url': 'reservas'}
    return render(request, "Oasis/front_usuario/front_usuario_reservas.html", contexto)

def reservas_usuario_info(request, id):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk=logueo["id"])
    
    try:
        reserva = Reserva.objects.get(pk=id, usuario=logueo["id"])
        evento = Evento.objects.get(pk=reserva.evento.id)
        
        contexto = {'reserva': reserva, 'evento': evento, 'user': user, 'url': 'reservas_info'}
        return render(request, "Oasis/front_usuario/front_usuario_reservas_info.html", contexto)
    except CompraEntrada.DoesNotExist:
        messages.error(request, f'La compra de entrada con el ID {id} no existe o no pertenece al usuario actual.')
        return redirect('reservas_usuario')


#USUARIOS
@rol_requerido([1])
def guInicio(request):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    q = Usuario.objects.filter(estado=1)

    for usuario in q:
        usuario.cantidad_reservas = Reserva.objects.filter(usuario=usuario).count()

    for usuario in q:
        usuario.cantidad_pedidos = HistorialPedido.objects.filter(usuario=usuario).count()

    usuarioAdmin = Usuario.objects.filter(rol=1).count()
    usuarioBartender = Usuario.objects.filter(rol=2).count()
    usuarioMesero = Usuario.objects.filter(rol=3).count()
    usuarioCliente = Usuario.objects.filter(rol=4).count()
    contexto = {'data': q,  
    'user': user, 
    'roles':Usuario.ROLES, 
    'estado':Usuario.ESTADO,
    'clientes':usuarioCliente, 
    'administradores':usuarioAdmin, 
    'bartenders':usuarioBartender, 
    'meseros':usuarioMesero,
    'url': "Gestion_Usuarios" 
    }
    return render(request, "Oasis/usuarios/guInicio.html", contexto)


@rol_requerido([1])
def guUsuariosCrear(request):
    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre')
            fecha_nacimiento = request.POST.get('fechaNacimiento')
            email = request.POST.get('email')
            password = request.POST.get('password')
            cedula = request.POST.get('cedula')
            foto = request.FILES.get('foto')
            rol = int(request.POST.get('rol'))

            if foto is None:
                foto = "Img_usuarios/default.png"

            try:
                cedula = int(cedula)
                if cedula <= 0 or len(str(cedula)) != 10:
                    messages.warning(request, "La cédula debe ser mayor a 0 y tener 10 dígitos")
                    return redirect("guInicio")
            except ValueError:
                messages.warning(request, "La cédula debe ser un número válido")
                return redirect("guInicio")


            if Usuario.objects.filter(email=email).exists():
                messages.warning(request, "El correo ya está registrado")
                return redirect("guInicio")

            if Usuario.objects.filter(cedula=cedula).exists():
                messages.warning(request, "La cedula ya está registrada")
                return redirect("guInicio")
            
            edad = calcular_edad(fecha_nacimiento)
            if edad < 18:
                messages.warning(request, "Debe ser mayor de 18 años para registrarse")
                return redirect("guInicio")
            
            q = Usuario(
                nombre=nombre,
                fecha_nacimiento=fecha_nacimiento,
                email=email,
                password=hash_password(password),
                rol=rol,
                cedula=cedula,
                foto=foto,
            )

            q.save()
            messages.success(request, "Usuario creado correctamente")
        except Exception as e:
            messages.error(request, f'Error: {e}')
    else:
        messages.warning(request, 'No se enviaron datos')

    return redirect('guInicio')


@rol_requerido([1])
def guUsuariosEliminados(request, id):
    try:
        q = Usuario.objects.get(pk = id)
        q.delete()
        messages.success(request, 'Usuario eliminado correctamente!!')
    except Exception as e:
        messages.error(request,f'Error: {e}')

    return redirect('guInicio')


@rol_requerido([1])
def guUsuariosActualizar(request, id):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        fecha_nacimiento = request.POST.get('fechaNacimiento')
        email = request.POST.get('email')
        # password = request.POST.get('password')
        cedula = request.POST.get('cedula')
        rol = request.POST.get('rol')
        foto_nueva = request.FILES.get('foto_nueva')

        try:
            cedula = int(cedula)
            if cedula <= 0 or len(str(cedula)) != 10:
                messages.warning(request, "La cédula debe ser mayor a 0 y tener 10 dígitos")
                return redirect("guInicio")
        except ValueError:
            messages.warning(request, "La cédula debe ser un número válido")
            return redirect("guInicio")

        if Usuario.objects.filter(email=email).exclude(pk=id).exists():
            messages.warning(request, "El correo ya está registrado por otro usuario")
            return redirect("guInicio")

        if Usuario.objects.filter(cedula=cedula).exclude(pk=id).exists():
            messages.warning(request, "La cédula ya está registrada por otro usuario")
            return redirect("guInicio")
        
        edad = calcular_edad(fecha_nacimiento)
        if edad < 18:
            messages.warning(request, "Debe ser mayor de 18 años para registrarse")
            return redirect("guInicio")

        try:
            q = Usuario.objects.get(pk=id)
            q.nombre = nombre
            q.email = email
            # q.password = hash_password(password)
            q.fecha_nacimiento = fecha_nacimiento
            q.rol = rol
            q.cedula = cedula
            
            if foto_nueva:
                q.foto = foto_nueva

            q.save()
            messages.success(request, "Usuario actualizado correctamente")
        except Exception as e:
            messages.error(request,f'Error: {e}')
    else:
        messages.warning(request,'No se enviaron datos')

    return redirect('guInicio')


@rol_requerido([1])
def gu_reservas_usuario(request, id):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    
    usuario_reservas = Usuario.objects.get(pk=id)
    try:
        q = Reserva.objects.filter(usuario = id)
    except Exception as e:
        messages.error(request, f'Error: {e}')

    return render(request, "Oasis/usuarios/guReservasUsuario.html", {'user': user, 'usuarioReserva': usuario_reservas, 'reservas' : q})


@rol_requerido([1])
def gu_historial_pedidos_usuario(request, id):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    
    usuario_historial_pedidos = Usuario.objects.get(pk=id)
    try:
        historial_pedidos = HistorialPedido.objects.filter(usuario=usuario_historial_pedidos).order_by('-fecha')
        
        detalles_pedidos = []
        for historial_pedido in historial_pedidos:
            detalles = HistorialDetallePedido.objects.filter(historial_pedido=historial_pedido)
            detalles_pedidos.append({
                'pedido': historial_pedido,
                'detalles': detalles
            })

        total_pedidos = historial_pedidos.count()
            
        contexto = {'user':user, 'usuario_historial_pedidos':usuario_historial_pedidos, 'detalles_pedidos': detalles_pedidos, 'total_pedidos': total_pedidos}

        return render(request, "Oasis/usuarios/guHistorialPedidos.html", contexto)
    
    except Exception as e:
        messages.error(request, f'Error: {e}')
    

@rol_requerido([1])
def guUsuariosBloqueados(request):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    usuarios_bloqueados = Usuario.objects.filter(estado=2)

    info_bloqueo = []

    for usuario_bloqueado in usuarios_bloqueados:
        info_bloqueo.append({
            'usuario_bloqueado': usuario_bloqueado,
            'bloqueo': Bloqueo.objects.get(usuario=usuario_bloqueado),
        })


    contexto = {'user':user, 'url':'Usuarios_Bloqueados', 'data': usuarios_bloqueados, 'info_bloqueo': info_bloqueo}
    return render(request, "Oasis/usuarios/guUsuariosBloqueados.html", contexto)


@rol_requerido([1])
def guBloquearUsuario(request, id):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])

    if request.method == 'POST':
        motivo = request.POST.get('motivo')
    else:
        messages.warning(request,'No se enviaron datos')

    try:
        q = Usuario.objects.get(pk = id)
        q.estado = 2
        q.save()

        bloqueado = Bloqueo(
            usuario = q,
            motivo = motivo,
            fecha_bloqueo = timezone.now(),
            realizado_por = user
        )

        bloqueado.save()
        messages.success(request, 'Usuario bloqueado correctamente!!')
    except Exception as e:
        messages.error(request,f'Error: {e}')

    return redirect('guInicio')


@rol_requerido([1])
def guDesbloquearUsuario(request, id):
    try:
        q = Bloqueo.objects.get(pk = id)

        q.usuario.estado = 1
        q.usuario.save()

        q.delete()

        messages.success(request, 'Usuario desbloqueado correctamente!!')
    except Exception as e:
        messages.error(request, f'Error: {e}')

    return redirect('guUsuariosBloqueados')



#PRODUCTOS
@rol_requerido([1])
def invProductos(request):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    q = Producto.objects.all()
    categories = Categoria.objects.all()
    contexto = {'data' : q, 'user':user,  'categories':categories, 'url': "Gestion_Productos" }
    return render(request, "Oasis/inventario/invProductos.html", contexto)


@rol_requerido([1])
def crearProducto(request):
    if request.method == "POST":
        try:
            nom = request.POST.get('nombre')
            desc = request.POST.get('descripcion')
            cat_id = int(request.POST.get('categoria'))
            inventario = int(request.POST.get('inventario'))
            pre = request.POST.get('precio')
            foto = request.FILES.get('foto')

            cat = Categoria.objects.get(pk=cat_id)
            
            if foto == None:
                foto = "Img_productos/default.png"

            if int(pre) <= 0:
                messages.warning(request, "El precio debe ser mayor a 0")
                return redirect("Productos")
            
            if inventario <= 0:
                messages.warning(request, "El inventario debe ser mayor a 0")
                return redirect("Productos")

            if Producto.objects.filter(nombre=nom).exists():
                messages.warning(request, "Ya existe un producto con ese nombre")
                return redirect("Productos")

            q = Producto(
                nombre=nom,
                descripcion=desc,
                categoria=cat,
                inventario=inventario,
                precio=pre,
                foto=foto,
            )
            q.save()
            messages.success(request, "Producto Agregado Correctamente!")
        except Exception as e:
            messages.error(request, f'Error: {e}')
    else:
        messages.warning(request, f'Error: No se enviaron datos...')

    return redirect('Productos')


@rol_requerido([1])
def eliminarProducto(request, id):
    try:
        q = Producto.objects.get(pk = id)

        if DetallePedido.objects.filter(producto = q).exists():
            messages.warning(request, "No se puede eliminar el producto porque tiene pedidos")
            return redirect('Productos')

        q.delete()
        messages.success(request, "Producto Eliminado Correctamente!")
    except Exception as e:
        messages.error(request, f'Error: {e}')
    
    return redirect('Productos')


@rol_requerido([1])
def actualizarProducto(request, id):
    if request.method == "POST":
        cat = Categoria.objects.get(pk=request.POST.get('categoria'))
        nom = request.POST.get('nombre')
        desc = request.POST.get('descripcion')
        inventario = int(request.POST.get('inventario'))
        precio_str = request.POST.get('precio')
        precio_str = precio_str.replace(',', '.')
        pre = float(precio_str)
        foto_nueva = request.FILES.get('foto_nueva')

        if int(pre) <= 0:
            messages.warning(request, "El precio debe ser mayor a 0")
            return redirect("Productos")
        
        if inventario <= 0:
            messages.warning(request, "El inventario debe ser mayor a 0")
            return redirect("Productos")

        if Producto.objects.filter(nombre=nom).exclude(pk=id).exists():
            messages.warning(request, "Ya existe otro producto con ese nombre")
            return redirect("Productos")

        try:
            q = Producto.objects.get(pk=id)
            q.nombre = nom
            q.categoria = cat
            q.descripcion = desc
            q.inventario = inventario
            q.precio = pre

            if foto_nueva:
                q.foto = foto_nueva

            q.save()
            messages.success(request, "Producto Actualizado Correctamente!")

        except Exception as e:
            messages.error(request, f'Error: {e}')

    else:
        messages.warning(request, f'Error: No se enviaron datos...')

    return redirect('Productos')


@rol_requerido([1])
def invDetalleProducto(request, id):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    producto = Producto.objects.get(pk = id)
    categories = Categoria.objects.all()
    contexto = {'user':user, 'producto': producto, 'categories': categories,'url': 'Inv_Detalle_Producto'}
    return render(request, 'Oasis/inventario/invDetalleProducto.html', contexto)


@rol_requerido([2, 1])
def peInicio(request):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk=logueo["id"])

    pedidos = Pedido.objects.all().order_by('fecha')

    detalles_pedidos = []
    for pedido in pedidos:
        detalles = DetallePedido.objects.filter(pedido=pedido)
        detalles_activos_count = detalles.filter(estado='Activo').count()
        detalles_pedidos.append({
            'pedido': pedido,
            'detalles': detalles,
            'detalles_activos_count': detalles_activos_count
        })

    total_preparacion = 0
    for pedido in pedidos:
        if pedido.estado == pedido.PREPARACION:
            total_preparacion += 1

    contexto = {
        'user': user,
        'detalles_pedidos': detalles_pedidos,
        'total_preparacion': total_preparacion,
        'url': "Gestion_Pedidos"
    }
    return render(request, "Oasis/pedidos/peInicio.html", contexto)


@rol_requerido([3, 1])
def peGestionMesas(request):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    mesas = Mesa.objects.all()
    mesas_activas = Mesa.objects.filter(estado='Activa').count()
    mesas_disponibles = Mesa.objects.filter(estado='Disponible').count()
    contexto = {'user':user, 'mesas':mesas, 'mesas_activas': mesas_activas, 'mesas_disponibles':mesas_disponibles, 'url': "Mesas"}
    return render (request, "Oasis/pedidos/peGestionMesas.html", contexto)


@rol_requerido([3, 1])
def pedidoEmpleado(request, id):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk=logueo["id"])
    carrito = request.session.get("carrito", [])
    mesa = Mesa.objects.get(pk=id)
    categorias = Categoria.objects.all()

    cat = request.GET.get("cat")

    if cat is not None:
        cat = int(cat)
        c = Categoria.objects.get(pk=cat)
        productos = Producto.objects.filter(categoria=c)
    else:
        productos = Producto.objects.all()

    contexto = {'user': user, 'productos': productos, 'mesa': mesa, 'carrito': carrito, 'categorias': categorias, 'cat': cat, 'url': "Agregar_Pedido"}
    return render(request, "Oasis/pedidos/pedidoEmpleado.html", contexto)



#MESAS
@rol_requerido([1])
def mesaInicio(request):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    q = Mesa.objects.all()
    contexto = {'data' : q , 'user':user, 'url': "Gestion_Mesas"}
    return render(request, "Oasis/mesas/mesasInicio.html", contexto)


@rol_requerido([1])
def crearMesa(request):
    if request.method == "POST":
        try:
            nom = request.POST.get('nombre')
            cap = int(request.POST.get('capacidad'))
            precio = int(request.POST.get('precio'))

            if precio <= 0:
                messages.warning (request, 'El precio de cada mesa debe ser mayor a 0.')
                return redirect('Mesas')
            
            if Mesa.objects.filter(nombre=nom).count() == 0:
                if 4 <= cap <= 8:
                    q = Mesa(
                    nombre = nom,
                    capacidad = cap,
                    precio = precio,
                    usuario = None,
                    )
                    q.save()
                    messages.success(request, "Mesa Registrada Correctamente!")
                else:
                    messages.warning (request, f'La capacidad de cada mesa debe ser mayor a 4 o menor a 8.')
            else:
                messages.warning (request, f'Esta mesa ya esta creada en el sistema.')
        except Exception as e:
            messages.error(request, f'Error: {e}')
        return redirect('Mesas')
    else:
        messages.warning (request, f'Error: No se enviaron datos...')
        return redirect('Mesas')




@rol_requerido([1])
def mesaActualizar(request, id):
    if request.method == "POST":
        nom = request.POST.get('nombre')
        cap = int(request.POST.get('capacidad'))
        precio = int(request.POST.get('precio'))
        try:
            if Mesa.objects.filter(nombre=nom).exclude(pk=id).exists():
                messages.warning(request, 'Esta mesa ya está creada en el sistema con otro ID.')

            elif cap > 9 or cap < 4:
                messages.warning (request, 'La capacidad de cada mesa debe ser mayor a 4 o menor a 8')
            
            elif precio <= 0:
                messages.warning (request, 'El precio de cada mesa debe ser mayor a 0.')
                return redirect('Mesas')
            
            else:
                q = Mesa.objects.get(pk=id)
                q.nombre = nom
                q.capacidad = cap
                q.precio = precio
                q.save()
                messages.success(request, "Mesa Actualizada Correctamente!")
        except Exception as e:
            messages.error(request, f'Error: {e}')

    else:
        messages.warning (request, f'Error: No se enviaron datos...')
        
    return redirect('Mesas')



@rol_requerido([1])
def eliminarMesa(request, id):
    try:
        q = Mesa.objects.get(pk = id)

        if q.estado == "Activa":
            messages.error(request, 'No puedes eliminar una mesa que tiene pedidos activos.')
            return redirect('Mesas')
        
        if q.estado_reserva == "Reservada":
            messages.error(request, 'No puedes eliminar una mesa que tiene reservas hechas.')
            return redirect('Mesas')

        if HistorialPedido.objects.filter(mesa=q).exists():
            messages.error(request, 'No puedes eliminar una mesa que tiene historial de pedidos hechos, primero elimina el historial.')
            return redirect('Mesas')

        
        q.delete()
        messages.success(request, "Mesa Eliminada Correctamente!")
    except Exception as e:
        messages.error(request, f'Error: {e}')
    
    return redirect('Mesas')



@rol_requerido([1])
def reservasMesa(request, id):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    
    try:
        q = Reserva.objects.filter(mesa = id)
    except Exception as e:
        messages.error(request, f'Error: {e}')

    return render(request, "Oasis/mesas/reservasMesa.html", {'user': user, 'mesa': Mesa.objects.get(pk = id),'reservas' : q, 'url': "reservasMesa"})



#EVENTOS

@rol_requerido([1])
def eveInicio(request):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    q = Evento.objects.filter(estado=True)

    contexto = {'data' : q, 'user':user, 'url': "Gestion_Eventos"}
    return render(request, "Oasis/eventos/eveInicio.html", contexto)


@rol_requerido([1])
def crearEvento(request):
    if request.method == "POST":
        try:
            nom = request.POST.get('nombre')
            date = request.POST.get('fecha')
            time = request.POST.get('hora_incio')
            general = request.POST.get('entrada_general')
            vip = request.POST.get('entrada_vip')
            aforo = request.POST.get('aforo')
            desc = request.POST.get('descripcion')
            flyer = request.FILES.get('flyer')

            if flyer == None:
                flyer = "Img_eventos/default.png"

            if Evento.objects.filter(nombre=nom, fecha=date).exists():
                for i in Evento.objects.filter(nombre=nom, fecha=date):
                    if i.estado == True:
                        messages.warning(request, 'Este evento ya está creado en el sistema para esta fecha.')
                        return redirect('Eventos')
            
            if date < datetime.now().strftime("%Y-%m-%d"):
                messages.warning (request, 'La fecha debe ser mayor o igual a la actual.')
                return redirect('Eventos')
            
            if int(general) <= 0:
                messages.warning (request, 'La entrada general debe ser mayor a 0.')
                return redirect('Eventos')
            
            if int(vip) <= 0:
                messages.warning (request, 'La entrada VIP debe ser mayor a 0.')
                return redirect('Eventos')
            
            if int(aforo) <= 0:
                messages.warning (request, 'El aforo debe ser mayor a 0.')
                return redirect('Eventos')

            # INSERT INTO Evento VALUES (nom, date, time, desc, foto)
            q = Evento(
                nombre = nom,
                fecha = date,
                hora_incio = time,
                precio_entrada = general,
                precio_vip = vip,
                aforo = aforo,
                descripcion = desc,
                foto = flyer
            )
            q.save()
            messages.success(request, "Evento Creado Correctamente!")
        except Exception as e:
            messages.error(request, f'Error: {e}')
        return redirect('Eventos')
    
    else:
        messages.warning (request, f'Error: No se enviaron datos...')
        return redirect('Eventos')


@rol_requerido([1])
def enviar_correo_cancelacion_evento_reserva(reserva):
    try:
        destinatario = reserva.usuario.email
        contexto = {'reserva': reserva}
        mensaje_html = render_to_string('Oasis/emails/plantillas/cancelacion_evento_reserva_email_template.html', contexto)
        
        email = EmailMessage(
            subject='Cancelación de Evento en Oasis Night Club',
            body=mensaje_html,
            from_email=settings.EMAIL_HOST_USER,
            to=[destinatario],
        )
        email.content_subtype = 'html'
        email.send()
    except Exception as e:
        print(f"Error al enviar el correo de reserva: {e}")  # Loguear el error



# Función para enviar correos de cancelación de entradas
@rol_requerido([1])
def enviar_correo_cancelacion_evento_entrada(entrada, qr_entradas):
    try:
        destinatario = entrada.usuario.email
        contexto = {'compra': entrada, 'entradas': qr_entradas}
        mensaje_html = render_to_string('Oasis/emails/plantillas/cancelacion_evento_entrada_email_template.html', contexto)
        
        email = EmailMessage(
            subject='Cancelación de Evento en Oasis Night Club',
            body=mensaje_html,
            from_email=settings.EMAIL_HOST_USER,
            to=[destinatario],
        )
        email.content_subtype = 'html'
        email.send()
    except Exception as e:
        print(f"Error al enviar el correo de entrada: {e}")  # Loguear el error


@rol_requerido([1])
def eliminarEvento(request, id):
    try:
        evento = Evento.objects.get(pk=id)
        evento.estado = False
        evento.save()

        # Procesar las reservas y entradas asociadas al evento
        reservas = Reserva.objects.filter(evento=evento)
        entradas = CompraEntrada.objects.filter(evento=evento)

        # Si hay reservas, enviar correos de cancelación en segundo plano
        for reserva in reservas:
            threading.Thread(target=enviar_correo_cancelacion_evento_reserva, args=(reserva,)).start()

        # Si hay entradas, enviar correos de cancelación en segundo plano
        for entrada in entradas:
            qr_entradas = EntradasQR.objects.filter(compra=entrada)
            threading.Thread(target=enviar_correo_cancelacion_evento_entrada, args=(entrada, qr_entradas)).start()

        messages.success(request, "Evento Eliminado Correctamente!")

    except Exception as e:
        messages.error(request, f'Error: {e}')
    
    return redirect('Eventos')


@rol_requerido([1])
def eliminarEventoDefinitivo(request, id):
    try:
        evento = Evento.objects.get(pk=id)

        if CompraEntrada.objects.filter(evento=evento).exists():
            messages.warning(request, "No puedes eliminar un evento que tiene entradas por resolver")
            return redirect('EventosEliminados')
        
        elif Reserva.objects.filter(evento=evento).exists():
            messages.warning(request, "No puedes eliminar un evento que tiene reservas por resolver")
            return redirect('EventosEliminados')
        
        else:
            evento.delete()
            messages.success(request, "Evento eliminado correctamente")
            return redirect('EventosEliminados')
    except Exception as e:
        messages.error(request, f'Error: {e}')
        return redirect('EventosEliminados')



@rol_requerido([1])
def actualizarEvento(request, id):
    if request.method == "POST":
        nom = request.POST.get('nombre')
        date = request.POST.get('fecha')
        time = request.POST.get('hora_incio')
        general = request.POST.get('entrada_general')
        vip = request.POST.get('entrada_vip')
        aforo = request.POST.get('aforo')
        desc = request.POST.get('descripcion')
        foto_nueva = request.FILES.get('foto_nueva')

        if Evento.objects.filter(nombre=nom, fecha=date).exclude(pk=id).exists():
            for i in Evento.objects.filter(nombre=nom, fecha=date).exclude(pk=id):
                if i.estado == True:
                    messages.warning(request, 'Este evento ya está creado en el sistema para esta fecha.')
                    return redirect('Eventos')
        
        if date < datetime.now().strftime("%Y-%m-%d"):
            messages.warning (request, 'La fecha debe ser mayor o igual a la actual.')
            return redirect('Eventos')
        
        if int(general) <= 0:
            messages.warning (request, 'La entrada general debe ser mayor a 0.')
            return redirect('Eventos')
        
        if int(vip) <= 0:
            messages.warning (request, 'La entrada VIP debe ser mayor a 0.')
            return redirect('Eventos')
        
        if int(aforo) <= 0:
            messages.warning (request, 'El aforo debe ser mayor a 0.')
            return redirect('Eventos')


        try:
            q = Evento.objects.get(pk=id)
            q.nombre = nom
            q.fecha = date
            q.hora_incio = time
            q.precio_entrada = general
            q.precio_vip = vip
            q.aforo = aforo
            q.descripcion = desc

            if foto_nueva:
                q.foto = foto_nueva

            q.save()
            messages.success(request, "Evento Actualizado Correctamente!")

        except Exception as e:
            messages.error(request, f'Error: {e}')

    else:
        messages.warning (request, f'Error: No se enviaron datos...')
        
    return redirect('Eventos')



@rol_requerido([1])
def detalleEvento(request, id):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    evento = Evento.objects.get(pk = id)
    contexto = {'evento': evento, 'user':user, 'url': "Gestion_Eventos"}
    return render(request, 'Oasis/eventos/eveDetalleEvento.html', contexto)



@rol_requerido([1])
def eveEntradas(request, id):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])

    evento = Evento.objects.get(pk = id)
    entradas = CompraEntrada.objects.filter(evento = id)

    precio_entrada_general = evento.precio_entrada
    precio_entrada_vip = evento.precio_vip

    for entrada in entradas:
        entrada.total_entradas = entrada.entrada_general + entrada.entrada_vip
        entrada.subtotal_general = entrada.entrada_general * precio_entrada_general
        entrada.subtotal_vip = entrada.entrada_vip * precio_entrada_vip
        entrada.save()

    contexto = {'evento': evento, 'user':user, 'entradas': entradas, 'url': "Gestion_Eventos"}

    return render(request, 'Oasis/eventos/eveEntradas.html', contexto)



@rol_requerido([1])
def enviar_correo_cancelacion_entrada(entrada, total_entradas):
    try:
        destinatario = entrada.usuario.email
        contexto = {
            'compra': entrada,
            'total_entradas': total_entradas
        }
        mensaje_html = render_to_string('Oasis/emails/plantillas/cancelacion_entrada_email_template.html', contexto)

        subject = "Cancelación de Entrada en Oasis Night Club" if total_entradas == 1 else "Cancelación de Entradas en Oasis Night Club"

        email = EmailMessage(
            subject=subject,
            body=mensaje_html,
            from_email=settings.EMAIL_HOST_USER,
            to=[destinatario],
        )
        email.content_subtype = 'html'
        email.send()

    except Exception as e:
        print(f"Error al enviar el correo: {e}")


@rol_requerido([1])
def eliminarEntrada(request, id):
    try:
        entrada = CompraEntrada.objects.get(pk=id)
        evento = Evento.objects.get(pk=entrada.evento.id)
        
        qr_entradas = EntradasQR.objects.filter(compra=entrada)
        qr_entradas.delete()
        entrada.delete()

        evento.entradas_disponibles = F('entradas_disponibles') + entrada.entrada_general + entrada.entrada_vip
        cantidad_entradas_evento = CompraEntrada.objects.filter(evento=evento).count()

        if cantidad_entradas_evento == 0:
            evento.entradas = False

        evento.ganancia_entradas -= entrada.total
        evento.ganancia_total -= entrada.total
        evento.save()

        total_entradas = entrada.entrada_general + entrada.entrada_vip
        threading.Thread(target=enviar_correo_cancelacion_entrada, args=(entrada, total_entradas)).start()

        messages.success(request, "Entrada eliminada correctamente!")

    except Exception as e:
        messages.error(request, f"Error: {e}")
    
    return redirect(f'/Evento_Entradas/{evento.id}')


@rol_requerido([1])
def eveReserva(request, id):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk=logueo["id"])
    evento = Evento.objects.get(id=id)
    reservas = Reserva.objects.filter(evento=evento)

    contexto = {'user': user, 'reservas': reservas, 'evento': evento, 'url': "Gestion_Eventos"}

    return render(request, 'Oasis/eventos/eveReserva.html', contexto)


@rol_requerido([1])
def eveReservaLlegada(request, codigo_qr):
    try:
        reserva = Reserva.objects.get(codigo_qr=codigo_qr)
        reserva.estado_qr = False
        reserva.save()

        messages.success(request, "¡Llegada al bar exitosa!")
        return redirect(reverse('eveReserva', args=[reserva.evento.id]))

    except Exception as e:
        messages.error(request, f'Error: {e}')
        return redirect(reverse('eveReserva', args=[reserva.evento.id]))

@rol_requerido([1])
def eveEliminados(request):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    q = Evento.objects.filter(estado=False)

    contexto = {'data' : q, 'user':user, 'url': "Gestion_Eventos"}
    return render(request, "Oasis/eventos/eveEliminados.html", contexto)


# MENÚ (CATEGORÍAS)
@rol_requerido([1])
def meInicio(request):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    q = Categoria.objects.all()
    contexto = {'data' : q, 'user':user, 'url': 'Gestion_Menu'}
    return render(request, "Oasis/menu/meInicio.html", contexto)

@rol_requerido([1])
def crearCategoria(request):
    if request.method == "POST":
        try:
            nom = request.POST.get('nombre')
            desc = request.POST.get('descripcion')
            foto = request.FILES.get('foto')

            if foto == None:
                foto = "Img_categorias/default.jpg"

            if Categoria.objects.filter(nombre=nom).exists():
                messages.warning(request, 'Ya existe una categoria con ese nombre.')
                return redirect('Menu')

            # INSERT INTO Categoria VALUES (nom, desc)
            q = Categoria(
                nombre = nom, 
                descripcion = desc,
                foto = foto,
                )
            q.save()
            messages.success(request, "Categoria Creada Correctamente!")
        except Exception as e:
            messages.error(request, f'Error: {e}')
        return redirect('Menu')
    
    else:
        messages.warning (request, f'Error: No se enviaron datos...')
        return redirect('Menu')


@rol_requerido([1])
def eliminarCategoria(request, id):
    try:
        q = Categoria.objects.get(pk = id)
        q.delete()
        messages.success(request, "Categoria Eliminada Correctamente!")
    except Exception as e:
        messages.error(request, f'Error: {e}')
    
    return redirect('Menu')


@rol_requerido([1])
def actualizarCategoria(request, id):
    if request.method == "POST":
        nom = request.POST.get('nombre')
        desc = request.POST.get('descripcion')
        foto_nueva = request.FILES.get('foto_nueva')

        if Categoria.objects.filter(nombre=nom).exclude(pk=id).exists():
            messages.warning(request, 'Ya existe otra categoria con ese nombre.')
            return redirect('Menu')
    
        try:
            q = Categoria.objects.get(pk=id)
            q.nombre = nom
            q.descripcion = desc

            if foto_nueva:
                q.foto = foto_nueva

            q.save()
            messages.success(request, "Categoria Actualizada Correctamente!")

        except Exception as e:
            messages.error(request, f'Error: {e}')

    else:
        messages.warning (request, f'Error: No se enviaron datos...')
        
    return redirect('Menu')



@rol_requerido([1])
def meProductos(request, id):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])

    categoria = Categoria.objects.get(pk = id)
    productos = Producto.objects.filter(categoria = categoria)

    contexto = {'user':user, 'categoria' : categoria, 'productos': productos,'url': 'Productos'}
    return render (request, 'Oasis/menu/meProductos.html', contexto)


@rol_requerido([1])
def meCrearProducto(request, id):
    if request.method == "POST":
        try:
            nom = request.POST.get('nombre')
            desc = request.POST.get('descripcion')
            inventario = int(request.POST.get('inventario'))
            pre = request.POST.get('precio')
            foto = request.FILES.get('foto')

            cat = Categoria.objects.get(pk=id)

            if int(pre) <= 0:
                messages.warning(request, "El precio debe ser mayor a 0")
                return redirect("meProductos", id)
            
            if inventario <= 0:
                messages.warning(request, "El inventario debe ser mayor a 0")
                return redirect("meProductos", id)

            if Producto.objects.filter(nombre=nom).exists():
                messages.warning(request, "Ya existe un producto con ese nombre")
                return redirect("meProductos", id)
            
            if foto == None:
                foto = "Img_productos/default.png"

            q = Producto(
                nombre=nom,
                descripcion=desc,
                categoria=cat,
                inventario=inventario,
                precio=pre,
                foto=foto,
            )
            q.save()
            messages.success(request, "Producto Agregado Correctamente!")
        except Exception as e:
            messages.error(request, f'Error: {e}')
    else:
        messages.warning(request, f'Error: No se enviaron datos...')

    return redirect('meProductos', id)


@rol_requerido([1])
def meDetalleProducto(request, id):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    producto = Producto.objects.get(pk = id)
    contexto = {'user':user, 'producto': producto, 'url': 'Me_Detalle_Producto'}
    return render(request, 'Oasis/menu/meDetalleProducto.html', contexto)


@rol_requerido([1])
def gaInicio(request):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    q = Galeria.objects.all()
    contexto = {'data' : q, 'user':user, 'url': 'Gestion_Galeria'}
    return render(request, "Oasis/galeria/gaInicio.html", contexto)


@rol_requerido([1])
def crearCarpeta(request):
    if request.method == "POST":
        try:
            nom = request.POST.get('nombre')
            date = request.POST.get('fecha')
            foto = request.FILES.get('foto')

            if foto == None:
                foto = "Img_carpeta/default.png"

            if Galeria.objects.filter(nombre=nom, fecha=date).exists():
                messages.warning(request, 'Ya existe una carpeta con ese nombre y fecha.')
                return redirect('gaInicio')

            # INSERT INTO Evento VALUES (nom, date, time, desc, foto)
            q = Galeria(
                nombre = nom,
                fecha = date,
                foto = foto,
            )
            q.save()
            messages.success(request, "Carpeta Creada Correctamente!")
        except Exception as e:
            messages.error(request, f'Error: {e}')
        return redirect('gaInicio')
    
    else:
        messages.warning (request, f'Error: No se enviaron datos...')
        return redirect('gaInicio')



@rol_requerido([1])
def eliminarCarpeta(request, id):
    try:
        q = Galeria.objects.get(pk = id)
        q.delete()
        messages.success(request, "Carpeta Eliminada Correctamente!")
    except Exception as e:
        messages.error(request, f'Error: {e}')
    
    return redirect('gaInicio')


@rol_requerido([1])
def actualizarCarpeta(request, id):
    if request.method == "POST":
        nom = request.POST.get('nombre')
        date = request.POST.get('fecha')
        foto_nueva = request.FILES.get('foto_nueva')

        if Galeria.objects.filter(nombre=nom, fecha=date).exclude(pk=id).exists():
            messages.warning(request, 'Ya existe una carpeta con ese nombre y fecha.')
            return redirect('gaFotos', id=id)


        try:
            q = Galeria.objects.get(pk=id)
            q.nombre = nom
            q.fecha = date
            
            if foto_nueva:
                q.foto = foto_nueva

            q.save()
            messages.success(request, "Carpeta Actualizada Correctamente!")

        except Exception as e:
            messages.error(request, f'Error: {e}')

    else:
        messages.warning (request, f'Error: No se enviaron datos...')
        
    return redirect('gaFotos', id=id)

@rol_requerido([1])
def gaFotos(request, id):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    carpeta = Galeria.objects.get(pk = id)
    fotos = Fotos.objects.filter(carpeta = carpeta)
    contexto = {'user':user, 'carpeta': carpeta, "fotos": fotos,'url': 'gaFotos'}
    return render(request, 'Oasis/galeria/gaFotos.html', contexto)


@rol_requerido([1])
def agregarFoto(request, id):
    if request.method == "POST":
        foto_nueva = request.FILES.get('foto_nueva')
        try:
            q = Galeria.objects.get(pk=id)
            nueva_foto = Fotos(
                carpeta=q,
                foto=foto_nueva
            )
            nueva_foto.save()
            messages.success(request, "Foto Agregada Correctamente!")
        except Exception as e:
            messages.error(request, f'Error: {e}')
    else:
        messages.warning (request, f'Error: No se enviaron datos...')

    return redirect('gaFotos', id=id)



@rol_requerido([1])
def cambiarFoto(request, id):
    if request.method == "POST":
        foto_nueva = request.FILES.get('foto_nueva')
        try:
            q = Fotos.objects.get(pk=id)
            q.foto = foto_nueva
            q.save()
            messages.success(request, "Foto Actualizada Correctamente!")
        except Exception as e:
            messages.error(request, f'Error: {e}')
    else:
        messages.warning (request, f'Error: No se enviaron datos...')

    return redirect('gaFotos', id=q.carpeta.id)


@rol_requerido([1])
def eliminarFoto(request, id):
    try:
        q = Fotos.objects.get(pk = id)
        q.delete()
        messages.success(request, "Foto Eliminada Correctamente!")
    except Exception as e:
        messages.error(request, f'Error: {e}')
    
    return redirect('gaFotos', id=q.carpeta.id)




def front_productos(request):
    logueo = request.session.get("logueo", False)
    user = None
    if logueo:
        user = Usuario.objects.get(pk=logueo["id"])
    
    categorias = Categoria.objects.all()
    cat = request.GET.get("cat")
    
    sin_productos = False
    nombre_categoria = None
    
    if cat is None:
        productos = Producto.objects.all()
        if len(productos) == 0:
            sin_productos = True
    else:
        c = Categoria.objects.get(pk=cat)
        productos = Producto.objects.filter(categoria=c)
        nombre_categoria = c.nombre
    
    contexto = {
        "user": user,
        "productos": productos,
        "categorias": categorias,
        "sin_productos": sin_productos,
        "nombre_categoria": nombre_categoria,
        "url": "front_productos"
    }
    
    return render(request, "Oasis/front_productos/front_productos.html", contexto)



def front_producto_info(request, id):
    logueo = request.session.get("logueo", False)
    user = None
    if logueo:
        user = Usuario.objects.get(pk=logueo["id"])

    producto = Producto.objects.get(pk=id)

    contexto = {"user": user, "producto": producto, "url": "front_producto_info"}

    return render(request, "Oasis/front_productos/front_producto_info.html", contexto)


def front_eventos(request):
    logueo = request.session.get("logueo", False)
    user = None
    if logueo:
        user = Usuario.objects.get(pk = logueo["id"])
    eventos = Evento.objects.filter(estado=True)

    contexto = {"user": user, "eventos": eventos, "url": "front_eventos"}
    return render(request, "Oasis/front_eventos/front_eventos.html", contexto)

def front_eventos_info(request, id):
    logueo = request.session.get("logueo", False)
    user = None
    if logueo:
        user = Usuario.objects.get(pk = logueo["id"])
    evento = Evento.objects.get(pk=id)
    reservas = Reserva.objects.filter(evento=evento)
    mesas = Mesa.objects.all()

    listMesas = []

    for reserva in reservas:
        listMesas.append(reserva.mesa)

    total_defecto = evento.precio_entrada + evento.precio_vip

    contexto = {"user": user, "evento": evento, "mesas": mesas, "total_defecto": total_defecto, "listMesas": listMesas, 'url': 'front_eventos_info'}
    return render(request, "Oasis/front_eventos/front_eventos_info.html", contexto)



def front_galeria(request):
    logueo = request.session.get("logueo", False)
    user = None
    if logueo:
        user = Usuario.objects.get(pk = logueo["id"])
    q = Galeria.objects.all()
    contexto = {'user' : user, 'galeria': q, 'url': 'front_galeria'}
    return render(request, "Oasis/front_galeria/front_galeria.html", contexto)


def front_fotos(request, id):
    logueo = request.session.get("logueo", False)
    user = None
    if logueo:
        user = Usuario.objects.get(pk = logueo["id"])
    q = Galeria.objects.get(pk=id)
    fotos = Fotos.objects.filter(carpeta = q)
    contexto = {'user' : user, 'galeria': q,'fotos': fotos, 'url': 'front_fotos'}
    return render(request, "Oasis/front_galeria/front_fotos.html", contexto)

def generar_pdf_entrada(request, compra, entrada):
    html_string = render_to_string('Oasis/emails/pdf/entrada_pdf_template.html', {'compra': compra, 'entrada': entrada, 'request': request})
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="entrada_{entrada.id}.pdf"'
    pisa_status = pisa.CreatePDF(html_string, dest=response)
    if pisa_status.err:
        return None
    return response

def enviar_correo_entradas(request, compra, qr_entradas, destinatario):
    mensaje_html = render_to_string('Oasis/emails/plantillas/entrada_email_template.html', {
        'compra': compra,
        'entradas': qr_entradas,
        'request': request
    })
    
    email = EmailMessage(
        subject='Compra de entradas en Oasis Night Club',
        body=mensaje_html,
        from_email=settings.EMAIL_HOST_USER,
        to=[destinatario],
    )
    email.content_subtype = 'html' 

    # Generar y adjuntar PDFs por cada entrada
    for entrada in qr_entradas:
        pdf = generar_pdf_entrada(request, compra, entrada)
        if pdf:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                temp_pdf.write(pdf.content)
                temp_pdf_path = temp_pdf.name
            email.attach_file(temp_pdf_path)
            os.remove(temp_pdf_path)

    # Enviar el correo
    email.send()

def comprar_entradas(request, id):
    logueo = request.session.get("logueo", False)
    messages = []

    if not logueo:
        messages.append({'message_type': 'warning', 'message': 'Inicia sesión antes de comprar'})
        return JsonResponse({'messages': messages}) 

    user = Usuario.objects.get(pk=logueo["id"])
    evento = Evento.objects.get(pk=id)

    if user.estado == 2:
        messages.append({'message_type': 'warning', 'message': 'Estás bloqueado, no puedes comprar entradas.'})
        return JsonResponse({'messages': messages})

    if user.rol != 4:
        messages.append({'message_type': 'warning', 'message': 'Debes de ser un cliente para comprar entradas'})
        return JsonResponse({'messages': messages})

    if request.method == "POST":    
        data = json.loads(request.body)
        
        cantidad_general = int(data.get("cantidad_general", 0))
        cantidad_vip = int(data.get("cantidad_vip", 0))
        precio_entrada_general = evento.precio_entrada
        precio_entrada_vip = evento.precio_vip
        total = (cantidad_general * precio_entrada_general) + (cantidad_vip * precio_entrada_vip)

        if evento.entradas_disponibles >= cantidad_general + cantidad_vip:
            compra = CompraEntrada.objects.create(
                usuario=user, 
                evento=evento,
                entrada_general=cantidad_general,
                entrada_vip=cantidad_vip,
                total=total,
            )

            evento.entradas_disponibles -= cantidad_general + cantidad_vip
            
            if not evento.entradas:
                evento.entradas = True

            evento.ganancia_entradas += total
            evento.ganancia_total += total
            evento.save()

            if cantidad_general > 0:
                for _ in range(cantidad_general):
                    EntradasQR.objects.create(
                        compra= CompraEntrada.objects.get(pk=compra.id),
                        tipo_entrada="General",
                    )
            
            if cantidad_vip > 0:
                for _ in range(cantidad_vip):
                    EntradasQR.objects.create(
                        compra= CompraEntrada.objects.get(pk=compra.id),
                        tipo_entrada="VIP",
                    ) 

            qr_entradas = EntradasQR.objects.filter(compra=compra.id)
            destinatario = user.email

            # Iniciar el hilo para enviar el correo en segundo plano
            correo_thread = threading.Thread(target=enviar_correo_entradas, args=(request, compra, qr_entradas, destinatario))
            correo_thread.start()

            # Confirmación inmediata de la compra
            messages.append({'message_type': 'success', 'message': 'Entradas compradas correctamente'})
        else:
            messages.append({'message_type': 'error', 'message': 'No hay suficientes entradas disponibles'})

    return JsonResponse({'messages': messages})


def generar_pdf_reserva(request, reserva):
    html_string = render_to_string('Oasis/emails/pdf/reserva_pdf_template.html', {'reserva': reserva, 'request': request})
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reserva.pdf"'
    pisa_status = pisa.CreatePDF(html_string, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar PDF')
    return response

def enviar_correo_reserva(user, reserva, request):
    pdf = generar_pdf_reserva(request, reserva)

    if pdf:
        destinatario = user.email
        contexto = {
            'reserva': reserva,
            'request': request
        }
        mensaje_html = render_to_string('Oasis/emails/plantillas/reserva_email_template.html', contexto)

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            temp_pdf.write(pdf.content)
            temp_pdf_path = temp_pdf.name

        email = EmailMessage(
            subject='Reserva exitosa en Oasis Night Club',
            body=mensaje_html,
            from_email=settings.EMAIL_HOST_USER,
            to=[destinatario],
        )
        email.attach_file(temp_pdf_path)
        email.content_subtype = 'html'
        email.send()

        os.remove(temp_pdf_path)


def reservar_mesa(request, id):
    logueo = request.session.get("logueo", False)
    messages = []

    if not logueo:
        messages.append({'message_type': 'warning', 'message': 'Inicia sesión antes de reservar'})
        return JsonResponse({'messages': messages}) 

    user = Usuario.objects.get(pk=logueo["id"])
    evento = Evento.objects.get(pk=id)

    if user.estado == 2:
        messages.append({'message_type': 'warning', 'message': 'Estás bloqueado, no puedes reservar una mesa.'})
        return JsonResponse({'messages': messages})

    if user.rol != 4:
        messages.append({'message_type': 'warning', 'message': 'Debes de ser un cliente para reservar una mesa'})
        return JsonResponse({'messages': messages})

    if request.method == "POST":
        data = json.loads(request.body)
        mesa = Mesa.objects.get(pk=data.get("id_mesa", 0))
        total = int(data.get("total_general", 0))

        if evento.entradas_disponibles >= mesa.capacidad:
            reserva = Reserva.objects.create(
                usuario=user, 
                evento=evento,  
                mesa=mesa,
                total=total,
            )
            evento.entradas_disponibles -= mesa.capacidad

            if not evento.reservas:
                evento.reservas = True
                
            evento.ganancia_reservas += total
            evento.ganancia_total += total
            evento.save()
            mesa.estado_reserva = 'Reservada'
            mesa.ganancia_reserva += total
            mesa.total_ganancia = mesa.ganancia_reserva + mesa.pedidos
            mesa.save()

            messages.append({'message_type': 'success', 'message': 'Mesa reservada correctamente'})

            threading.Thread(target=enviar_correo_reserva, args=(user, reserva, request)).start()

        else:
            messages.append({'message_type': 'error', 'message': 'No hay suficientes entradas disponibles'})

    return JsonResponse({'messages': messages})


@rol_requerido([1])
def enviar_correo_cancelacion_reserva(reserva):
    try:
        destinatario = reserva.usuario.email
        contexto = {
            'reserva': reserva,
        }
        mensaje_html = render_to_string('Oasis/emails/plantillas/cancelacion_reserva_email_template.html', contexto)

        email = EmailMessage(
            subject='Cancelación de Reserva en Oasis Night Club',
            body=mensaje_html,
            from_email=settings.EMAIL_HOST_USER,
            to=[destinatario],
        )
        email.content_subtype = 'html'
        email.send() 

    except Exception as e:
        print(f"Error al enviar el correo: {e}") 


@rol_requerido([1])
def eliminar_reserva(request, id):
    try:
        reserva = Reserva.objects.get(pk=id)
        reserva.evento.entradas_disponibles += reserva.mesa.capacidad
        reserva.delete()

        cantidad_reservas_evento = Reserva.objects.filter(evento=reserva.evento).count()
        if cantidad_reservas_evento == 0:
            reserva.evento.reservas = False
            
        reserva.evento.ganancia_reservas -= reserva.total
        reserva.evento.ganancia_total -= reserva.total
        reserva.evento.save()

        mesa = Mesa.objects.get(pk=reserva.mesa.id)
        if not Reserva.objects.filter(mesa=mesa).exists():
            reserva.mesa.estado_reserva = "Disponible"

        reserva.mesa.save()

        threading.Thread(target=enviar_correo_cancelacion_reserva, args=(reserva,)).start()

        messages.success(request, 'Reserva eliminada correctamente')

    except Exception as e:
        messages.error(request, f"Error al eliminar la reserva: {e}")

    return redirect(f'/Reservas/{reserva.evento.id}')


def escanear_mesa (request):
    logueo = request.session.get("logueo", False)
    user = None
    if logueo:
        user = Usuario.objects.get(pk = logueo["id"])

    mesas = Mesa.objects.all()

    contexto = {'user':user, 'mesas':mesas}
    return render(request, "Oasis/front_pedidos/escanear_mesa.html", contexto)



def pedidoUsuario(request, id):
    logueo = request.session.get("logueo", False)
    user = None
    if logueo:
        user = get_object_or_404(Usuario, pk=logueo["id"])

    mesa = get_object_or_404(Mesa, pk=id)
    carrito = request.session.get("carrito", [])
    productos = Producto.objects.all()
    categorias = Categoria.objects.all()

    cat = request.GET.get("cat")

    if cat is not None:
        cat = int(cat)
        c = Categoria.objects.get(pk=cat)
        productos = Producto.objects.filter(categoria=c)
    else:
        productos = Producto.objects.all()

    contexto = {'user': user, 'productos': productos, 'mesa': mesa, 'carrito': carrito, 'cat': cat, 'categorias':categorias}
    return render(request, "Oasis/front_pedidos/pedido_usuario.html", contexto)
    

def carrito_add(request):
    if request.method == "POST":
        try:
            carrito = request.session.get("carrito", [])
            if not carrito:
                request.session["carrito"] = []
                request.session["items"] = 0
                carrito = []

            id_producto = int(request.POST.get("id"))
            cantidad = int(request.POST.get("cantidad", 1))
            template_name = request.POST.get("template_name", "Oasis/carrito/carrito.html")
            # Consulto en DB
            q = Producto.objects.get(pk=id_producto)

            for p in carrito:
                if p["id"] == id_producto:
                    if q.inventario >= (p["cantidad"] + cantidad) and cantidad > 0:
                        p["cantidad"] += cantidad
                        p["subtotal"] = p["cantidad"] * q.precio
                    else:
                        messages.warning(request, "Cantidad supera inventario")
                    break
            else:
                if q.inventario >= cantidad and cantidad > 0:
                    carrito.append({
                        "id": q.id,
                        "foto": q.foto.url,
                        "producto": q.nombre,
                        "precio": q.precio,
                        "cantidad": cantidad,
                        "subtotal": cantidad * q.precio
                    })
                else:
                    messages.warning(request, "No se puede agregar, no hay suficiente inventario.")

            # Actualizamos variable de sesión carrito...
            request.session["carrito"] = carrito
            items = len(carrito)
            contexto = {
                "items": items,
                "total": sum(p["subtotal"] for p in carrito)
            }
            request.session["items"] = len(carrito)
            return render(request, template_name, contexto)
        except ValueError:
            messages.error(request, "Error: Digite un valor correcto para cantidad...")
            return HttpResponse("Error...")
        except Exception as e:
            messages.error(request, f"Ocurrió un error: {e}")
            return HttpResponse("Error...")
    else:
        messages.warning(request, "No se enviaron datos.")
        return HttpResponse("Error...")


def carrito_ver(request):
    carrito = request.session.get("carrito", False)
    template_name = "template_name", "Oasis/carrito/carrito.html"

    if not carrito:
        request.session["carrito"] =[]
        request.session["items"] = 0
        contexto = {
        "items": 0,
        "total": 0
    }
    else:
        contexto = {
            "items": len(carrito),
            "total": sum(p["subtotal"] for p in carrito)
        }
        request.session["items"] = len(carrito)
    return render(request, template_name, contexto)


def carrito_ver_admin(request):
    carrito = request.session.get("carrito", False)
    template_name = "Oasis/carrito/carrito_admin.html"

    if not carrito:
        request.session["carrito"] =[]
        request.session["items"] = 0
        contexto = {
        "items": 0,
        "total": 0
    }
    else:
        contexto = {
            "items": len(carrito),
            "total": sum(p["subtotal"] for p in carrito)
        }
        request.session["items"] = len(carrito)
    return render(request, template_name, contexto)


def carrito_eliminar(request, id):
    try:
        carrito = request.session.get("carrito", False)
        if carrito != False:
            for i, item in enumerate(carrito):
                if item["id"] == id:
                    carrito.pop(i)
                    break
            else:
                messages.warning(request, "No se encontró el item carrito")
        request.session["carrito"] = carrito
        request.session["items"] = len(carrito)
        return redirect('carrito_ver')
    except Exception as e:
        messages.error(request, f"Error: {e}")

def carrito_eliminar_admin(request, id):
    try:
        carrito = request.session.get("carrito", False)
        if carrito != False:
            for i, item in enumerate(carrito):
                if item["id"] == id:
                    carrito.pop(i)
                    break
            else:
                messages.warning(request, "No se encontró el item carrito")
        request.session["carrito"] = carrito
        request.session["items"] = len(carrito)
        return redirect('carrito_ver_admin')
    except Exception as e:
        messages.error(request, f"Error: {e}")


def vaciar_carrito(request):
	request.session["carrito"] = []
	request.session["items"] = 0
	return redirect('front_productos')

def vaciar_carrito_admin(request):
	request.session["carrito"] = []
	request.session["items"] = 0
	return redirect('pedidoEmpleado')

def actualizar_totales_carrito(request, id_producto):
    carrito = request.session.get("carrito", False)
    cantidad = request.GET.get("cantidad")
    if carrito != False:
        for i, item in enumerate(carrito):
            if item["id"] == id_producto:
                item["cantidad"] = int(cantidad)
                item["subtotal"] = int(cantidad) * item["precio"]
                break
        else:
            messages.warning(request, "No se encontró el item carrito")
    request.session["carrito"] = carrito
    request.session["items"] = len(carrito)
    return redirect('carrito_ver')

def actualizar_totales_carrito_admin(request, id_producto):
    carrito = request.session.get("carrito", False)
    cantidad = request.GET.get("cantidad")
    if carrito != False:
        for i, item in enumerate(carrito):
            if item["id"] == id_producto:
                item["cantidad"] = int(cantidad)
                item["subtotal"] = int(cantidad) * item["precio"]
                break
        else:
            messages.warning(request, "No se encontró el item carrito")
    request.session["carrito"] = carrito
    request.session["items"] = len(carrito)
    return redirect('carrito_ver_admin')


def crear_pedido_admin(request, id):
    try:
        logueo = request.session.get("logueo")
        
        user = Usuario.objects.get(pk=logueo["id"])
        mesa = Mesa.objects.get(pk=id)
        
        carrito = request.session.get("carrito", [])
        if not carrito:
            messages.error(request, "El pedido está vacío.")
            return redirect('pedidoEmpleado', id=id)
        
        comentario = request.POST.get("comentario", "")
        
        pedido = Pedido.objects.create(
            mesa=mesa, 
            total=sum(item['subtotal'] for item in carrito), 
            usuario=user,
            comentario=comentario
        )
        
        for p in carrito:
            producto = Producto.objects.get(pk=p['id'])
            DetallePedido.objects.create(
                pedido=pedido,
                producto=producto,
                cantidad=p['cantidad'],
                precio=p['precio']
            )
            producto.inventario -= p['cantidad']
            producto.save()

        mesa.estado = mesa.ACTIVA
        mesa.usuario = user
        mesa.save()
        request.session["carrito"] = []
        request.session["items"] = 0
        messages.success(request, "Pedido creado con éxito.")

    except Exception as e:
        messages.error(request, f"Ocurrió un Error: {e}")
    
    return redirect('peGestionMesas')



class registrar_usuario_movil(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            nombre = request.data.get('nombre')
            email = request.data.get('email')
            cedula = request.data.get('cedula')
            fecha_nacimiento = request.data.get('fechaNacimiento')
            password1 = request.data.get('password1')
            password2 = request.data.get('password2')

            if password1 != password2:
                return JsonResponse({'message': 'Las contraseñas no coinciden'}, status=400)
            
            if Usuario.objects.filter(email=email).exists():
                return JsonResponse({'message': 'El correo ya está registrado'}, status=400)

            if Usuario.objects.filter(cedula=cedula).exists():
                return JsonResponse({'message': 'La cedula ya está registrada'}, status=400)
            
            else:
                q = Usuario.objects.create(
                    nombre = nombre,
                    fecha_nacimiento = fecha_nacimiento,
                    email = email,
                    cedula = cedula,
                    password = hash_password(password1)
                )
                q.save()
                return JsonResponse({'message': 'Usuario registrado existosamente!'})
        except Exception as e:
            return JsonResponse({'error': str(e), 'trace': traceback.format_exc()}, status=500)


class token_qr_movil(APIView):
    def get(self, request, mesa):
        try:
            mesa = Mesa.objects.get(codigo_qr = mesa)
            if mesa:
                return JsonResponse({'mesa':{
                    'nombre': mesa.nombre,
                    'codigo_qr':mesa.codigo_qr
                }})
        except Exception as e:
            return JsonResponse({'Error':f'{e}'}, status=400)


class comprar_entradas_movil(APIView):
    def post(self, request):
        try:

            id_usuario = request.data.get('id_usuario')
            id_evento = request.data.get('id_evento')
            cantidad_general = request.data.get('cantidad_general')
            cantidad_vip = request.data.get('cantidad_vip')
            total = request.data.get('total')

            usuario = Usuario.objects.get(pk=id_usuario)
            evento = Evento.objects.get(pk=id_evento)


            if evento.entradas_disponibles >= cantidad_general + cantidad_vip:
                compra = CompraEntrada.objects.create(
                    usuario=usuario, 
                    evento=evento,
                    entrada_general=cantidad_general,
                    entrada_vip=cantidad_vip,
                    total=total
                )

                evento.entradas_disponibles -= cantidad_general + cantidad_vip
                
                if not evento.entradas:
                    evento.entradas = True

                evento.ganancia_entradas += total
                evento.ganancia_total += total
                evento.save()

                if cantidad_general > 0:
                    for _ in range(cantidad_general):
                        EntradasQR.objects.create(
                            compra= CompraEntrada.objects.get(pk=compra.id),
                            tipo_entrada="General",
                        )
                
                if cantidad_vip > 0:
                    for _ in range(cantidad_vip):
                        EntradasQR.objects.create(
                            compra= CompraEntrada.objects.get(pk=compra.id),
                            tipo_entrada="VIP",
                        ) 


                qr_entradas = EntradasQR.objects.filter(compra=compra.id)
                destinatario = usuario.email

                correo_thread = threading.Thread(target=enviar_correo_entradas, args=(request, compra, qr_entradas, destinatario))
                correo_thread.start()   

                return JsonResponse({'message':'Entradas compradas con éxito'})
            else:
                return JsonResponse({'message':'No hay suficientes entradas disponibles'})
        except Exception as e:
            return JsonResponse({'error':f'{e}'}, status=500)


class entradas_usuario_movil(APIView):
    def get(self, request, id):
        try:
            usuario = Usuario.objects.get(pk=id)
            entradas = CompraEntrada.objects.filter(usuario=usuario)

            if not entradas:
                return JsonResponse({'entradas': []}, status=200)


            entradas_info = []
            for entrada in entradas:
                evento = Evento.objects.get(id=entrada.evento.id)
                entradas_info.append({
                    'entrada': {
                        'id': entrada.id,
                        'entrada_general': entrada.entrada_general,
                        'entrada_vip': entrada.entrada_vip,
                        'total': entrada.total,
                        'fecha_compra': entrada.fecha_compra
                    },
                    'evento': {
                        'id': evento.id,
                        'nombre': evento.nombre,
                        'fecha': evento.fecha,
                        'hora_incio': evento.hora_incio,
                        'descripcion': evento.descripcion,
                        'aforo': evento.aforo,
                        'precio_entrada': evento.precio_entrada,
                        'precio_vip': evento.precio_vip,
                        'foto': evento.foto.url,
                        'estado': evento.estado
                    }
                })

            return JsonResponse({'entradas': entradas_info})

        except Usuario.DoesNotExist:
            return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
        except Evento.DoesNotExist:
            return JsonResponse({'error': 'Evento no encontrado'}, status=404)
        except Exception as e:
            return JsonResponse({'error': f'Error: {str(e)}'}, status=500)



class entradas_detalles_usuario_movil(APIView):
    def get(self, request, user_id, entrada_id):

        try:
            usuario = Usuario.objects.get(pk=user_id)
            compra_entrada = CompraEntrada.objects.get(pk=entrada_id, usuario=usuario)

            # Serializar los datos
            qr_entradas = EntradasQR.objects.filter(compra=compra_entrada.id)
            evento = Evento.objects.get(pk=compra_entrada.evento.id)

            qr_entradas_serializer = EntradasQRSerializer(qr_entradas, many=True, context={'request': request})
            evento_serializer = EventoSerializer(evento, context={'request': request})
            compra_entrada_serializer = CompraEntradaSerializer(compra_entrada, context={'request': request})

            return Response({
                'qr_entradas': qr_entradas_serializer.data,
                'evento': evento_serializer.data,
                'compra_entrada': compra_entrada_serializer.data
            })


        except Exception as e:
            return JsonResponse({'error': f'Error: {str(e)}'})


class mesas_reservadas_movil(APIView):
    def get(self, request, id_evento):
        try:
            evento = Evento.objects.get(pk=id_evento)
            reservas = Reserva.objects.filter(evento=evento)
            mesas = Mesa.objects.all()

            listMesasReservadas = [reserva.mesa.id for reserva in reservas]

            mesas_serializer = MesaSerializer(mesas, many=True, context={'request': request})

            # Marcar las mesas como reservadas
            mesas_data = []
            for mesa in mesas_serializer.data:
                mesa['reservada'] = mesa['id'] in listMesasReservadas
                mesas_data.append(mesa)

            return Response({
                'mesas': mesas_data,
            })
        except Exception as e:
            return JsonResponse({'error': f'Error: {str(e)}'})

                

class reservar_mesa_movil(APIView):
    def post(self, request):
        try:
            id_usuario = request.data.get('id_usuario')
            id_evento = request.data.get('id_evento')
            id_mesa = request.data.get('id_mesa')
            total = request.data.get('total')

            usuario = Usuario.objects.get(pk=id_usuario)
            evento = Evento.objects.get(pk=id_evento)
            mesa = Mesa.objects.get(pk=id_mesa)


            if evento.entradas_disponibles >= mesa.capacidad:
                reserva = Reserva.objects.create(
                    usuario=usuario, 
                    evento=evento,  
                    mesa=mesa,
                    total=total,
                )
                evento.entradas_disponibles -= mesa.capacidad

                if not evento.reservas:
                    evento.reservas = True

                evento.ganancia_reservas += total
                evento.ganancia_total += total
                evento.save()
                mesa.estado_reserva = 'Reservada'
                mesa.save()

                threading.Thread(target=enviar_correo_reserva, args=(usuario, reserva, request)).start()
                return JsonResponse({'message':'Reserva hecha con éxito'})

            else:
                return JsonResponse({'message':'No hay suficientes entradas disponibles'})

        except Exception as e:
            return JsonResponse({'error': f'Error: {str(e)}'}, status=500)

class reservas_usuario_movil(APIView):
    def get(self, request, id):
        try:
            usuario = Usuario.objects.get(pk = id)
            reservas = Reserva.objects.filter(usuario = usuario)

            if not reservas:
                return JsonResponse({'reservas': []}, status=200)

            reservas_info = []
            for reserva in reservas:
                evento = Evento.objects.get(id=reserva.evento.id)
                reservas_info.append({
                    'reserva': {
                        'id': reserva.id,
                        'mesa': reserva.mesa.nombre,
                        'total': reserva.total,
                        'fecha_compra': reserva.fecha_compra
                    },
                    'evento': {
                        'id': evento.id,
                        'nombre': evento.nombre,
                        'fecha': evento.fecha,
                        'foto': evento.foto.url,
                        'estado': evento.estado
                    }
                })
            
            return JsonResponse({'reservas': reservas_info})
        
        except Exception as e:
            return JsonResponse({'error': f'Error: {str(e)}'}, status=500)

class reservas_detalles_usuario_movil(APIView):
    def get(self, request, user_id, reserva_id):

        try:
            usuario = Usuario.objects.get(pk=user_id)
            reserva = Reserva.objects.get(pk=reserva_id, usuario=usuario)
            evento = Evento.objects.get(pk=reserva.evento.id)

            evento_serializer = EventoSerializer(evento, context={'request': request})
            reserva_serializer = ReservaSerializer(reserva, context={'request': request})

            return Response({
                'evento': evento_serializer.data,
                'reserva': reserva_serializer.data,
                'mesa': reserva.mesa.nombre,
                'capacidad_mesa': reserva.mesa.capacidad

            })
        
        except Exception as e:
            return JsonResponse({'error': f'Error: {str(e)}'})



class realizar_pedido_movil(APIView):
    def post(self, request):
        try:
            id_usuario = request.data.get('id_usuario')
            codigo_mesa = request.data.get('codigo_mesa')
            comentario = request.data.get('comentario')
            total = request.data.get('total')
            productos_seleccionados = request.data.get('productos_seleccionados')
            print(productos_seleccionados)

            usuario = Usuario.objects.get(pk=id_usuario)
            mesa = Mesa.objects.get(codigo_qr=codigo_mesa)
            
            pedidos_mesa = Pedido.objects.filter(mesa=mesa)
            if pedidos_mesa:
                for p in pedidos_mesa:
                    p.usuario = usuario
                    p.save()

            pedido = Pedido.objects.create(
                mesa=mesa, 
                total=total, 
                usuario= usuario,
                comentario=comentario
            )

            
            for p in productos_seleccionados:
                try:
                    producto = Producto.objects.get(pk=p['id'])
                    detalle = DetallePedido.objects.create(
                        pedido=pedido,
                        producto=producto,
                        cantidad=p['cantidad'],
                        precio=p['precio']
                    )
                    producto.inventario -= p['cantidad']
                    producto.save()
                    print(f'Detalle del pedido creado: {detalle}')
                except Exception as e:
                    print(f'Error al crear detalle del pedido: {e}')

            mesa.estado = mesa.ACTIVA
            mesa.usuario = usuario
            mesa.save()
            
            return JsonResponse({'message': 'Pedido creado con éxito'})

        except Exception as e:
            return JsonResponse({'error': f'{e}'})



class ver_pedido_usuario_movil(APIView):
    def get(self, request, user_id):
        try:
            usuario = Usuario.objects.get(pk=user_id)
            pedidos = Pedido.objects.filter(usuario=usuario).order_by('-fecha')

            # Verificar si hay pedidos
            if not pedidos.exists():
                mesa_serializer_data = None
                detalles_pedidos = []
                cuenta = 0
                total_pedidos = 0
                pedidos_eliminados = 0
            else:
                try:
                    mesa = Mesa.objects.get(usuario=usuario)
                    mesa_serializer = MesaSerializer(mesa, context={'request': request})
                    mesa_serializer_data = mesa_serializer.data
                except Mesa.DoesNotExist:
                    mesa_serializer_data = None

                detalles_pedidos = []
                cuenta = 0

                for pedido in pedidos:
                    detalles = DetallePedido.objects.filter(pedido=pedido)
                    detalles_activos_count = detalles.filter(estado='Activo').count()
                    
                    pedido_serializer = PedidoSerializer(pedido, context={'request': request})
                    detalle_serializer = DetallePedidoSerializer(detalles, many=True, context={'request': request})
                    
                    detalles_pedidos.append({
                        'pedido': pedido_serializer.data,
                        'detalles': detalle_serializer.data,
                        'detalles_activos_count': detalles_activos_count
                    })

                    if pedido.estado != 'Cancelado':
                        for detalle in detalles:
                            if detalle.estado != "Eliminado":
                                cuenta += detalle.cantidad * detalle.precio

                pedidos_eliminados = pedidos.filter(estado='Cancelado').count()
                total_pedidos = pedidos.count()

            return JsonResponse({
                'total_pedidos': total_pedidos,
                'pedidos_eliminados': pedidos_eliminados,
                'mesa': mesa_serializer_data,
                'detalles_pedidos': detalles_pedidos,
                'cuenta': cuenta,
                'hay_pedidos': total_pedidos > 0
            })
        except Exception as e:
            return JsonResponse({'error': f'{e}'})


class ver_pedido_mesa_movil(APIView):
    def get(self, request, codigo_mesa):
        try:
            print(f"Buscando mesa con código QR: {codigo_mesa}")
            mesa = Mesa.objects.get(codigo_qr=codigo_mesa)
            pedidos = Pedido.objects.filter(mesa=mesa)

            mesa_serializer = MesaSerializer(mesa, context={'request': request})


            detalles_pedidos = []
            cuenta = 0

            for pedido in pedidos:
                detalles = DetallePedido.objects.filter(pedido=pedido)
                detalles_activos_count = detalles.filter(estado='Activo').count()
                
                pedido_serializer = PedidoSerializer(pedido, context={'request': request})
                detalle_serializer = DetallePedidoSerializer(detalles, many=True, context={'request': request})
                
                detalles_pedidos.append({
                    'pedido': pedido_serializer.data,
                    'detalles': detalle_serializer.data,
                    'detalles_activos_count': detalles_activos_count
                })

                if pedido.estado != 'Cancelado':
                    for detalle in detalles:
                        if detalle.estado != "Eliminado":
                            cuenta += detalle.cantidad * detalle.precio

            pedidos_eliminados = pedidos.filter(estado='Cancelado').count()
            total_pedidos = pedidos.count()

            return JsonResponse({
                'total_pedidos': total_pedidos,
                'pedidos_eliminados': pedidos_eliminados,
                'mesa': mesa_serializer.data,
                'detalles_pedidos': detalles_pedidos,
                'cuenta': cuenta,
            })
        except Exception as e:
            return JsonResponse({'error': f'{e}'})


class eliminar_pedido_usuario_movil(APIView):
    def get(self, request, id_pedido):
        try:
            pedido = Pedido.objects.get(pk=id_pedido)
            pedido.estado = pedido.CANCELADO
            pedido.comentario = ""

            detalles_pedido = DetallePedido.objects.filter(pedido=pedido)
            for d in detalles_pedido:
                d.estado = d.ELIMINADO
                d.motivo_eliminacion = ""
                d.save()

            pedido.save()
            return JsonResponse({'message':'Pedido cancelado exitosamente'})
        except Exception as e:
            return JsonResponse({'error': f'{e}'})



class eliminar_producto_pedido_usuario_movil(APIView):
    def get(self, request, id_detalle):
        try:
            detalle = DetallePedido.objects.get(pk=id_detalle)
            detalle.estado = detalle.ELIMINADO
            detalle.motivo_eliminacion = ""
            detalle.save()

            return JsonResponse({'message': 'Producto eliminado exitosamente'})
        except Exception as e:
            return JsonResponse({'error': str(e)})


class pagar_pedido_usuario_movil(APIView):
    def get(self, request, id_usuario, codigo_mesa):
        try:
            usuario = Usuario.objects.get(pk=id_usuario)
            mesa = Mesa.objects.get(codigo_qr=codigo_mesa)
            # Filtrar pedidos excluyendo los cancelados
            pedidos = Pedido.objects.filter(mesa=mesa).exclude(estado='Cancelado')
            pedidos_eliminados = Pedido.objects.filter(mesa=mesa).filter(estado='Cancelado')

            # Verificar si algún pedido está en preparación
            if any(pedido.estado == pedido.PREPARACION for pedido in pedidos):
                    return JsonResponse({'message': 'No se pueden pagar pedidos en preparación'}, status=400)


            # Calcular el total del pedido excluyendo los productos eliminados
            total_pedido = sum(
                sum(detalle.cantidad * detalle.precio for detalle in pedido.detallepedido_set.filter(estado='Activo'))
                for pedido in pedidos
            )

            # Crear el historial de pedido
            historial_pedido = HistorialPedido.objects.create(
                mesa=mesa,
                fecha=timezone.now(),
                usuario=usuario,
                total=total_pedido
            )

            # Agrupar productos por ID y sumar las cantidades, excluyendo los productos eliminados
            productos_agrupados = defaultdict(lambda: {'cantidad': 0, 'precio': 0})
            for pedido in pedidos:
                for detalle in pedido.detallepedido_set.filter(estado='Activo'):
                    producto_id = detalle.producto.id
                    productos_agrupados[producto_id]['cantidad'] += detalle.cantidad
                    productos_agrupados[producto_id]['precio'] = detalle.precio

            # Crear objetos en la tabla de historial de detalles con los productos agrupados
            for producto_id, datos in productos_agrupados.items():
                producto = Producto.objects.get(pk=producto_id)
                HistorialDetallePedido.objects.create(
                    historial_pedido=historial_pedido,
                    producto=producto,
                    cantidad=datos['cantidad'],
                    precio=datos['precio']
                )

            # Eliminar pedidos y detalles originales
            pedidos.delete()
            pedidos_eliminados.delete()

            # Actualizar el estado de la mesa
            mesa.estado = mesa.DISPONIBLE
            mesa.usuario = None
            mesa.save()

            return JsonResponse({'message': 'Pedido pagado exitosamente!'}, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e), 'trace': traceback.format_exc()}, status=500)


class liberar_mesa_usuario_movil(APIView):
    def get (self, request, codigo_mesa):
        try:
            mesa = Mesa.objects.get(codigo_qr=codigo_mesa)
            mesa.estado = mesa.DISPONIBLE
            mesa.usuario = None
            mesa.save()

            pedidos_eliminados = Pedido.objects.filter(mesa = mesa)
            pedidos_eliminados.delete()        

            return JsonResponse({'message':'Mesa liberada exitosamente!'})
        except Exception as e:
            return JsonResponse({'error': str(e), 'trace': traceback.format_exc()}, status=500)
        



class verificar_pedido_usuario_movil(APIView):
    def get(self, request, id_usuario):
        try:
            usuario = Usuario.objects.get(pk=id_usuario)
            pedido = Pedido.objects.filter(usuario=usuario).count()

            if pedido > 0:
                try:
                    # Intentar obtener la mesa del usuario
                    mesa = Mesa.objects.get(usuario=usuario)
                    mesaSerializer = MesaSerializer(mesa, context={'request': request})
                    return JsonResponse({'pedidos': True, 'mesa': mesaSerializer.data})
                except ObjectDoesNotExist:
                    # El usuario no tiene una mesa asignada
                    return JsonResponse({'pedidos': False, 'mesa': None}, status=200)
            else:
                return JsonResponse({'pedidos': False}, status=200)

        except Exception as e:
            return JsonResponse({'error': str(e), 'trace': traceback.format_exc()}, status=500)




class ver_mesa_cargo_movil(APIView):
    def get(self, request, id_usuario):
        try:
            usuario = Usuario.objects.get(pk = id_usuario)
            mesas = Mesa.objects.filter(usuario=usuario)


            mesasSerializer = MesaSerializer(mesas, many=True, context={'request': request})

            return JsonResponse({'mesas': mesasSerializer.data})
            
        except Exception as e:
            return JsonResponse({'error': str(e), 'trace': traceback.format_exc()}, status=500)


class qr_reserva_escaneado_movil(APIView):
    def get(self, request, codigo_qr):
        try:
            reserva = Reserva.objects.get(codigo_qr = codigo_qr)
            reserva.estado_qr = False
            reserva.save()

            return JsonResponse({'message':'Reserva escaneada exitosamente!'})

        except Exception as e:
            return JsonResponse({'error': str(e), 'trace': traceback.format_exc()}, status=500)
        

class qr_entrada_escaneado_movil(APIView):
    def get(self, request, codigo_qr):
        try:
            entrada = EntradasQR.objects.get(codigo_qr = codigo_qr)
            entrada.estado_qr = False
            entrada.save()

            return JsonResponse({'message':'Entrada escaneada exitosamente!'})
        except Exception as e:
            return JsonResponse({'error': str(e), 'trace': traceback.format_exc()}, status=500)
    
    
class categoria_productos_movil(APIView):
    def get(self, request, id_categoria):
        try:
            categoria = Categoria.objects.get(pk = id_categoria)
            productos = Producto.objects.filter(categoria = categoria)

            productosSerializer = ProductoSerializer(productos, many=True, context={'request': request})

            return JsonResponse({'productos': productosSerializer.data})
        
        except Exception as e:
            return JsonResponse({'error': str(e), 'trace': traceback.format_exc()}, status=500)
        

class galeria_fotos_movil(APIView):
    def get(self, request, id_carpeta):
        try:
            carpeta = Galeria.objects.get(pk = id_carpeta)
            fotos = Fotos.objects.filter(carpeta = carpeta)

            fotosSerializer = FotosSerializer(fotos, many=True, context={'request': request})
            return JsonResponse({'fotos': fotosSerializer.data})
        
        except Exception as e:
            return JsonResponse({'error': str(e), 'trace': traceback.format_exc()}, status=500)


def crear_pedido_usuario(request, id):
    try:
        logueo = request.session.get("logueo", False)
        user = None
        if logueo:
            user = Usuario.objects.get(pk = logueo["id"])

        else:
            messages.error(request, "Inicia sesión ó registrate para realizar el pedido.")
            return redirect('pedidoUsuario', id=id)

        if user.estado == 2:
            messages.warning(request, 'Estás bloqueado, no puedes realizar pedidos.')
            return redirect('pedidoUsuario', id=id)

        if user.rol != 4:
            messages.warning(request, 'Debes de ser un cliente para realizar el pedido.')
            return redirect('pedidoUsuario', id=id)
        
        mesa = Mesa.objects.get(pk=id)
        
        carrito = request.session.get("carrito", [])
        if not carrito:
            messages.error(request, "El pedido está vacío.")
            return redirect('pedidoEmpleado', id=id)
        
        comentario = request.POST.get("comentario", "")

        pedidos_mesa = Pedido.objects.filter(mesa=mesa)
        if pedidos_mesa:
            for p in pedidos_mesa:
                p.usuario = user
                p.save()
        

        pedido = Pedido.objects.create(
            mesa=mesa, 
            total=sum(item['subtotal'] for item in carrito), 
            usuario=user,
            comentario=comentario
        )
        
        for p in carrito:
            producto = Producto.objects.get(pk=p['id'])
            DetallePedido.objects.create(
                pedido=pedido,
                producto=producto,
                cantidad=p['cantidad'],
                precio=p['precio']
            )
            producto.inventario -= p['cantidad']
            producto.save()

        mesa.estado = mesa.ACTIVA
        mesa.usuario = user
        mesa.save()
        request.session["carrito"] = []
        request.session["items"] = 0
        messages.success(request, "Pedido creado con éxito.")

    except Exception as e:
        messages.error(request, f"Ocurrió un Error: {e}")
    
    return redirect('ver_detalles_pedido_usuario')




def pagar_pedido(request, id, rol):
    logueo = request.session.get("logueo", False)
    usuario = Usuario.objects.get(pk=logueo["id"])

    try:
        mesa = Mesa.objects.get(pk=id)
        # Filtrar pedidos excluyendo los cancelados
        pedidos = Pedido.objects.filter(mesa=mesa).exclude(estado='Cancelado')
        pedidos_eliminados = Pedido.objects.filter(mesa=mesa).filter(estado='Cancelado')

        if not pedidos.exists():
            if rol == 'usuario':
                messages.error(request, "No hay pedidos para esta mesa.")
                return redirect('ver_detalles_pedido_usuario')
            else:
                messages.error(request, "No hay pedidos para esta mesa.")
                return redirect('peGestionMesas')

        # Verificar si algún pedido está en preparación
        if any(pedido.estado == pedido.PREPARACION for pedido in pedidos):
            if rol == 'usuario':
                messages.warning(request, "No se pueden pagar pedidos en preparación.")
                return redirect('ver_detalles_pedido_usuario')
            else:
                messages.warning(request, "No se pueden pagar pedidos en preparación.")
                return redirect('ver_pedidos_mesa', mesa_id=id)

        # Calcular el total del pedido excluyendo los productos eliminados
        total_pedido = sum(
            sum(detalle.cantidad * detalle.precio for detalle in pedido.detallepedido_set.filter(estado='Activo'))
            for pedido in pedidos
        )

        # Crear el historial de pedido
        historial_pedido = HistorialPedido.objects.create(
            mesa=mesa,
            fecha=timezone.now(),
            usuario=usuario,
            total=total_pedido
        )

        # Agrupar productos por ID y sumar las cantidades, excluyendo los productos eliminados
        productos_agrupados = defaultdict(lambda: {'cantidad': 0, 'precio': 0})
        for pedido in pedidos:
            for detalle in pedido.detallepedido_set.filter(estado='Activo'):
                producto_id = detalle.producto.id
                productos_agrupados[producto_id]['cantidad'] += detalle.cantidad
                productos_agrupados[producto_id]['precio'] = detalle.precio

        # Crear objetos en la tabla de historial de detalles con los productos agrupados
        for producto_id, datos in productos_agrupados.items():
            producto = Producto.objects.get(pk=producto_id)
            HistorialDetallePedido.objects.create(
                historial_pedido=historial_pedido,
                producto=producto,
                cantidad=datos['cantidad'],
                precio=datos['precio']
            )

        # Eliminar pedidos y detalles originales
        pedidos.delete()
        pedidos_eliminados.delete()

        # Actualizar el total de ganancias sumando reservas y pedidos
        mesa.pedidos += total_pedido
        mesa.total_ganancia = mesa.ganancia_reserva + mesa.pedidos
        mesa.estado = mesa.DISPONIBLE
        mesa.usuario = None
        mesa.save()

        messages.success(request, "¡Pedido pagado exitosamente!")
    except Exception as e:
        messages.error(request, f"Ocurrió un Error: {e}")

    if rol == 'usuario':
        return redirect('ver_detalles_pedido_usuario')
    else:
        return redirect('peGestionMesas')


@rol_requerido([3, 1])
def ver_pedidos_mesa(request, mesa_id):
    logueo = request.session.get("logueo", False)
    if logueo:
        user = Usuario.objects.get(pk = logueo["id"])
    else:
        messages.error(request, "Inicia sesión para ver los pedidos")
        return redirect('login')
    
    mesa = Mesa.objects.get(pk=mesa_id)
    pedidos = Pedido.objects.filter(mesa=mesa)

    detalles_pedidos = []
    cuenta = 0

    for pedido in pedidos:
        detalles = DetallePedido.objects.filter(pedido=pedido)
        detalles_activos_count = detalles.filter(estado='Activo').count()
        subtotal_pedido = 0

        for detalle in detalles:
            if detalle.estado != detalle.ELIMINADO:
                subtotal_pedido += detalle.subtotal
        
        detalles_pedidos.append({
            'pedido': pedido,
            'detalles': detalles,
            'detalles_activos_count': detalles_activos_count
        })

        if pedido.estado != 'Cancelado':
            cuenta += subtotal_pedido

    pedidos_eliminados = len(pedidos.filter(estado='Cancelado'))
    total_pedidos = len(pedidos)

    contexto = {
        'user': user,
        'mesa': mesa,
        'detalles_pedidos': detalles_pedidos,
        'total_pedidos': total_pedidos,
        'pedidos_eliminados': pedidos_eliminados,
        'cuenta': cuenta,
        'url': 'ver_pedidos_mesa'
    }
    return render(request, 'Oasis/pedidos/info_pedido_mesa.html', contexto)


@rol_requerido([1])
def ver_historial_pedidos(request):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])

    historial_pedidos = HistorialPedido.objects.all().order_by('-fecha')

    detalles_pedidos = []
    for historial_pedido in historial_pedidos:
        detalles = HistorialDetallePedido.objects.filter(historial_pedido=historial_pedido)
        detalles_pedidos.append({
            'pedido': historial_pedido,
            'detalles': detalles
        })

    contexto = {
        'user':user, 'detalles_pedidos': detalles_pedidos, 'url': 'Historial_Pedidos'
    }
    return render(request, "Oasis/pedidos/peHistorial.html", contexto)



@rol_requerido([4, 3, 1])
def descargar_pdf_pedido(request, id):
    try:
        historial_pedido = HistorialPedido.objects.get(pk=id)
        historial_detalles_pedido = HistorialDetallePedido.objects.filter(historial_pedido=historial_pedido)

        locale.setlocale(locale.LC_TIME, 'es_CO.utf8')
        fecha_actual = datetime.now().strftime('%d de %B de %Y')

        html_string = render_to_string('Oasis/pdf/factura_pedido_pdf_template.html', {
            'historial_pedido': historial_pedido,
            'historial_detalles_pedido': historial_detalles_pedido,
            'request': request,
            'fecha_actual': fecha_actual
        })

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="factura_pedido_{historial_pedido.id}.pdf"'

        pisa_status = pisa.CreatePDF(html_string, dest=response)

        if pisa_status.err:
            return HttpResponse('Error al generar el PDF', status=500)

        return response

    except Exception as e:
        messages.error(request, f"Ocurrió un error: {e}")
        return HttpResponse(f"Error: {e}", status=500)


@rol_requerido([3, 1])
def ver_mesas_a_cargo(request):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])

    try:
        mesas = Mesa.objects.filter(usuario=user)

        contexto = {
            'user':user, 'mesas':mesas, 'url': 'ver_mesas_a_cargo'
        }
        return render(request, "Oasis/usuario/mesas_a_cargo.html", contexto)
    
    except Exception as e:
        messages.error(request, f"Ocurrió un Error: {e}")
    

@rol_requerido([2, 1])
def entregar_pedido(request, id):
    try:
        pedido = Pedido.objects.get(pk=id)
        pedido.estado = pedido.ENTREGADO
        pedido.save()
        messages.success(request, "El pedido ha sido entregado.")
    except Exception as e:
        messages.error(request, f"Ocurió un un Error: {e}")

    return redirect('peInicio')


@rol_requerido([2, 1])
def cancelar_pedido(request):
    if request.method == 'POST':
        pedido_id = request.POST.get('pedido_id')
        comentario = request.POST.get('comentario')
        try:
            pedido = Pedido.objects.get(pk=pedido_id)
            pedido.comentario = comentario
            pedido.estado = pedido.CANCELADO

            detalles_pedido = DetallePedido.objects.filter(pedido=pedido)
            for d in detalles_pedido:
                d.estado = d.ELIMINADO
                d.motivo_eliminacion = ""
                d.save()

            pedido.save()
            messages.success(request, "Pedido cancelado exitosamente.")
        except Pedido.DoesNotExist:
            messages.error(request, "El pedido no existe.")
        except Exception as e:
            messages.error(request, f"Ocurrio un error: {e}")
    return redirect('peInicio')


@rol_requerido([4, 3, 1])
def cancelar_pedido_sin_comentario(request, id_pedido, id_mesa=None, ruta=None):
    try:
        pedido = Pedido.objects.get(pk=id_pedido)

        if not id_mesa:
            tiempo_transcurrido = timezone.now() - pedido.fecha
            if tiempo_transcurrido > timedelta(minutes=10):
                messages.error(request, "No puedes eliminar este ítem porque han pasado más de 10 minutos desde que se creó.")
                return redirect(f'/{ruta}/')

        pedido.estado = pedido.CANCELADO
        pedido.comentario = ""

        detalles_pedido = DetallePedido.objects.filter(pedido=pedido)
        for d in detalles_pedido:
            d.estado = d.ELIMINADO
            d.motivo_eliminacion = ""
            d.save()

        pedido.save()
        messages.success(request, "Pedido cancelado exitosamente.")
    except Exception as e:
        return messages.error(request, f'Ocurrio un error {e}')
    
    if id_mesa:
        return redirect(f'/{ruta}/{id_mesa}')
    else:
        return redirect(f'/{ruta}/')


@rol_requerido([2, 1])
def eliminar_item(request):
    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        motivo = request.POST.get('comentario')
        
        try: 
            detalle = DetallePedido.objects.get(pk=producto_id)
            detalle.motivo_eliminacion = motivo
            detalle.estado = detalle.ELIMINADO
            detalle.save()
            
            messages.success(request, 'Producto eliminado del pedido con éxito.')

        except DetallePedido.DoesNotExist:
            messages.error(request, "El detalle del pedido no existe.")
        except Exception as e:
            messages.error(request, f'Ocurrió un error: {e}')
    
    return redirect('peInicio')


@rol_requerido([4, 3, 1])
def eliminar_item_sin_comentario(request, id_producto, id_mesa=None, ruta=None):
    try:
        detalle = DetallePedido.objects.get(pk=id_producto)

        if not id_mesa:
            tiempo_transcurrido = timezone.now() - detalle.pedido.fecha
            if tiempo_transcurrido > timedelta(minutes=10):
                messages.error(request, "No puedes eliminar este ítem porque han pasado más de 10 minutos desde que se creó.")
                return redirect(f'/{ruta}/')
            
        detalle.estado = detalle.ELIMINADO
        detalle.motivo_eliminacion = ""
        detalle.save()

        messages.success(request, 'Producto eliminado del pedido con éxito.')
    except Exception as e:
        messages.error(request, f'Ocurrió un error: {e}')

    if id_mesa:
        return redirect(f'/{ruta}/{id_mesa}')
    else:
        return redirect(f'/{ruta}/')
    


@rol_requerido([4, 3, 1])
def liberar_mesa(request, id):
    logueo = request.session.get("logueo")
    user = Usuario.objects.get(pk=logueo["id"])
    try:

        mesa = Mesa.objects.get(pk=id)
        mesa.estado = mesa.DISPONIBLE
        mesa.usuario = None
        mesa.save()

        pedidos_eliminados = Pedido.objects.filter(mesa = mesa)
        pedidos_eliminados.delete()        

        messages.success(request, "Mesa liberada exitosamente.")
    except Exception as e:
        messages.error(request, f"Ocurrio un error: {e}")

    if user.rol == 4:
        return redirect('ver_detalles_pedido_usuario')
    else:
        return redirect('peGestionMesas')


def crear_venta(request):
	try:
		logueo = request.session.get("logueo")

		user = Usuario.objects.get(pk=logueo["id"])
		nueva_venta = Venta.objects.create(usuario=user)

		carrito = request.session.get("carrito", [])
		for p in carrito:
			producto = Producto.objects.get(pk=p["id"])
			cantidad = p["cantidad"]

			detalle_venta = DetalleVenta.objects.create(
                venta=nueva_venta,
                producto= producto,
                cantidad= cantidad,
                precio_historico=producto.precio,
            )

			producto.inventario -= cantidad
			producto.save()

			request.session["carrito"] = []
			request.session["items"] = 0

		messages.success(request, "Venta realizada correctamente!")

	except Exception as e:
		messages.error(request, f"Ocurrió un Error: {e}")

	return redirect('inicio')


@rol_requerido([4, 3, 1])
def ver_pedidos_usuario(request):
    logueo = request.session.get("logueo")
    user = Usuario.objects.get(pk=logueo["id"])
    ruta = ""
    if user.rol == 4:
        ruta = "Oasis/front_usuario/front_usuario_historial_pedidos.html"
    else:
        ruta = "Oasis/usuario/pedidos_usuario.html"

    historial_pedidos = HistorialPedido.objects.filter(usuario=user).order_by('-fecha')

    detalles_pedidos = []
    for historial_pedido in historial_pedidos:
        detalles = HistorialDetallePedido.objects.filter(historial_pedido=historial_pedido)
        detalles_pedidos.append({
            'pedido': historial_pedido,
            'detalles': detalles
        })

    total_pedidos = historial_pedidos.count()
        
    contexto = {
        'user':user, 'detalles_pedidos': detalles_pedidos, 'total_pedidos': total_pedidos, 'url': 'historial_pedidos'
    }
    return render(request, ruta, contexto)

@rol_requerido([4, 3, 1])
def ver_detalles_usuario(request):
    logueo = request.session.get("logueo")
    user = Usuario.objects.get(pk=logueo["id"])
    ruta = ""

    if user.rol == 4:
        ruta = "Oasis/front_usuario/front_usuario_pedidos.html"
    else:
        ruta = "Oasis/usuario/detalles_pedido_usuario.html"

    pedidos = Pedido.objects.filter(usuario=user).order_by('-fecha')


    try:
        mesa = Mesa.objects.get(usuario=user)
    except Mesa.DoesNotExist:
        mesa = None


    detalles_pedidos = []
    cuenta = 0

    for pedido in pedidos:
        detalles = DetallePedido.objects.filter(pedido=pedido)
        detalles_activos_count = detalles.filter(estado='Activo').count()
        subtotal_pedido = 0

        for detalle in detalles:
            if detalle.estado != detalle.ELIMINADO:
                subtotal_pedido += detalle.subtotal
        
        detalles_pedidos.append({
            'pedido': pedido,
            'detalles': detalles,
            'detalles_activos_count': detalles_activos_count
        })

        if pedido.estado != 'Cancelado':
            cuenta += subtotal_pedido

    pedidos_eliminados = pedidos.filter(estado='Cancelado').count()
    total_pedidos = pedidos.count()

    contexto = {
        'user': user,
        'mesa': mesa,
        'detalles_pedidos': detalles_pedidos,
        'total_pedidos': total_pedidos,
        'pedidos_eliminados': pedidos_eliminados,
        'cuenta': cuenta,
        'url': 'ver_detalles_pedido_usuario'
    }
    return render(request, ruta, contexto)


@rol_requerido([1])
def ganancias_eventos(request):   
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk = logueo["id"])
    
    eventos = Evento.objects.filter(Q(reservas=True) | Q(entradas=True))

    context = {
        'user':user,
        'eventos': eventos,
        'url': 'ganancias_eventos'
    }
    
    return render(request, 'Oasis/reportes/reportes_eventos.html', context)


@rol_requerido([1])
def descargar_pdf_ganancias_evento(request, id):
    evento = Evento.objects.get(id=id)
    
    # Establecer el locale en español
    locale.setlocale(locale.LC_TIME, 'es_CO.utf8')

    # Obtener la fecha actual en el formato "1 de febrero de 2023"f
    fecha_actual = datetime.now().strftime('%d de %B de %Y')
    
    html_string = render_to_string('Oasis/pdf/ganancia_evento_pdf_template.html', {'evento': evento, 'request': request, 'fecha_actual':fecha_actual})

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ganancias_{evento.nombre}.pdf"'
    
    pisa_status = pisa.CreatePDF(html_string, dest=response)

    if pisa_status.err:
        return HttpResponse('Error al generar el PDF', status=500)
    
    return response

@rol_requerido([1])
def reporte_mesas(request):
    logueo = request.session.get("logueo", False)
    user = Usuario.objects.get(pk=logueo["id"])
    mesas = Mesa.objects.all()
    context = {
        'user': user,
        'mesas': mesas,
        'fecha_actual': datetime.now().strftime('%d de %B de %Y'),
        'url': "reporte_mesas"
    }
    return render(request, 'Oasis/reportes/reporte_mesas.html', context)

@rol_requerido([1])
def descargar_pdf_mesas(request, id):
    mesa = Mesa.objects.get(id=id)
     # Establecer el locale en español
    locale.setlocale(locale.LC_TIME, 'es_CO.utf8')

    
    fecha_actual = datetime.now().strftime('%d de %B de %Y')
   
    html_string = render_to_string('Oasis/pdf/reporte_mesa_pdf.html', {'mesa': mesa, 'request': request,'fecha_actual': fecha_actual})
    
    response = HttpResponse(content_type='application/pdf')
   
    response['Content-Disposition'] = f'attachment; filename="mesa_{mesa.nombre}.pdf"'
    
    pisa_status = pisa.CreatePDF(html_string, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar el PDF', status=500)
    return response

@rol_requerido([1])
def reset_mesas(request):
    try:
        # Obtener todas las mesas
        mesas = Mesa.objects.all()

        # Recorrer cada mesa y poner tanto el total de ganancias como la reserva en 0
        for mesa in mesas:
            mesa.total_ganancia = 0  # Poner las ganancias en 0
            mesa.ganancia_reserva = 0  # Poner el precio/reserva en 0
            mesa.pedidos = 0
            mesa.save()

        # Añadir mensaje de éxito
        messages.success(request, 'Las mesas han sido reseteadas exitosamente.')

    except Exception as e:
        # Añadir mensaje de error si algo falla
        messages.error(request, f'Ocurrió un error al resetear las mesas: {str(e)}')

    # Redirigir de vuelta al reporte de mesas
    return redirect('reporte_mesas')


#mas_info
def mas_info(request):
    return render(request, 'Oasis/mas_info.html')

# -------------------------------------------------------------------------------------------
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated

# Vistas para el conjunto de datos de las API

class UsuarioViewSet(viewsets.ModelViewSet):
    # authentication_classes = [TokenAuthentication, SessionAuthentication]
	authentication_classes = [TokenAuthentication]
	permission_classes = [IsAuthenticated]
	queryset = Usuario.objects.all()
	serializer_class = UsuarioSerializer

class EventoViewSet(viewsets.ModelViewSet):
    queryset = Evento.objects.all()
    serializer_class = EventoSerializer

class CompraEntradaViewSet(viewsets.ModelViewSet):
    queryset = CompraEntrada.objects.all()
    serializer_class = CompraEntradaSerializer

class EntradasQRViewSet(viewsets.ModelViewSet):
    queryset = EntradasQR.objects.all()
    serializer_class = EntradasQRSerializer

class MesaViewSet(viewsets.ModelViewSet):
    queryset = Mesa.objects.all()
    serializer_class = MesaSerializer

class ReservaViewSet(viewsets.ModelViewSet):
    queryset = Reserva.objects.all()
    serializer_class = ReservaSerializer

class CategoriaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer

class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer

class PedidoViewSet(viewsets.ModelViewSet):
    queryset = Pedido.objects.all()
    serializer_class = PedidoSerializer

class DetallePedidoViewSet(viewsets.ModelViewSet):
    queryset = DetallePedido.objects.all()
    serializer_class = DetallePedidoSerializer

class PedidoMesaViewSet(viewsets.ModelViewSet):
    queryset = DetallePedido.objects.all()
    serializer_class = DetallePedidoSerializer


class GaleriaViewSet(viewsets.ModelViewSet):
    queryset = Galeria.objects.all()
    serializer_class = GaleriaSerializer

class FotosViewSet(viewsets.ModelViewSet):
    queryset = Fotos.objects.all()
    serializer_class = FotosSerializer

class VentaViewSet(viewsets.ModelViewSet):
    queryset = Venta.objects.all()
    serializer_class = VentaSerializer

class DetalleVentaViewSet(viewsets.ModelViewSet):
    queryset = DetalleVenta.objects.all()
    serializer_class = DetalleVentaSerializer



# ------------------------------- Personalización de Token Autenticación ------------
from rest_framework.authtoken.views import ObtainAuthToken


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
	if created:
		Token.objects.create(user=instance)

class CustomAuthToken(ObtainAuthToken):
	def post(self, request, *args, **kwargs):
		serializer = self.serializer_class(data=request.data,
										   context={'request': request})
		serializer.is_valid(raise_exception=True)
		user = serializer.validated_data['username']
		# traer datos del usuario para bienvenida y ROL
		usuario = Usuario.objects.get(email=user)
		token, created = Token.objects.get_or_create(user=usuario)

		return Response({
			'token': token.key,
			'user': {
				'user_id': usuario.pk,
				'email': usuario.email,
				'nombre': usuario.nombre,
				'rol': usuario.rol,
                'estado': usuario.estado,
				'foto': usuario.foto.url
			}
		})