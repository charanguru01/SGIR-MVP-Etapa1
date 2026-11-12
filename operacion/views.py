"""
Vistas y Controladores Web Responsivos del SGIR (Etapa 1).
Implementa los casos de uso CU-01 a CU-07 aplicando control de acceso por roles (RBAC)
y mensajes de error genéricos ante fallos de autenticación (OWASP A01 / A07).
"""
from decimal import Decimal, InvalidOperation
import uuid
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from operacion.models import (
    AnulacionProducto,
    Comanda,
    DetallePedido,
    Estacion,
    Impresora,
    Mesa,
    Pago,
    Producto,
    Rol,
    Usuario,
    Venta,
)
from operacion.security import (
    generar_hash_pin,
    normalizar_rut,
    obtener_usuario_sesion,
    rol_requerido,
    validar_rut_chileno,
    verificar_pin,
)
from operacion.services import (
    ErrorReglaNegocio,
    ServicioAnulaciones,
    ServicioImpresion,
    ServicioPedidos,
    ServicioVentas,
)


def vista_login(request: HttpRequest) -> HttpResponse:
    """CU-02 Iniciar sesión mediante RUT y PIN con mensaje genérico ante credenciales inválidas."""
    usuario_actual = obtener_usuario_sesion(request)
    if usuario_actual:
        if usuario_actual.rol.codigo == Rol.CAJERO:
            return redirect("caja")
        return redirect("salon")

    if request.method == "POST":
        rut_ingresado = normalizar_rut(request.POST.get("rut", ""))
        pin_ingresado = (request.POST.get("pin") or "").strip()

        usuario = Usuario.objects.select_related("rol").filter(rut=rut_ingresado, activo=True).first()
        if usuario and verificar_pin(pin_ingresado, usuario.pin_hash):
            request.session.cycle_key()
            request.session["sgir_usuario_id"] = usuario.id
            messages.success(request, f"Bienvenido/a, {usuario.nombre} ({usuario.rol.nombre}).")
            if usuario.rol.codigo == Rol.CAJERO:
                return redirect("caja")
            return redirect("salon")

        # Mensaje genérico para evitar enumeración de usuarios (OWASP A07 / Ley N° 19.628)
        messages.error(request, "Credenciales inválidas o usuario inactivo. Verifique RUT y PIN.")

    return render(request, "operacion/login.html")


def vista_logout(request: HttpRequest) -> HttpResponse:
    """Cierra la sesión activa del trabajador."""
    request.session.flush()
    messages.info(request, "Sesión finalizada correctamente.")
    return redirect("login")


@rol_requerido(Rol.ADMIN, Rol.GARZON)
def vista_salon(request: HttpRequest) -> HttpResponse:
    """RF-04 Consultar plano de mesas disponibles y ocupadas por plaza."""
    usuario = request.usuario_sgir
    if usuario.rol.codigo == Rol.GARZON:
        mesas = Mesa.objects.filter(sector=usuario.plaza_asignada)
    else:
        mesas = Mesa.objects.all()

    return render(
        request,
        "operacion/salon.html",
        {
            "usuario": usuario,
            "mesas": mesas,
        },
    )


