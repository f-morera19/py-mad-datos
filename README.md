# traficFines

Paquete de Python para **descargar, limpiar y analizar las multas de tráfico** que publica el Ayuntamiento de Madrid en su [portal de datos abiertos](https://datos.madrid.es/dataset/210104-0-multas-circulacion-detalle/downloads).

Tarea del curso de **Python Avanzado** del Máster de Big Data y Data Engineering de la UCM.

El paquete permite:

- Localizar mediante *scraping* el CSV de multas de cualquier mes publicado (desde junio de 2017).
- Descargar los datos una sola vez y guardarlos en una **caché en disco** con caducidad configurable.
- Limpiar y normalizar los datos (nombres de columna, espacios, columnas numéricas y fecha).
- Analizarlos: multas por hora del día (gráfico), por calificación y el importe total recaudado por mes.

---

## Contenido de la entrega

```
traficFines/
├── README.md                     Este fichero
├── pyproject.toml                Configuración y dependencias del paquete
├── uv.lock                       Versiones exactas de las dependencias
├── dist/
│   └── traficfines-1.0.0-py3-none-any.whl   Paquete instalable
├── src/traficFines/
│   ├── __init__.py
│   ├── cache.py                  Clases Cache, CacheUrl y excepción CacheError
│   └── madridFines.py            Clase MadridFines y excepción MadridError
├── cuadernos/
│   ├── enunciado_original.ipynb  Enunciado y ETAPA 1 (análisis exploratorio)
│   └── enunciado_actualizado.ipynb
└── datos/
    └── evolucion_multas05.png    Ejemplo del gráfico de multas por hora
```

---

## Requisitos

- Python **3.12** o superior.
- Conexión a internet para descargar los datos del portal (después se reutilizan desde la caché).

Dependencias, que se instalan automáticamente con el paquete: `pandas`, `numpy`, `matplotlib`, `requests` y `beautifulsoup4`.

---

## Instalación

### Opción A: instalar el fichero `.whl` (recomendado)

```bash
pip install dist/traficfines-1.0.0-py3-none-any.whl
```

Para reinstalarlo después de generar una versión nueva del mismo número:

```bash
pip install --force-reinstall dist/traficfines-1.0.0-py3-none-any.whl
```

### Opción B: trabajar sobre el código con `uv`

```bash
uv sync
```

Crea el entorno `.venv` con el paquete en modo editable y las dependencias de desarrollo (`ipykernel`, para abrir los cuadernos).

### Generar el `.whl` de nuevo

```bash
uv build --no-create-gitignore
```

Los ficheros se crean en `dist/`, que forma parte del repositorio. La opción `--no-create-gitignore` evita que `uv` cree un `dist/.gitignore` que haría que git ignorase los paquetes generados.

---

## Uso rápido

```python
from traficFines.madridFines import MadridFines

# "multas" es el nombre de la sub-carpeta de caché; 30 los días que los datos se consideran válidos.
multas = MadridFines("multas", 30)

multas.add(2019, 5)   # mayo de 2019
multas.add(2023, 5)   # mayo de 2023

print(multas.loaded)  # [(5, 2019), (5, 2023)]

print(multas.fines_calificacion())
#  CALIFICACION   GRAVE    LEVE  MUY GRAVE
#  MES ANIO
#  5   2019       61124  111017        747
#      2023      137561   94448       1092

print(multas.total_payments())
#            IMPORTE_MAXIMO  IMPORTE_MINIMO
#  MES ANIO
#  5   2019      17207760.0       8603880.0
#      2023      30764540.0      15382270.0

multas.fines_hour("evolucion_multas.png")   # guarda el gráfico de multas por hora
```
---

## Tests

Las pruebas automáticas están en la carpeta `pruebas/`, fuera del paquete distribuido (`src/traficFines/`):

- `pruebas/conftest.py`: fixtures compartidas (caché redirigida, respuestas HTTP falsas, HTML del portal y CSV de ejemplo).
- `pruebas/test_cache.py`: pruebas de `Cache`, `CacheUrl` y `CacheError`.
- `pruebas/test_madridFines.py`: pruebas de `MadridFines`, `MadridError` y de `__init__.py`.

Para instalar las dependencias de desarrollo (`pytest`, `pytest-cov`) y ejecutar las pruebas con el informe de cobertura:

```bash
uv sync
```

```bash
uv run pytest --cov=traficFines --cov-report=term-missing
```

- **Sin internet**: todas las llamadas a `requests.get` (descarga de CSV y HTML del portal) se simulan. Si alguna prueba intentase acceder a la red, falla.
- **Ficheros generados**: la caché, los gráficos PNG y los ficheros auxiliares de pytest, coverage y matplotlib se escriben solo en `pruebas/data/` (ignorada por git). Nunca se toca `~/.my_cache`.

---

## Nota sobre el uso de IA

Este README se redactó con ayuda de una herramienta de inteligencia artificial (Claude, de Anthropic). El contenido ha sido revisado por el autor.
