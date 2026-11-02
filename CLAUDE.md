# Reglas del proyecto: Motor de Reposicion de Inventario

- Toda la logica vive en `src/reposicion/`; los DAGs en `dags/` solo orquestan.
- La bandeja (`data/landing/`) es un sistema externo: se lee, nunca se modifica.
- Una prediccion solo usa informacion disponible en su fecha de corte.
- Las tareas son idempotentes: reejecutar produce el mismo resultado.
- Costos de negocio solo en `config/costos.yaml`, nunca en el codigo.
- Datos y modelos van en DVC, nunca en Git.
- Nada llega a `main` sin Pull Request y pytest en verde.
- Commits con formato `tipo(alcance): descripcion`; agregar archivos por nombre.
- Las pruebas usan datos sinteticos pequenos.