@rol_requerido(Rol.ADMIN, Rol.GARZON)
def vista_tomar_pedido(request: HttpRequest, mesa_id: int) -> HttpResponse:
    """CU-03 / CU-04: Armado de borrador de pedido, edición previa, confirmación y envío a estaciones."""
    usuario = request.usuario_sgir
    mesa = get_object_or_404(Mesa, id=mesa_id)

    if usuario.rol.codigo == Rol.GARZON and mesa.sector != usuario.plaza_asignada:
        messages.error(request, "La mesa seleccionada no pertenece a su plaza asignada.")
        return redirect("salon")

    clave_carrito = f"carrito_mesa_{mesa.id}"
    carrito: list[dict] = request.session.get(clave_carrito, [])

    if request.method == "POST":
        accion = request.POST.get("accion")

        if accion == "agregar":
            producto_id = int(request.POST.get("producto_id", 0))
            cantidad = max(1, int(request.POST.get("cantidad", 1)))
            punto_coccion = (request.POST.get("punto_coccion") or "").strip()
            comentario = (request.POST.get("comentario") or "").strip()

            producto = get_object_or_404(Producto, id=producto_id, vigente=True)
            carrito.append(
                {
                    "item_uid": str(uuid.uuid4())[:8],
                    "producto_id": producto.id,
                    "nombre": producto.nombre,
                    "estacion": producto.estacion.nombre,
                    "precio": int(producto.precio),
                    "cantidad": cantidad,
                    "subtotal": int(producto.precio) * cantidad,
                    "punto_coccion": punto_coccion,
                    "comentario": comentario,
                }
            )
            request.session[clave_carrito] = carrito
            messages.success(request, f"Agregado al borrador: {cantidad}x {producto.nombre}.")
            return redirect("tomar_pedido", mesa_id=mesa.id)

        if accion == "eliminar_item":
            item_uid = request.POST.get("item_uid")
            carrito = [it for it in carrito if it.get("item_uid") != item_uid]
            request.session[clave_carrito] = carrito
            messages.info(request, "Ítem retirado del borrador antes del envío (RF-07).")
            return redirect("tomar_pedido", mesa_id=mesa.id)

        if accion == "confirmar":
            token = request.POST.get("token_idempotencia")
            try:
                pedido = ServicioPedidos.confirmar_pedido(
                    mesa=mesa,
                    garzon=usuario,
                    items_borrador=carrito,
                    token_idempotencia=token,
                )
                request.session[clave_carrito] = []
                messages.success(
                    request,
                    f"Pedido #{pedido.id} confirmado y comandas enrutadas a producción.",
                )
                return redirect("comandas")
            except ErrorReglaNegocio as exc:
                messages.error(request, str(exc))

    productos = Producto.objects.select_related("estacion").filter(vigente=True)
    venta_abierta = Venta.objects.filter(mesa=mesa, estado=Venta.ABIERTA).first()
    detalles_enviados = (
        DetallePedido.objects.select_related("producto", "pedido")
        .filter(pedido__venta=venta_abierta)
        .order_by("id")
        if venta_abierta
        else []
    )
    total_borrador = sum(item["subtotal"] for item in carrito)

    return render(
        request,
        "operacion/tomar_pedido.html",
        {
            "usuario": usuario,
            "mesa": mesa,
            "productos": productos,
            "carrito": carrito,
            "total_borrador": total_borrador,
            "venta_abierta": venta_abierta,
            "detalles_enviados": detalles_enviados,
            "token_idempotencia": str(uuid.uuid4()),
        },
    )


@rol_requerido(Rol.ADMIN, Rol.GARZON)
def vista_comandas(request: HttpRequest) -> HttpResponse:
    """Visualiza comandas generadas y su estado de impresión por estación (RF-11, RF-12)."""
    comandas = Comanda.objects.select_related("pedido", "pedido__mesa", "estacion").all()[:30]
    pendientes_count = Comanda.objects.filter(estado_impresion=Comanda.ESTADO_PENDIENTE).count()
    return render(
        request,
        "operacion/comandas.html",
        {
            "usuario": request.usuario_sgir,
            "comandas": comandas,
            "pendientes_count": pendientes_count,
        },
    )


@rol_requerido(Rol.ADMIN, Rol.GARZON)
def vista_reintentar_comandas(request: HttpRequest) -> HttpResponse:
    """Ejecuta reintento supervisado de comandas pendientes por fallo de impresora (RNF-07)."""
    if request.method == "POST":
        recuperadas = ServicioImpresion.reintentar_pendientes()
        messages.info(request, f"Reintento completado. Comandas confirmadas: {recuperadas}.")
    return redirect("comandas")


@rol_requerido(Rol.ADMIN, Rol.GARZON)
def vista_anular_producto(request: HttpRequest, detalle_id: int) -> HttpResponse:
    """CU-07: Formulario y ejecución de anulación autorizada por Administrador (RF-17)."""
    detalle = get_object_or_404(
        DetallePedido.objects.select_related("pedido", "pedido__mesa", "producto"),
        id=detalle_id,
    )
    if request.method == "POST":
        try:
            cantidad = int(request.POST.get("cantidad", 1))
            motivo = request.POST.get("motivo", "")
            tipo_salida = request.POST.get("tipo_salida", "")
            observacion = request.POST.get("observacion_motivo", "")
            rut_admin = request.POST.get("rut_admin", "")
            pin_admin = request.POST.get("pin_admin", "")

            ServicioAnulaciones.anular_producto_enviado(
                detalle_id=detalle.id,
                cantidad_a_anular=cantidad,
                motivo=motivo,
                tipo_salida=tipo_salida,
                rut_admin=rut_admin,
                pin_admin=pin_admin,
                observacion_motivo=observacion,
            )
            messages.success(
                request,
                "Anulación autorizada registrada en auditoría, saldo recalculado y aviso enviado a estación.",
            )
            return redirect("tomar_pedido", mesa_id=detalle.pedido.mesa.id)
        except (ErrorReglaNegocio, ValueError) as exc:
            messages.error(request, str(exc))

    return render(
        request,
        "operacion/anular_producto.html",
        {
            "usuario": request.usuario_sgir,
            "detalle": detalle,
            "motivos": AnulacionProducto.MOTIVOS,
            "tipos_salida": AnulacionProducto.TIPOS_SALIDA,
        },
    )


