# SGIR - Sistema de Gestión Integral para Restaurantes (MVP Etapa 1)

Prototipo funcional desarrollado para la asignatura **Ingeniería de Software (TI3043 - INACAP)**.
Implementa una arquitectura Cliente-Servidor web responsiva (*Touch-First*) diseñada para operar en **red local (LAN)** sin dependencia de internet (RNF-04), cumpliendo con los **17 Requerimientos Funcionales (RF-01 a RF-17)**, **9 Requerimientos No Funcionales (RNF-01 a RNF-09)**, **12 Reglas de Negocio (RN-01 a RN-12)**, normativa vigente (**Ley N° 21.459** y **Ley N° 19.628**) y controles **OWASP Top 10**.

## Integrantes del Equipo
- Sergio Mutis
- Isaac Vejar
- Javier Bastías

## Estructura Modular del Proyecto (Alineada a Paquetes UML)
- `sgir_config/`: Configuración del servidor, seguridad de sesiones, CSRF y enrutamiento raíz.
- `operacion/models.py`: Modelo lógico de 12 entidades (`Rol`, `Usuario`, `Sucursal`, `Estacion`, `Impresora`, `Mesa`, `Producto`, `Venta`, `Pedido`, `DetallePedido`, `Comanda`, `Pago`, `AnulacionProducto`).
- `operacion/security.py`: Validación de RUT chileno (Módulo 11), hashing criptográfico de PIN (PBKDF2-SHA256 con salt), decoradores RBAC y registro de auditoría (OWASP A01, A02, A03).
- `operacion/services.py`: Lógica de negocio desacoplada (`ServicioPedidos`, `ServicioComandas`, `ServicioImpresion`, `ServicioAnulaciones`, `ServicioVentas`).
- `operacion/views.py`: Controladores web responsivos para Login, Salón/Mesas, Toma de Pedidos, Comandas, Anulación Autorizada (CU-07), Caja y Administración.
- `operacion/tests.py`: Suite de pruebas unitarias, de integración, seguridad OWASP y resiliencia ante fallos de impresión.
- `operacion/management/commands/cargar_datos_prueba.py`: Comando para poblar usuarios, mesas, estaciones, impresoras y carta de prueba.

## Instalación y Ejecución Local (LAN)

1. Crear y activar entorno virtual:
   ```bash
   python -m venv venv
   # En Windows PowerShell:
   .\venv\Scripts\Activate.ps1
   # En Linux/macOS:
   source venv/bin/activate
   ```

2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

3. Aplicar migraciones y cargar datos de prueba coherentes:
   ```bash
   python manage.py migrate
   python manage.py cargar_datos_prueba
   ```

4. Ejecutar pruebas automatizadas:
   ```bash
   python manage.py test operacion -v 2
   ```

5. Iniciar servidor accesible en la red local (LAN):
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```
   Acceder desde navegador o tablet en `http://127.0.0.1:8000/` o `http://<IP-LOCAL-SERVIDOR>:8000/`.

## Credenciales de Prueba Precargadas
| Rol | Nombre | RUT | PIN |
| :--- | :--- | :--- | :--- |
| **Administrador** | Marcelo Moya | `11.111.111-1` | `1234` |
| **Garzón (Plaza Salón)** | Carlos Pérez | `22.222.222-2` | `2345` |
| **Cajero** | Ana Torres | `33.333.333-3` | `3456` |
