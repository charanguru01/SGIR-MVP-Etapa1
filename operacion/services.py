"""
Capa de Servicios de Negocio del SGIR (Etapa 1).
Implementa la lógica transaccional desacoplada de las vistas HTTP:
- ServicioPedidos: Armado, confirmación con idempotencia (RNF-05) y cálculo de venta (RF-08, RF-09).
- ServicioComandas: Enrutamiento automático de ítems por estación configurada (RF-10, RF-11, RN-06).
- ServicioImpresion: Despacho a impresoras locales con manejo de fallos y cola de reintento (RF-12, RNF-07).
- ServicioAnulaciones: Flujo supervisado CU-07 con auditoría inmutable y aviso a producción (RF-17, RNF-09).
- ServicioVentas: Registro de pago separado (consumo y propina) y cierre seguro de mesa (RF-14, RF-15, RN-07, RN-08).
"""
from decimal import Decimal
import uuid
from django.db import transaction
from django.utils import timezone
from operacion.models import (
    AnulacionProducto,
    Comanda,
    DetallePedido,
    Estacion,
    Mesa,
    Pago,
    Pedido,
    Producto,
    Rol,
    Usuario,
    Venta,
)
from operacion.security import normalizar_rut, verificar_pin


class ErrorReglaNegocio(Exception):
    """Excepción controlada cuando se incumple una regla de negocio RN-01 a RN-12."""


class ServicioImpresion:
    """Gestiona la transmisión de comandas a impresoras de estación en LAN (RF-12, RNF-07)."""

    @staticmethod
    def despachar_comanda(comanda: Comanda) -> Comanda:
        """
        Envía el ticket a la impresora operativa asociada a la estación.
        Si no existe impresora operativa, conserva la comanda en estado PENDIENTE sin perder datos (RN-09).
        """
        impresora = comanda.estacion.impresoras.filter(operativa=True).first()
        if impresora is None:
            comanda.estado_impresion = Comanda.ESTADO_PENDIENTE
            comanda.detalle_error = (
                f"Sin impresora operativa en estación '{comanda.estacion.nombre}'. Queda en cola de reintento."
            )
            comanda.save(update_fields=["estado_impresion", "detalle_error"])
            return comanda

        # Simulación determinística de envío ESC/POS por socket local LAN
        comanda.estado_impresion = Comanda.ESTADO_CONFIRMADA
        comanda.detalle_error = f"Impreso correctamente en {impresora.nombre_dispositivo} ({impresora.identificador_red})"
        comanda.save(update_fields=["estado_impresion", "detalle_error"])
        return comanda

    @classmethod
    def reintentar_pendientes(cls) -> int:
        """Reintenta el envío de todas las comandas marcadas como PENDIENTE (RNF-07)."""
        pendientes = Comanda.objects.filter(estado_impresion=Comanda.ESTADO_PENDIENTE)
        confirmadas = 0
        for comanda in pendientes:
            actualizada = cls.despachar_comanda(comanda)
            if actualizada.estado_impresion == Comanda.ESTADO_CONFIRMADA:
                confirmadas += 1
        return confirmadas


class ServicioComandas:
    """Agrupa los ítems de un pedido por estación de destino y genera comandas (RF-10, RF-11, RN-06)."""

    @staticmethod
    def generar_comandas_pedido(pedido: Pedido) -> list[Comanda]:
        """Separa los detalles del pedido según su estación configurada y las despacha."""
        detalles = pedido.detalles.select_related("producto", "producto__estacion").all()
        agrupado: dict[Estacion, list[DetallePedido]] = {}
        for det in detalles:
            est = det.producto.estacion
            agrupado.setdefault(est, []).append(det)

        comandas_creadas: list[Comanda] = []
        for estacion, lista_detalles in agrupado.items():
            lineas = [
                f"=== COMANDA #{pedido.id} | MESA {pedido.mesa.numero} ({pedido.mesa.sector}) ===",
                f"Estación: {estacion.nombre} | Garzón: {pedido.garzon.nombre}",
                f"Hora: {timezone.localtime(pedido.confirmado_en).strftime('%H:%M:%S')}",
                "-" * 42,
            ]
            for d in lista_detalles:
                extra = []
                if d.punto_coccion:
                    extra.append(f"Cocción: {d.punto_coccion}")
                if d.comentario:
                    extra.append(f"Nota: {d.comentario}")
                sufijo = f" ({' | '.join(extra)})" if extra else ""
                lineas.append(f"- {d.cantidad}x {d.producto.nombre}{sufijo}")

            comanda = Comanda.objects.create(
                pedido=pedido,
                estacion=estacion,
                tipo_documento=Comanda.TIPO_PEDIDO,
                contenido_ticket="\n".join(lineas),
            )
            ServicioImpresion.despachar_comanda(comanda)
            comandas_creadas.append(comanda)

        return comandas_creadas