@rol_requerido(Rol.ADMIN, Rol.CAJERO, Rol.GARZON)
def vista_caja(request: HttpRequest) -> HttpResponse:
    """Listado de ventas abiertas y cerradas para precuenta y cobro (RF-13, RF-14)."""
    ventas_abiertas = Venta.objects.select_related("mesa").filter(estado=Venta.ABIERTA)
    ventas_cerradas = Venta.objects.select_related("mesa").filter(estado=Venta.CERRADA)[:15]
    return render(
        request,
        "operacion/caja.html",
        {
            "usuario": request.usuario_sgir,
            "ventas_abiertas": ventas_abiertas,
            "ventas_cerradas": ventas_cerradas,
        },
    )


@rol_requerido(Rol.ADMIN, Rol.CAJERO, Rol.GARZON)
def vista_cobrar_venta(request: HttpRequest, venta_id: int) -> HttpResponse:
    """CU-05: Emisión de precuenta y registro de pago separando consumo y propina (RF-13, RF-14, RF-15)."""
    venta = get_object_or_404(Venta.objects.select_related("mesa"), id=venta_id)
    detalles = DetallePedido.objects.select_related("producto").filter(pedido__venta=venta)
    propina_sugerida = (venta.saldo_pendiente * Decimal("0.10")).quantize(Decimal("1"))

    if request.method == "POST":
        try:
            medio_pago = request.POST.get("medio_pago", Pago.EFECTIVO)
            monto_consumo = Decimal(request.POST.get("monto_consumo", "0"))
            monto_propina = Decimal(request.POST.get("monto_propina", "0"))

            ServicioVentas.registrar_pago_y_cerrar(
                venta_id=venta.id,
                cajero=request.usuario_sgir,
                medio_pago=medio_pago,
                monto_consumo=monto_consumo,
                monto_propina=monto_propina,
            )
            messages.success(
                request,
                f"Pago registrado (Consumo: ${monto_consumo} | Propina: ${monto_propina}). Mesa {venta.mesa.numero} liberada.",
            )
            return redirect("caja")
        except (ErrorReglaNegocio, InvalidOperation) as exc:
            messages.error(request, str(exc))

    return render(
        request,
        "operacion/cobrar_venta.html",
        {
            "usuario": request.usuario_sgir,
            "venta": venta,
            "detalles": detalles,
            "propina_sugerida": propina_sugerida,
            "medios_pago": Pago.MEDIOS,
        },
    )


@rol_requerido(Rol.ADMIN)
def vista_administracion(request: HttpRequest) -> HttpResponse:
    """CU-01 / CU-06: Gestión exclusiva de Administrador para usuarios, estaciones, impresoras y auditoría."""
    if request.method == "POST":
        accion = request.POST.get("accion")

        if accion == "crear_usuario":
            nombre = (request.POST.get("nombre") or "").strip()
            rut = normalizar_rut(request.POST.get("rut", ""))
            pin = (request.POST.get("pin") or "").strip()
            rol_id = request.POST.get("rol_id")
            plaza = (request.POST.get("plaza_asignada") or "Salón Principal").strip()

            if not nombre or not validar_rut_chileno(rut):
                messages.error(request, "Nombre obligatorio y RUT chileno válido (Módulo 11).")
            elif Usuario.objects.filter(rut=rut).exists():
                messages.error(request, "Ya existe un usuario registrado con ese RUT.")
            else:
                try:
                    rol = get_object_or_404(Rol, id=rol_id)
                    Usuario.objects.create(
                        nombre=nombre,
                        rut=rut,
                        pin_hash=generar_hash_pin(pin),
                        rol=rol,
                        plaza_asignada=plaza,
                    )
                    messages.success(request, f"Usuario {nombre} creado con PIN cifrado (RNF-03).")
                except ValueError as exc:
                    messages.error(request, str(exc))
            return redirect("administracion")

        if accion == "toggle_impresora":
            imp = get_object_or_404(Impresora, id=request.POST.get("impresora_id"))
            imp.operativa = not imp.operativa
            imp.save(update_fields=["operativa"])
            estado_txt = "OPERATIVA" if imp.operativa else "FUERA DE LÍNEA (Simulación fallo)"
            messages.info(request, f"Impresora {imp.nombre_dispositivo} cambiada a: {estado_txt}.")
            return redirect("administracion")

    return render(
        request,
        "operacion/administracion.html",
        {
            "usuario": request.usuario_sgir,
            "usuarios": Usuario.objects.select_related("rol").all(),
            "roles": Rol.objects.all(),
            "estaciones": Estacion.objects.all(),
            "impresoras": Impresora.objects.select_related("estacion").all(),
            "anulaciones": AnulacionProducto.objects.select_related(
                "detalle_pedido__producto", "autorizador"
            ).all()[:20],
        },
    )
