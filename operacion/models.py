"""
Modelo de Datos del Sistema de Gestión Integral para Restaurantes (SGIR - Etapa 1).
Implementa fielmente las 12 entidades de la Vista Lógica UML (Enterprise Architect),
garantizando integridad referencial, parametrización por establecimiento y trazabilidad
inmutable de pedidos, comandas, pagos y anulaciones autorizadas (Ley N° 21.459).
"""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator


class Rol(models.Model):
    """Define los perfiles de autorización (Administrador, Garzón, Cajero) para RBAC."""

    ADMIN = "ADMIN"
    GARZON = "GARZON"
    CAJERO = "CAJERO"

    CHOICES_ROL = [
        (ADMIN, "Administrador"),
        (GARZON, "Garzón"),
        (CAJERO, "Cajero"),
    ]

    codigo = models.CharField(max_length=20, choices=CHOICES_ROL, unique=True)
    nombre = models.CharField(max_length=50)
    descripcion_permisos = models.TextField(blank=True)

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    def __str__(self) -> str:
        return self.nombre


class Usuario(models.Model):
    """
    Representa al personal del restaurante (RF-01, RF-02, Ley N° 19.628).
    El PIN nunca se almacena en texto plano; se persiste como hash criptográfico (RNF-03).
    """

    rut = models.CharField(max_length=12, unique=True, db_index=True)
    nombre = models.CharField(max_length=120)
    pin_hash = models.CharField(max_length=256)
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name="usuarios")
    plaza_asignada = models.CharField(
        max_length=50,
        default="Salón Principal",
        help_text="Sector o plaza asignada al garzón antes del turno.",
    )
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self) -> str:
        return f"{self.nombre} ({self.rut}) - {self.rol.nombre}"


class Mesa(models.Model):
    """Representa una mesa configurable dentro de un sector o plaza (RF-04)."""

    DISPONIBLE = "DISPONIBLE"
    OCUPADA = "OCUPADA"

    ESTADOS = [
        (DISPONIBLE, "Disponible"),
        (OCUPADA, "Ocupada"),
    ]

    numero = models.PositiveIntegerField(unique=True)
    sector = models.CharField(max_length=50, default="Salón Principal")
    capacidad = models.PositiveIntegerField(default=4)
    estado = models.CharField(max_length=15, choices=ESTADOS, default=DISPONIBLE)

    class Meta:
        ordering = ["sector", "numero"]
        verbose_name = "Mesa"
        verbose_name_plural = "Mesas"

    def __str__(self) -> str:
        return f"Mesa {self.numero} ({self.sector}) - {self.estado}"


class Estacion(models.Model):
    """Define las áreas de producción configurables: Cocina Caliente, Cocina Fría, Barra (RF-16)."""

    nombre = models.CharField(max_length=60, unique=True)
    tipo = models.CharField(max_length=40, default="Producción")
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Estación"
        verbose_name_plural = "Estaciones"

    def __str__(self) -> str:
        return self.nombre


class Impresora(models.Model):
    """Representa una impresora térmica vinculada a una estación en red local (RF-12, RF-16)."""

    estacion = models.ForeignKey(
        Estacion, on_delete=models.CASCADE, related_name="impresoras"
    )
    identificador_red = models.CharField(
        max_length=100,
        help_text="Dirección IP:Puerto en LAN, ej. 192.168.1.50:9100",
    )
    nombre_dispositivo = models.CharField(max_length=80)
    operativa = models.BooleanField(
        default=True,
        help_text="Permite simular desconexión o falta de papel para pruebas RNF-07.",
    )

    class Meta:
        verbose_name = "Impresora"
        verbose_name_plural = "Impresoras"

    def __str__(self) -> str:
        estado = "Operativa" if self.operativa else "Fuera de línea"
        return f"{self.nombre_dispositivo} ({self.identificador_red}) [{estado}]"


class Producto(models.Model):
    """Representa un ítem de la carta asociado a una estación de destino (RF-05)."""

    nombre = models.CharField(max_length=120)
    categoria = models.CharField(max_length=60)
    precio = models.DecimalField(
        max_digits=10, decimal_places=0, validators=[MinValueValidator(Decimal("0"))]
    )
    estacion = models.ForeignKey(
        Estacion, on_delete=models.PROTECT, related_name="productos"
    )
    requiere_coccion = models.BooleanField(default=False)
    vigente = models.BooleanField(default=True)

    class Meta:
        ordering = ["categoria", "nombre"]
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

    def __str__(self) -> str:
        return f"{self.nombre} (${self.precio})"


