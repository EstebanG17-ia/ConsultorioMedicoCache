from datetime import date, time, timedelta

from django.core.management.base import BaseCommand

from citas.api import invalidar_cache_citas
from citas.models import Cita, Paciente

MOTIVOS = ["Consulta general", "Seguimiento", "Control de presión", "Revisión de laboratorio"]
ESTADOS = [Cita.PENDIENTE, Cita.CONFIRMADA, Cita.CANCELADA]


class Command(BaseCommand):
    help = "Agrega citas de prueba (por defecto 2000) para que la diferencia de tiempos sea medible."

    def add_arguments(self, parser):
        parser.add_argument("--total", type=int, default=2000)

    def handle(self, *args, **options):
        pacientes = list(Paciente.objects.all())
        if not pacientes:
            self.stdout.write(self.style.ERROR("Primero ejecuta: python manage.py cargar_datos"))
            return
        total = options["total"]
        base = date(2027, 1, 1)
        citas = [
            Cita(
                paciente=pacientes[i % len(pacientes)],
                fecha=base + timedelta(days=i // 10),
                hora=time(8 + (i % 10), 0),
                motivo=f"{MOTIVOS[i % len(MOTIVOS)]} #{i + 1}",
                estado=ESTADOS[i % len(ESTADOS)],
            )
            for i in range(total)
        ]
        Cita.objects.bulk_create(citas, batch_size=500)
        invalidar_cache_citas()  # bulk_create no dispara signals
        self.stdout.write(self.style.SUCCESS(f"Agregadas {total} citas. Total: {Cita.objects.count()}"))
