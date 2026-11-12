"""Rutas de la interfaz web responsiva del SGIR (Etapa 1)."""
from django.urls import path
from operacion import views

urlpatterns = [
    path("", views.vista_login, name="login"),
    path("logout/", views.vista_logout, name="logout"),
    path("salon/", views.vista_salon, name="salon"),
    path("mesa/<int:mesa_id>/pedido/", views.vista_tomar_pedido, name="tomar_pedido"),
    path("comandas/", views.vista_comandas, name="comandas"),
    path("comandas/reintentar/", views.vista_reintentar_comandas, name="reintentar_comandas"),
    path("detalle/<int:detalle_id>/anular/", views.vista_anular_producto, name="anular_producto"),
    path("caja/", views.vista_caja, name="caja"),
    path("caja/venta/<int:venta_id>/cobrar/", views.vista_cobrar_venta, name="cobrar_venta"),
    path("administracion/", views.vista_administracion, name="administracion"),
]