class Venta(models.Model):
    """
    Agrupa los pedidos sucesivos de una mesa durante una atención (RF-09, RF-15).
    Mantiene el saldo actualizado ante anulaciones autorizadas (RN-12).
    """

    ABIERTA = "ABIERTA"
    CERRADA = "CERRADA"

    ESTADOS = [
        (ABIERTA, "Abierta"),
        (CERRADA, "Cerrada"),
    ]

    mesa = models.ForeignKey(Mesa, on_delete=models.PROTECT, related_name="ventas")
    estado = models.CharField(max_length=15, choices=ESTADOS, default=ABIERTA)
    monto_total = models.DecimalField(max_digits=10, decimal_places=0, default=Decimal("0"))
    abierta_en = models.DateTimeField(auto_now_add=True)
    cerrada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-abierta_en"]
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"

    @property
    def total_pagado(self) -> Decimal:
        """Calcula el importe acumulado de consumo pagado (sin propina, RN-07)."""
        total = sum((p.monto_consumo for p in self.pagos.all()), Decimal("0"))
        return total

    @property
    def saldo_pendiente(self) -> Decimal:
        """Retorna el saldo pendiente de cobro de la venta."""
        return max(Decimal("0"), self.monto_total - self.total_pagado)

    def __str__(self) -> str:
        return f"Venta #{self.id} - Mesa {self.mesa.numero} ({self.estado}) Total: ${self.monto_total}"


class Pedido(models.Model):
    """Representa un envío confirmado de ítems de una mesa (RF-08, RNF-05, RNF-06)."""

    venta = models.ForeignKey(Venta, on_delete=models.PROTECT, related_name="pedidos")
    mesa = models.ForeignKey(Mesa, on_delete=models.PROTECT, related_name="pedidos")
    garzon = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="pedidos")
    token_idempotencia = models.CharField(
        max_length=64,
        unique=True,
        help_text="Previene duplicación por doble envío táctil (RNF-05).",
    )
    confirmado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-confirmado_en"]
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"

    def __str__(self) -> str:
        return f"Pedido #{self.id} (Mesa {self.mesa.numero} - Garzón {self.garzon.nombre})"


class DetallePedido(models.Model):
    """
    Línea de producto dentro de un pedido confirmado (RF-06, RN-04, RN-05).
    Conserva el precio aplicado histórico y nunca se elimina físicamente.
    """

    ACTIVO = "ACTIVO"
    ANULADO_PARCIAL = "ANULADO_PARCIAL"
    ANULADO_TOTAL = "ANULADO_TOTAL"

    ESTADOS = [
        (ACTIVO, "Activo"),
        (ANULADO_PARCIAL, "Anulado Parcial"),
        (ANULADO_TOTAL, "Anulado Total"),
    ]

    pedido = models.ForeignKey(Pedido, on_delete=models.PROTECT, related_name="detalles")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    cantidad_anulada = models.PositiveIntegerField(default=0)
    precio_aplicado = models.DecimalField(max_digits=10, decimal_places=0)
    punto_coccion = models.CharField(max_length=40, blank=True, default="")
    comentario = models.CharField(max_length=200, blank=True, default="")
    estado = models.CharField(max_length=20, choices=ESTADOS, default=ACTIVO)

    @property
    def cantidad_vigente(self) -> int:
        """Unidades activas cobrables tras descontar anulaciones autorizadas."""
        return max(0, self.cantidad - self.cantidad_anulada)

    @property
    def subtotal_vigente(self) -> Decimal:
        """Subtotal monetario vigente de la línea."""
        return Decimal(self.cantidad_vigente) * self.precio_aplicado

    def __str__(self) -> str:
        return f"{self.cantidad_vigente}/{self.cantidad}x {self.producto.nombre} (Pedido #{self.pedido_id})"


