# Generated manually for SGIR MVP Etapa 1
from decimal import Decimal
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Estacion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=60, unique=True)),
                ("tipo", models.CharField(default="Producción", max_length=40)),
                ("activa", models.BooleanField(default=True)),
            ],
            options={"verbose_name": "Estación", "verbose_name_plural": "Estaciones"},
        ),
        migrations.CreateModel(
            name="Mesa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero", models.PositiveIntegerField(unique=True)),
                ("sector", models.CharField(default="Salón Principal", max_length=50)),
                ("capacidad", models.PositiveIntegerField(default=4)),
                ("estado", models.CharField(choices=[("DISPONIBLE", "Disponible"), ("OCUPADA", "Ocupada")], default="DISPONIBLE", max_length=15)),
            ],
            options={"verbose_name": "Mesa", "verbose_name_plural": "Mesas", "ordering": ["sector", "numero"]},
        ),
        migrations.CreateModel(
            name="Rol",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(choices=[("ADMIN", "Administrador"), ("GARZON", "Garzón"), ("CAJERO", "Cajero")], max_length=20, unique=True)),
                ("nombre", models.CharField(max_length=50)),
                ("descripcion_permisos", models.TextField(blank=True)),
            ],
            options={"verbose_name": "Rol", "verbose_name_plural": "Roles"},
        ),
        migrations.CreateModel(
            name="Impresora",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("identificador_red", models.CharField(help_text="Dirección IP:Puerto en LAN, ej. 192.168.1.50:9100", max_length=100)),
                ("nombre_dispositivo", models.CharField(max_length=80)),
                ("operativa", models.BooleanField(default=True, help_text="Permite simular desconexión o falta de papel para pruebas RNF-07.")),
                ("estacion", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="impresoras", to="operacion.estacion")),
            ],
            options={"verbose_name": "Impresora", "verbose_name_plural": "Impresoras"},
        ),
        migrations.CreateModel(
            name="Producto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=120)),
                ("categoria", models.CharField(max_length=60)),
                ("precio", models.DecimalField(decimal_places=0, max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
                ("requiere_coccion", models.BooleanField(default=False)),
                ("vigente", models.BooleanField(default=True)),
                ("estacion", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="productos", to="operacion.estacion")),
            ],
            options={"verbose_name": "Producto", "verbose_name_plural": "Productos", "ordering": ["categoria", "nombre"]},
        ),
        migrations.CreateModel(
            name="Usuario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rut", models.CharField(db_index=True, max_length=12, unique=True)),
                ("nombre", models.CharField(max_length=120)),
                ("pin_hash", models.CharField(max_length=256)),
                ("plaza_asignada", models.CharField(default="Salón Principal", help_text="Sector o plaza asignada al garzón antes del turno.", max_length=50)),
                ("activo", models.BooleanField(default=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("rol", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="usuarios", to="operacion.rol")),
            ],
            options={"verbose_name": "Usuario", "verbose_name_plural": "Usuarios"},
        ),
        migrations.CreateModel(
            name="Venta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("estado", models.CharField(choices=[("ABIERTA", "Abierta"), ("CERRADA", "Cerrada")], default="ABIERTA", max_length=15)),
                ("monto_total", models.DecimalField(decimal_places=0, default=Decimal("0"), max_digits=10)),
                ("abierta_en", models.DateTimeField(auto_now_add=True)),
                ("cerrada_en", models.DateTimeField(blank=True, null=True)),
                ("mesa", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ventas", to="operacion.mesa")),
            ],
            options={"verbose_name": "Venta", "verbose_name_plural": "Ventas", "ordering": ["-abierta_en"]},
        ),
        migrations.CreateModel(
            name="Pedido",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_idempotencia", models.CharField(help_text="Previene duplicación por doble envío táctil (RNF-05).", max_length=64, unique=True)),
                ("confirmado_en", models.DateTimeField(auto_now_add=True)),
                ("garzon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pedidos", to="operacion.usuario")),
                ("mesa", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pedidos", to="operacion.mesa")),
                ("venta", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pedidos", to="operacion.venta")),
            ],
            options={"verbose_name": "Pedido", "verbose_name_plural": "Pedidos", "ordering": ["-confirmado_en"]},
        ),
        migrations.CreateModel(
            name="Pago",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("medio_pago", models.CharField(choices=[("EFECTIVO", "Efectivo"), ("TARJETA", "Tarjeta (POS Externo)")], max_length=15)),
                ("monto_consumo", models.DecimalField(decimal_places=0, max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal("1"))])),
                ("monto_propina", models.DecimalField(decimal_places=0, default=Decimal("0"), max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
                ("registrado_en", models.DateTimeField(auto_now_add=True)),
                ("cajero", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="operacion.usuario")),
                ("venta", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pagos", to="operacion.venta")),
            ],
            options={"verbose_name": "Pago", "verbose_name_plural": "Pagos"},
        ),
        migrations.CreateModel(
            name="DetallePedido",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cantidad", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("cantidad_anulada", models.PositiveIntegerField(default=0)),
                ("precio_aplicado", models.DecimalField(decimal_places=0, max_digits=10)),
                ("punto_coccion", models.CharField(blank=True, default="", max_length=40)),
                ("comentario", models.CharField(blank=True, default="", max_length=200)),
                ("estado", models.CharField(choices=[("ACTIVO", "Activo"), ("ANULADO_PARCIAL", "Anulado Parcial"), ("ANULADO_TOTAL", "Anulado Total")], default="ACTIVO", max_length=20)),
                ("pedido", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="detalles", to="operacion.pedido")),
                ("producto", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="operacion.producto")),
            ],
        ),
        migrations.CreateModel(
            name="Comanda",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo_documento", models.CharField(choices=[("PEDIDO", "Comanda de Pedido"), ("AVISO_ANULACION", "Aviso de Anulación")], default="PEDIDO", max_length=20)),
                ("contenido_ticket", models.TextField()),
                ("estado_impresion", models.CharField(choices=[("CONFIRMADA", "Impresión Confirmada"), ("PENDIENTE", "Pendiente de Reintento")], default="PENDIENTE", max_length=15)),
                ("detalle_error", models.CharField(blank=True, default="", max_length=200)),
                ("creada_en", models.DateTimeField(auto_now_add=True)),
                ("estacion", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="operacion.estacion")),
                ("pedido", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="comandas", to="operacion.pedido")),
            ],
            options={"verbose_name": "Comanda", "verbose_name_plural": "Comandas", "ordering": ["-creada_en"]},
        ),
        migrations.CreateModel(
            name="AnulacionProducto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cantidad_anulada", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("motivo", models.CharField(choices=[("ERROR_DIGITACION", "Error de digitación"), ("RECHAZO_CLIENTE", "Rechazo del cliente"), ("DEFECTO_PREPARACION", "Defecto de cocina o barra"), ("OTRO_JUSTIFICADO", "Otro motivo justificado")], max_length=30)),
                ("observacion_motivo", models.CharField(blank=True, default="", max_length=200)),
                ("tipo_salida", models.CharField(choices=[("SIN_SALIDA", "Sin salida (no preparado/despachado)"), ("CON_SALIDA", "Con salida (ya preparado/entregado)")], max_length=15)),
                ("aviso_enviado", models.BooleanField(default=False)),
                ("fecha_hora", models.DateTimeField(auto_now_add=True)),
                ("autorizador", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="anulaciones_autorizadas", to="operacion.usuario")),
                ("detalle_pedido", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="anulaciones", to="operacion.detallepedido")),
            ],
            options={"verbose_name": "Anulación de Producto", "verbose_name_plural": "Anulaciones de Productos", "ordering": ["-fecha_hora"]},
        ),
    ]
