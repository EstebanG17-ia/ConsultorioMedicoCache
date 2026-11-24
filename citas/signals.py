from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .api import invalidar_cache_citas
from .models import Cita, Paciente


@receiver([post_save, post_delete], sender=Cita)
@receiver([post_save, post_delete], sender=Paciente)
def invalidar_al_cambiar(sender, **kwargs):
    # El JSON incluye nombre y apellido del paciente, así que un cambio en
    # Paciente también afecta el resultado almacenado.
    invalidar_cache_citas()
