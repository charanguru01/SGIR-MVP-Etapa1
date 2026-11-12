"""Comando de administración para poblar el prototipo SGIR con datos coherentes del caso de estudio."""
from decimal import Decimal
from django.core.management.base import BaseCommand
from operacion.models import Estacion, Impresora, Mesa, Producto, Rol, Usuario
from operacion.security import generar_hash_pin


class Command(BaseCommand):
    """Carga roles, usuarios (con PIN hasheado), mesas, estaciones, impresoras y carta gastronómica."""

    help = "Puebla la base de datos local con datos iniciales coherentes para el MVP SGIR."

    def handle(self, *args, **options) -> None:
        rol_admin, _ = Rol.objects.get_or_create(
            codigo=Rol.ADMIN,
            defaults={
                "nombre": "Administrador",
                "descripcion_permisos": "Acceso total, gestión de usuarios, estaciones y autorización de anulaciones CU-07.",
            },
        )
        rol_garzon, _ = Rol.objects.get_or_create(
            codigo=Rol.GARZON,
            defaults={
                "nombre": "Garzón",
                "descripcion_permisos": "Consulta de mesas de su plaza, toma y envío de pedidos, emisión de precuenta.",
            },
        )
        rol_cajero, _ = Rol.objects.get_or_create(
            codigo=Rol.CAJERO,
            defaults={
                "nombre": "Cajero",
                "descripcion_permisos": "Consulta de ventas abiertas, registro de pagos con propina separada y cierre de venta.",
            },
        )

        usuarios_demo = [
            ("Marcelo Moya", "11.111.111-1", "1234", rol_admin, "Salón Principal"),
            ("Carlos Pérez", "22.222.222-2", "2345", rol_garzon, "Salón Principal"),
            ("Ana Torres", "33.333.333-3", "3456", rol_cajero, "Caja Central"),
        ]
        for nombre, rut, pin, rol, plaza in usuarios_demo:
            Usuario.objects.get_or_create(
                rut=rut,
                defaults={
                    "nombre": nombre,
                    "pin_hash": generar_hash_pin(pin),
                    "rol": rol,
                    "plaza_asignada": plaza,
                },
            )

        for num in range(1, 7):
            Mesa.objects.get_or_create(
                numero=num,
                defaults={"sector": "Salón Principal", "capacidad": 4},
            )

        cocina_caliente, _ = Estacion.objects.get_or_create(nombre="Cocina Caliente", defaults={"tipo": "Cocina"})
        cocina_fria, _ = Estacion.objects.get_or_create(nombre="Cocina Fría", defaults={"tipo": "Cocina"})
        barra, _ = Estacion.objects.get_or_create(nombre="Barra", defaults={"tipo": "Bebestibles"})

        Impresora.objects.get_or_create(
            estacion=cocina_caliente,
            defaults={"identificador_red": "192.168.1.51:9100", "nombre_dispositivo": "Epson TM-T20 Cocina Caliente"},
        )
        Impresora.objects.get_or_create(
            estacion=cocina_fria,
            defaults={"identificador_red": "192.168.1.52:9100", "nombre_dispositivo": "Epson TM-T20 Cocina Fría"},
        )
        Impresora.objects.get_or_create(
            estacion=barra,
            defaults={"identificador_red": "192.168.1.53:9100", "nombre_dispositivo": "Epson TM-T20 Barra"},
        )

        carta = [
            ("Lomo Vetado a la Parrilla", "Fondos", Decimal("14900"), cocina_caliente, True),
            ("Salmón Grillado con Quinoa", "Fondos", Decimal("13500"), cocina_caliente, True),
            ("Ceviche Clásico Reineta", "Entradas", Decimal("9800"), cocina_fria, False),
            ("Tabla Mixta de la Casa", "Entradas", Decimal("12900"), cocina_fria, False),
            ("Pisco Sour Catedral", "Coctelería", Decimal("6500"), barra, False),
            ("Jugo Natural Frambuesa", "Bebestibles", Decimal("3800"), barra, False),
        ]
        for nombre, cat, precio, est, coccion in carta:
            Producto.objects.get_or_create(
                nombre=nombre,
                defaults={
                    "categoria": cat,
                    "precio": precio,
                    "estacion": est,
                    "requiere_coccion": coccion,
                },
            )

        self.stdout.write(self.style.SUCCESS("Datos de prueba SGIR cargados exitosamente."))