class Comanda(models.Model):
    """
    Documento operativo enviado a una estación de producción o aviso de anulación (RF-10, RF-11, RF-12).
    """

    TIPO_PEDIDO = "PEDIDO"
    TIPO_ANULACION = "AVISO_ANULACION"

    TIPOS = [
        (TIPO_PEDIDO, "Comanda de Pedido"),
        (TIPO_ANULACION, "Aviso de Anulación"),
    ]

    ESTADO_CONFIRMADA = "CONFIRMADA"
    ESTADO_PENDIENTE = "PENDIENTE"

    ESTADOS_IMPRESION = [
        (ESTADO_CONFIRMADA, "Impresión Confirmada"),
        (ESTADO_PENDIENTE, "Pendiente de Reintento"),
    ]

    pedido = models.ForeignKey(Pedido, on_delete=models.PROTECT, related_name="comandas")
    estacion = models.ForeignKey(Estacion, on_delete=models.PROTECT)
    tipo_documento = models.CharField(max_length=20, choices=TIPOS, default=TIPO_PEDIDO)
    contenido_ticket = models.TextField()
    estado_impresion = models.CharField(
        max_length=15, choices=ESTADOS_IMPRESION, default=ESTADO_PENDIENTE
    )
    detalle_error = models.CharField(max_length=200, blank=True, default="")
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creada_en"]
        verbose_name = "Comanda"
        verbose_name_plural = "Comandas"

    def __str__(self) -> str:
        return f"Comanda #{self.id} [{self.tipo_documento}] -> {self.estacion.nombre} ({self.estado_impresion})"


class Pago(models.Model):
    """Registra el cobro de una venta separando consumo y propina (RF-14, RN-07)."""

    EFECTIVO = "EFECTIVO"
    TARJETA = "TARJETA"

    MEDIOS = [
        (EFECTIVO, "Efectivo"),
        (TARJETA, "Tarjeta (POS Externo)"),
    ]

    venta = models.ForeignKey(Venta, on_delete=models.PROTECT, related_name="pagos")
    cajero = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    medio_pago = models.CharField(max_length=15, choices=MEDIOS)
    monto_consumo = models.DecimalField(
        max_digits=10, decimal_places=0, validators=[MinValueValidator(Decimal("1"))]
    )
    monto_propina = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))]
    )
    registrado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"

    def __str__(self) -> str:
        return f"Pago #{self.id} Venta #{self.venta_id}: Consumo ${self.monto_consumo} + Propina ${self.monto_propina}"


class AnulacionProducto(models.Model):
    """
    Bitácora inmutable de anulaciones supervisadas posteriores al envío (RF-17, RNF-09, RN-10, RN-11).
    Garantiza trazabilidad legal conforme a la Ley N° 21.459 (Art. 4° y 7°).
    """

    MOTIVO_DIGITACION = "ERROR_DIGITACION"
    MOTIVO_RECHAZO = "RECHAZO_CLIENTE"
    MOTIVO_DEFECTO = "DEFECTO_PREPARACION"
    MOTIVO_OTRO = "OTRO_JUSTIFICADO"

    MOTIVOS = [
        (MOTIVO_DIGITACION, "Error de digitación"),
        (MOTIVO_RECHAZO, "Rechazo del cliente"),
        (MOTIVO_DEFECTO, "Defecto de cocina o barra"),
        (MOTIVO_OTRO, "Otro motivo justificado"),
    ]

    SIN_SALIDA = "SIN_SALIDA"
    CON_SALIDA = "CON_SALIDA"

    TIPOS_SALIDA = [
        (SIN_SALIDA, "Sin salida (no preparado/despachado)"),
        (CON_SALIDA, "Con salida (ya preparado/entregado)"),
    ]

    detalle_pedido = models.ForeignKey(
        DetallePedido, on_delete=models.PROTECT, related_name="anulaciones"
    )
    autorizador = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, related_name="anulaciones_autorizadas"
    )
    cantidad_anulada = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    motivo = models.CharField(max_length=30, choices=MOTIVOS)
    observacion_motivo = models.CharField(max_length=200, blank=True, default="")
    tipo_salida = models.CharField(max_length=15, choices=TIPOS_SALIDA)
    aviso_enviado = models.BooleanField(default=False)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_hora"]
        verbose_name = "Anulación de Producto"
        verbose_name_plural = "Anulaciones de Productos"

    def __str__(self) -> str:
        return (
            f"Anulación #{self.id} - {self.cantidad_anulada}x {self.detalle_pedido.producto.nombre} "
            f"[{self.motivo} / {self.tipo_salida}] por {self.autorizador.nombre}"
        )