class ServicioPedidos:
    """Gestiona la confirmación transaccional de pedidos y apertura de cuenta (RF-08, RF-09, RNF-05)."""

    @staticmethod
    @transaction.atomic
    def confirmar_pedido(
        mesa: Mesa,
        garzon: Usuario,
        items_borrador: list[dict],
        token_idempotencia: str | None = None,
    ) -> Pedido:
        """
        Confirma un pedido de mesa, crea o recupera la venta abierta, persiste el detalle con
        precios vigentes (RN-05) y enruta comandas a producción.
        """
        if not items_borrador:
            raise ErrorReglaNegocio("No se puede confirmar un pedido sin productos.")

        token = token_idempotencia or str(uuid.uuid4())
        existente = Pedido.objects.filter(token_idempotencia=token).first()
        if existente is not None:
            # Idempotencia (RNF-05): evita duplicar ventas o comandas ante doble clic
            return existente

        venta, _ = Venta.objects.get_or_create(
            mesa=mesa,
            estado=Venta.ABIERTA,
            defaults={"monto_total": Decimal("0")},
        )

        pedido = Pedido.objects.create(
            venta=venta,
            mesa=mesa,
            garzon=garzon,
            token_idempotencia=token,
        )

        subtotal_pedido = Decimal("0")
        for item in items_borrador:
            producto = Producto.objects.get(id=item["producto_id"], vigente=True)
            cantidad = int(item["cantidad"])
            if cantidad < 1:
                raise ErrorReglaNegocio("La cantidad de cada producto debe ser mayor o igual a 1.")

            precio_unitario = producto.precio  # Congela precio vigente (RN-05)
            DetallePedido.objects.create(
                pedido=pedido,
                producto=producto,
                cantidad=cantidad,
                precio_aplicado=precio_unitario,
                punto_coccion=(item.get("punto_coccion") or "")[:40],
                comentario=(item.get("comentario") or "")[:200],
            )
            subtotal_pedido += Decimal(cantidad) * precio_unitario

        venta.monto_total += subtotal_pedido
        venta.save(update_fields=["monto_total"])

        if mesa.estado != Mesa.OCUPADA:
            mesa.estado = Mesa.OCUPADA
            mesa.save(update_fields=["estado"])

        ServicioComandas.generar_comandas_pedido(pedido)
        return pedido


