# Garay Tours

Sistema unificado para la agencia operadora de turismo **Garay Tours**: tiquetera (registro
de ventas y comisiones), control de entradas/salidas de dinero y conciliacion.

## Arquitectura

Arquitectura hexagonal. El dominio (tiquetera, comisiones, conciliacion, cupos) vive aislado
de los frameworks (Telegram, FastAPI) y de la base de datos.

```
src/garay/
  dominio/          # Nucleo: entidades, value objects, servicios y puertos. No conoce frameworks.
  aplicacion/       # Casos de uso que orquestan el dominio.
  infraestructura/  # Adaptadores: persistencia, mensajeria, observabilidad, extraccion IA.
  config/           # Configuracion centralizada (sin hardcoding).
  mensajes/         # Catalogo centralizado de textos de usuario (i18n-ready).
```

## Requisitos

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/)

## Puesta en marcha

```bash
uv sync                # crea el entorno e instala dependencias
uv run pytest          # corre los tests
uv run mypy            # chequeo estatico de tipos (strict)
uv run ruff check      # lint
```

## Estandares

Ver [`docs/ESTANDARES.md`](docs/ESTANDARES.md).
