"""
Módulo de Seguridad, Validación y Control de Acceso (OWASP Top 10 + Leyes N° 21.459 y N° 19.628).
Implementa:
- Normalización y validación de RUT chileno mediante algoritmo Módulo 11 (OWASP A03).
- Hashing criptográfico unidireccional de PIN mediante PBKDF2-SHA256 con salt aleatorio (OWASP A02, RNF-03).
- Decoradores de autorización estricta basada en roles RBAC (OWASP A01, RF-03).
"""
from functools import wraps
import re
from django.contrib.auth.hashers import check_password, make_password
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from operacion.models import Usuario


def normalizar_rut(rut_raw: str) -> str:
    """Limpia puntos, espacios y estandariza guion y dígito verificador en mayúscula."""
    limpio = re.sub(r"[^0-9kK]", "", (rut_raw or "").strip()).upper()
    if len(limpio) < 2:
        return limpio
    return f"{limpio[:-1]}-{limpio[-1]}"


def validar_rut_chileno(rut_raw: str) -> bool:
    """Valida el formato y dígito verificador de un RUT chileno mediante Módulo 11."""
    rut = normalizar_rut(rut_raw)
    if not re.match(r"^\d{7,8}-[0-9K]$", rut):
        return False

    cuerpo, dv = rut.split("-")
    suma = 0
    multiplicador = 2
    for digito in reversed(cuerpo):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1

    resto = 11 - (suma % 11)
    if resto == 11:
        dv_esperado = "0"
    elif resto == 10:
        dv_esperado = "K"
    else:
        dv_esperado = str(resto)

    return dv == dv_esperado


def generar_hash_pin(pin_plano: str) -> str:
    """
    Genera un hash criptográfico PBKDF2-SHA256 con salt único para almacenar el PIN (RNF-03).
    Valida que el PIN contenga exactamente 4 dígitos numéricos.
    """
    if not re.match(r"^\d{4}$", str(pin_plano or "")):
        raise ValueError("El PIN debe contener exactamente 4 dígitos numéricos.")
    return make_password(str(pin_plano))


def verificar_pin(pin_plano: str, pin_hash: str) -> bool:
    """Compara de forma segura (tiempo constante) el PIN ingresado contra su hash."""
    if not pin_plano or not pin_hash:
        return False
    return check_password(str(pin_plano), pin_hash)


def obtener_usuario_sesion(request: HttpRequest) -> Usuario | None:
    """Recupera la instancia activa del Usuario autenticado en la sesión actual."""
    usuario_id = request.session.get("sgir_usuario_id")
    if not usuario_id:
        return None
    return Usuario.objects.select_related("rol").filter(id=usuario_id, activo=True).first()


def rol_requerido(*roles_permitidos: str):
    """
    Middleware/Decorador RBAC (OWASP A01: Broken Access Control).
    Bloquea peticiones sin sesión válida o cuyo rol no esté explícitamente autorizado.
    """

    def decorador(vista_func):
        @wraps(vista_func)
        def _wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            usuario = obtener_usuario_sesion(request)
            if usuario is None:
                return redirect("login")
            if roles_permitidos and usuario.rol.codigo not in roles_permitidos:
                return HttpResponseForbidden(
                    "Acceso denegado (OWASP A01 / RBAC): Su rol no tiene permisos para esta operación."
                )
            request.usuario_sgir = usuario
            return vista_func(request, *args, **kwargs)

        return _wrapped

    return decorador
