"""
Suite de Pruebas Unitarias, de Integración, Seguridad OWASP y Resiliencia Operativa del SGIR.
Valida el cumplimiento de los criterios de aceptación (RF-01 a RF-17, RNF-03 a RNF-09, RN-01 a RN-12).
"""
from decimal import Decimal
import time
from django.test import Client, TestCase
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
from operacion.security import generar_hash_pin, validar_rut_chileno, verificar_pin
from operacion.services import (
    ErrorReglaNegocio,
    ServicioAnulaciones,
    ServicioImpresion,
    ServicioPedidos,
    ServicioVentas,
)


class SGIRPlanPruebasIntegralTestCase(TestCase):
    """Casos de prueba documentados en la Sección VI (Plan de Pruebas Integral)."""

    def setUp(self) -> None:
        self.rol_admin = Rol.objects.create(codigo=Rol.ADMIN, nombre="Administrador")
        self.rol_garzon = Rol.objects.create(codigo=Rol.GARZON, nombre="Garzón")
        self.rol_cajero = Rol.objects.create(codigo=Rol.CAJERO, nombre="Cajero")

        self.admin = Usuario.objects.create(
            rut="11.111.111-1",
            nombre="Marcelo Moya",
            pin_hash=generar_hash_pin("1234"),
            rol=self.rol_admin,
            plaza_asignada="Salón Principal",
        )
        self.garzon = Usuario.objects.create(
            rut="22.222.222-2",
            nombre="Carlos Pérez",
            pin_hash=generar_hash_pin("2345"),
            rol=self.rol_garzon,
            plaza_asignada="Salón Principal",
        )
        self.cajero = Usuario.objects.create(
            rut="33.333.333-3",
            nombre="Ana Torres",
            pin_hash=generar_hash_pin("3456"),
            rol=self.rol_cajero,
            plaza_asignada="Caja Central",
        )

        self.mesa1 = Mesa.objects.create(numero=1, sector="Salón Principal", capacidad=4)
        self.cocina = Estacion.objects.create(nombre="Cocina Caliente")
        self.barra = Estacion.objects.create(nombre="Barra")

        self.imp_cocina = Impresora.objects.create(
            estacion=self.cocina,
            identificador_red="192.168.1.51:9100",
            nombre_dispositivo="Impresora Cocina",
            operativa=True,
        )
        self.imp_barra = Impresora.objects.create(
            estacion=self.barra,
            identificador_red="192.168.1.53:9100",
            nombre_dispositivo="Impresora Barra",
            operativa=True,
        )

        self.plato = Producto.objects.create(
            nombre="Lomo Vetado",
            categoria="Fondos",
            precio=Decimal("15000"),
            estacion=self.cocina,
            requiere_coccion=True,
        )
        self.bebida = Producto.objects.create(
            nombre="Pisco Sour",
            categoria="Coctelería",
            precio=Decimal("6000"),
            estacion=self.barra,
        )
        self.client = Client()

    def test_cp01_validacion_rut_y_hashing_pin_owasp_a02(self) -> None:
        """CP-01 (RF-01, RNF-03, OWASP A02): Valida RUT Módulo 11 y almacenamiento cifrado del PIN."""
        self.assertTrue(validar_rut_chileno("11.111.111-1"))
        self.assertFalse(validar_rut_chileno("11.111.111-9"))
        self.assertNotEqual(self.admin.pin_hash, "1234")
        self.assertTrue(self.admin.pin_hash.startswith("pbkdf2_sha256$"))
        self.assertTrue(verificar_pin("1234", self.admin.pin_hash))
        self.assertFalse(verificar_pin("9999", self.admin.pin_hash))

    def test_cp02_control_acceso_rbac_owasp_a01(self) -> None:
        """CP-02 (RF-02, RF-03, OWASP A01): Garzón no puede acceder a Administración (HTTP 403)."""
        resp_login = self.client.post("/", {"rut": "22.222.222-2", "pin": "2345"})
        self.assertEqual(resp_login.status_code, 302)
        resp_admin = self.client.get("/administracion/")
        self.assertEqual(resp_admin.status_code, 403)

    def test_cp03_enrutamiento_comandas_por_estacion_e_idempotencia(self) -> None:
        """CP-03 (RF-08, RF-10, RF-11, RNF-05): Separa comandas Cocina/Barra y evita duplicados."""
        inicio = time.perf_counter()
        items = [
            {"producto_id": self.plato.id, "cantidad": 2, "punto_coccion": "A punto", "comentario": "Sin sal"},
            {"producto_id": self.bebida.id, "cantidad": 1, "punto_coccion": "", "comentario": ""},
        ]
        pedido1 = ServicioPedidos.confirmar_pedido(self.mesa1, self.garzon, items, token_idempotencia="tok-100")
        pedido2 = ServicioPedidos.confirmar_pedido(self.mesa1, self.garzon, items, token_idempotencia="tok-100")
        duracion_ms = (time.perf_counter() - inicio) * 1000

        self.assertEqual(pedido1.id, pedido2.id)
        self.assertLess(duracion_ms, 500)
        self.assertEqual(Comanda.objects.filter(pedido=pedido1).count(), 2)
        self.assertEqual(Venta.objects.get(mesa=self.mesa1).monto_total, Decimal("36000"))

    def test_cp04_resiliencia_fallo_impresora_y_reintento(self) -> None:
        """CP-04 (RF-12, RNF-07, RN-09): Si falla impresora, comanda queda PENDIENTE y luego se recupera."""
        self.imp_cocina.operativa = False
        self.imp_cocina.save()

        items = [{"producto_id": self.plato.id, "cantidad": 1}]
        pedido = ServicioPedidos.confirmar_pedido(self.mesa1, self.garzon, items)
        comanda = Comanda.objects.get(pedido=pedido)
        self.assertEqual(comanda.estado_impresion, Comanda.ESTADO_PENDIENTE)

        self.imp_cocina.operativa = True
        self.imp_cocina.save()
        recuperadas = ServicioImpresion.reintentar_pendientes()
        self.assertEqual(recuperadas, 1)
        comanda.refresh_from_db()
        self.assertEqual(comanda.estado_impresion, Comanda.ESTADO_CONFIRMADA)

    def test_cp05_anulacion_autorizada_cu07_y_auditoria_inmutable(self) -> None:
        """CP-05 (RF-17, RNF-09, RN-10, RN-11): Exige PIN Admin, mantiene historial y ajusta saldo."""
        items = [{"producto_id": self.plato.id, "cantidad": 2}]
        pedido = ServicioPedidos.confirmar_pedido(self.mesa1, self.garzon, items)
        detalle = pedido.detalles.first()

        # Intento con PIN de garzón debe ser rechazado
        with self.assertRaises(ErrorReglaNegocio):
            ServicioAnulaciones.anular_producto_enviado(
                detalle_id=detalle.id,
                cantidad_a_anular=1,
                motivo=AnulacionProducto.MOTIVO_DIGITACION,
                tipo_salida=AnulacionProducto.SIN_SALIDA,
                rut_admin="22.222.222-2",
                pin_admin="2345",
            )

        # Autorización válida de Administrador
        anulacion = ServicioAnulaciones.anular_producto_enviado(
            detalle_id=detalle.id,
            cantidad_a_anular=1,
            motivo=AnulacionProducto.MOTIVO_DIGITACION,
            tipo_salida=AnulacionProducto.SIN_SALIDA,
            rut_admin="11.111.111-1",
            pin_admin="1234",
        )
        detalle.refresh_from_db()
        self.assertEqual(detalle.cantidad_vigente, 1)
        self.assertEqual(detalle.estado, DetallePedido.ANULADO_PARCIAL)
        self.assertEqual(Venta.objects.get(mesa=self.mesa1).monto_total, Decimal("15000"))
        self.assertTrue(anulacion.aviso_enviado)

    def test_cp06_pago_propina_separada_y_cierre_mesa(self) -> None:
        """CP-06 (RF-14, RF-15, RN-07, RN-08): Separa consumo y propina; libera mesa solo con saldo cero."""
        items = [{"producto_id": self.bebida.id, "cantidad": 2}]
        ServicioPedidos.confirmar_pedido(self.mesa1, self.garzon, items)
        venta = Venta.objects.get(mesa=self.mesa1, estado=Venta.ABIERTA)

        # Rechaza pago menor al saldo pendiente (RN-08)
        with self.assertRaises(ErrorReglaNegocio):
            ServicioVentas.registrar_pago_y_cerrar(
                venta_id=venta.id,
                cajero=self.cajero,
                medio_pago=Pago.EFECTIVO,
                monto_consumo=Decimal("10000"),
                monto_propina=Decimal("1000"),
            )

        pago = ServicioVentas.registrar_pago_y_cerrar(
            venta_id=venta.id,
            cajero=self.cajero,
            medio_pago=Pago.TARJETA,
            monto_consumo=Decimal("12000"),
            monto_propina=Decimal("1200"),
        )
        venta.refresh_from_db()
        self.mesa1.refresh_from_db()
        self.assertEqual(pago.monto_propina, Decimal("1200"))
        self.assertEqual(venta.estado, Venta.CERRADA)
        self.assertEqual(self.mesa1.estado, Mesa.DISPONIBLE)