class ServicioAnulaciones:
    """
    Implementa el flujo excepcional CU-07: Anulación supervisada de productos enviados (RF-17, RNF-09).
    Cumple RN-04, RN-10, RN-11 y RN-12 sin eliminar jamás registros históricos.
    """

    @staticmethod
    @transaction.atomic
    def anular_producto_enviado(
        detalle_id: int,
        cantidad_a_anular: int,
        motivo: str,
        tipo_salida: str,
        rut_admin: str,
        pin_admin: str,
        observacion_motivo: str = "",
    ) -> AnulacionProducto:
        """Valida autorización de administrador, registra bitácora inmutable, recalcula saldo y avisa estación."""
        rut_norm = normalizar_rut(rut_admin)
        admin_user = (
            Usuario.objects.select_related("rol")
            .filter(rut=rut_norm, activo=True, rol__codigo=Rol.ADMIN)
            .first()
        )
        if admin_user is None or not verificar_pin(pin_admin, admin_user.pin_hash):
            raise ErrorReglaNegocio(
                "Autorización denegada: Credenciales de Administrador inválidas (RN-10)."
            )

        detalle = DetallePedido.objects.select_for_update().select_related(
            "pedido", "pedido__venta", "pedido__mesa", "producto", "producto__estacion"
        ).get(id=detalle_id)

        venta = detalle.pedido.venta
        if venta.estado != Venta.ABIERTA:
            raise ErrorReglaNegocio(
                "No es posible anular ítems de una venta cerrada (RN-12)."
            )

        if cantidad_a_anular < 1 or cantidad_a_anular > detalle.cantidad_vigente:
            raise ErrorReglaNegocio(
                f"Cantidad inválida. Máximo anulable disponible: {detalle.cantidad_vigente}."
            )

        motivos_validos = {m[0] for m in AnulacionProducto.MOTIVOS}
        if motivo not in motivos_validos:
            raise ErrorReglaNegocio("Debe seleccionar un motivo tipificado válido (RN-10).")

        salidas_validas = {s[0] for s in AnulacionProducto.TIPOS_SALIDA}
        if tipo_salida not in salidas_validas:
            raise ErrorReglaNegocio("Debe especificar si la anulación es Sin Salida o Con Salida (RN-11).")

        # Actualizar estado lógico del detalle sin borrar registro original (RN-04)
        detalle.cantidad_anulada += cantidad_a_anular
        if detalle.cantidad_vigente == 0:
            detalle.estado = DetallePedido.ANULADO_TOTAL
        else:
            detalle.estado = DetallePedido.ANULADO_PARCIAL
        detalle.save(update_fields=["cantidad_anulada", "estado"])

        # Recalcular saldo de la venta abierta
        descuento = Decimal(cantidad_a_anular) * detalle.precio_aplicado
        venta.monto_total = max(Decimal("0"), venta.monto_total - descuento)
        venta.save(update_fields=["monto_total"])

        # Generar aviso de anulación hacia la estación responsable
        estacion = detalle.producto.estacion
        ticket_aviso = "\n".join(
            [
                f"*** AVISO DE ANULACIÓN | MESA {detalle.pedido.mesa.numero} ***",
                f"Pedido Original: #{detalle.pedido.id} | Estación: {estacion.nombre}",
                f"Producto Anulado: {cantidad_a_anular}x {detalle.producto.nombre}",
                f"Condición: {tipo_salida} | Motivo: {motivo}",
                f"Autorizado por: {admin_user.nombre} ({admin_user.rut})",
            ]
        )
        comanda_aviso = Comanda.objects.create(
            pedido=detalle.pedido,
            estacion=estacion,
            tipo_documento=Comanda.TIPO_ANULACION,
            contenido_ticket=ticket_aviso,
        )
        ServicioImpresion.despachar_comanda(comanda_aviso)

        anulacion = AnulacionProducto.objects.create(
            detalle_pedido=detalle,
            autorizador=admin_user,
            cantidad_anulada=cantidad_a_anular,
            motivo=motivo,
            observacion_motivo=observacion_motivo[:200],
            tipo_salida=tipo_salida,
            aviso_enviado=(comanda_aviso.estado_impresion == Comanda.ESTADO_CONFIRMADA),
        )
        return anulacion


class ServicioVentas:
    """Gestiona pagos con separación de consumo/propina y cierre de venta (RF-14, RF-15, RN-07, RN-08)."""

    @staticmethod
    @transaction.atomic
    def registrar_pago_y_cerrar(
        venta_id: int,
        cajero: Usuario,
        medio_pago: str,
        monto_consumo: Decimal,
        monto_propina: Decimal = Decimal("0"),
    ) -> Pago:
        """Registra el pago separando consumo y propina; cierra la venta y libera mesa si saldo llega a cero."""
        venta = Venta.objects.select_for_update().select_related("mesa").get(id=venta_id)
        if venta.estado != Venta.ABIERTA:
            raise ErrorReglaNegocio("Esta venta ya se encuentra cerrada.")

        if monto_consumo <= Decimal("0"):
            raise ErrorReglaNegocio("El importe del consumo debe ser mayor a $0.")

        if monto_propina < Decimal("0"):
            raise ErrorReglaNegocio("La propina no puede ser negativa.")

        saldo_actual = venta.saldo_pendiente
        if monto_consumo < saldo_actual:
            raise ErrorReglaNegocio(
                f"Pago insuficiente (${monto_consumo}). Saldo pendiente de la venta: ${saldo_actual} (RN-08)."
            )

        pago = Pago.objects.create(
            venta=venta,
            cajero=cajero,
            medio_pago=medio_pago,
            monto_consumo=monto_consumo,
            monto_propina=monto_propina,
        )

        # Verificar saldo cero antes de liberar la mesa (RF-15, RN-08)
        if venta.saldo_pendiente == Decimal("0"):
            venta.estado = Venta.CERRADA
            venta.cerrada_en = timezone.now()
            venta.save(update_fields=["estado", "cerrada_en"])

            mesa = venta.mesa
            mesa.estado = Mesa.DISPONIBLE
            mesa.save(update_fields=["estado"])

        return pago
