"""Fixtures compartidas por las pruebas del paquete traficFines.

Reglas que se aplican a todas las pruebas:
- Ninguna prueba accede a internet: `requests.get` se sustituye siempre por un doble de prueba.
- Todo lo que se escribe en disco (caché y gráficos) va a la carpeta `pruebas/data`.
"""
from pathlib import Path
import os
import shutil

import pytest

DATA_DIR = Path(__file__).parent / "data"

# matplotlib guarda su propia caché de fuentes; también se redirige a pruebas/data y se usa
# un backend sin ventanas. Debe hacerse antes de importar matplotlib (lo importa madridFines).
os.environ["MPLCONFIGDIR"] = str(DATA_DIR / "matplotlib")
os.environ["MPLBACKEND"] = "Agg"

import requests  # noqa: E402

import traficFines.cache as cache_mod  # noqa: E402
import traficFines.madridFines as madrid_mod  # noqa: E402

CACHE_DIR_ORIGINAL = cache_mod.CACHE_DIR
CACHE_DIR_PRUEBAS = DATA_DIR / "cache"
GRAFICOS_DIR = DATA_DIR / "graficos"

URL_PORTAL = "https://datos.madrid.es/dataset/210104-0-multas-circulacion-detalle/downloads"


# --------------------------------------------------------------------------------------
# Respuestas HTTP falsas
# --------------------------------------------------------------------------------------

class FakeResponse:
    """Imita lo que el paquete usa de `requests.Response`: status_code, content y text."""

    def __init__(self, status_code: int = 200, body: str | bytes = ""):
        self.status_code = status_code
        self.content = body if isinstance(body, bytes) else body.encode("utf-8")

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


class FakeWeb:
    """Sustituto de `requests.get` que responde según un diccionario url -> respuesta.

    Cada valor puede ser un `FakeResponse` o una excepción (que se lanza al pedir esa URL).
    Las URLs no registradas devuelven un 404. Se guardan todas las URLs pedidas en `calls`.
    """

    def __init__(self):
        self.routes: dict[str, FakeResponse | Exception] = {}
        self.calls: list[str] = []

    def add(self, url: str, body: str | bytes = "", status_code: int = 200) -> None:
        self.routes[url] = FakeResponse(status_code, body)

    def fail(self, url: str, exc: Exception) -> None:
        self.routes[url] = exc

    def __call__(self, url, *args, **kwargs):
        self.calls.append(url)
        respuesta = self.routes.get(url, FakeResponse(404, "Not Found"))
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


def _red_bloqueada(*args, **kwargs):
    raise AssertionError("Una prueba ha intentado acceder a internet sin simularlo")


@pytest.fixture(autouse=True)
def sin_red(monkeypatch):
    """Por seguridad, cualquier `requests.get` no simulado hace fallar la prueba."""
    monkeypatch.setattr(requests, "get", _red_bloqueada)
    monkeypatch.setattr(cache_mod.requests, "get", _red_bloqueada)
    monkeypatch.setattr(madrid_mod.requests, "get", _red_bloqueada)


@pytest.fixture(autouse=True)
def cache_en_pruebas(monkeypatch):
    """Redirige la caché a `pruebas/data/cache` y la vacía antes de cada prueba."""
    shutil.rmtree(CACHE_DIR_PRUEBAS, ignore_errors=True)
    CACHE_DIR_PRUEBAS.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cache_mod, "CACHE_DIR", CACHE_DIR_PRUEBAS)
    return CACHE_DIR_PRUEBAS


@pytest.fixture
def graficos_dir() -> Path:
    """Carpeta donde se guardan los gráficos generados por las pruebas."""
    GRAFICOS_DIR.mkdir(parents=True, exist_ok=True)
    return GRAFICOS_DIR


@pytest.fixture
def fake_web(monkeypatch) -> FakeWeb:
    """Instala un `FakeWeb` como `requests.get` en ambos módulos del paquete."""
    web = FakeWeb()
    monkeypatch.setattr(cache_mod.requests, "get", web)
    monkeypatch.setattr(madrid_mod.requests, "get", web)
    return web


# --------------------------------------------------------------------------------------
# Datos de ejemplo: HTML del portal y CSV de multas
# --------------------------------------------------------------------------------------

def url_csv(year: int, month: int) -> str:
    return f"https://datos.madrid.es/egob/catalogo/210104-{year}{month:02d}-detalle.csv"


def item_portal(data_key: str | None, titulo: str, href: str | None) -> str:
    """Genera un `div.tracked-resource-item` como los del portal de datos abiertos."""
    atributo = f' data-key="{data_key}"' if data_key is not None else ""
    enlace = f'<a class="resource-type-data" href="{href}">Descargar</a>' if href is not None else ""
    return f'<div class="tracked-resource-item"{atributo}><span>{titulo}</span>{enlace}</div>'


def html_portal(meses: list[tuple[int, int]]) -> str:
    """HTML del portal con el "CSV Detalle" de los (año, mes) indicados y ruido alrededor.

    El ruido cubre las ramas que `get_url` debe ignorar: items sin data-key, con formato de
    fecha incorrecto, con año no numérico, otros tipos de fichero y enlaces que no son .csv.
    """
    items = [
        item_portal(None, "CSV Detalle", "/sin-data-key.csv"),
        item_portal("2024", "CSV Detalle", "/formato-incorrecto.csv"),
        item_portal("abcd-junio", "CSV Detalle", "/anio-no-numerico.csv"),
    ]
    for year, month in meses:
        nombre = madrid_mod.MESES[month].lower()
        items += [
            item_portal(f"{year}-{nombre}", "CSV Agrupadas-excluidas", f"/{year}{month}-agrupadas.csv"),
            item_portal(f"{year}-{nombre}", "TXT Detalle", f"/{year}{month}-detalle.txt"),
            item_portal(f"{year}-{nombre}", "CSV Detalle", f"/{year}{month}-detalle.xlsx"),
            # Enlace relativo con espacios delante: get_url debe limpiarlo y hacerlo absoluto.
            item_portal(f"{year}-{nombre.upper()}", "CSV Detalle",
                        "  " + url_csv(year, month).removeprefix("https://datos.madrid.es")),
        ]
    return f"<html><body><div class='resources'>{''.join(items)}</div></body></html>"


CABECERA_GUION = ("CALIFICACION\x00;  LUGAR  ;MES;ANIO;HORA;IMP_BOL;DESCUENTO;PUNTOS;"
                  "DENUNCIANTE;HECHO-BOL;VEL_LIMITE;VEL_CIRCULA;COORDENADA-X;COORDENADA-Y")
CABECERA_BAJO = ("CALIFICACION;LUGAR;MES;ANIO;HORA;IMP_BOL;DESCUENTO;PUNTOS;"
                 "DENUNCIANTE;HECHO-BOL;VEL_LIMITE;VEL_CIRCULA;COORDENADA_X;COORDENADA_Y")


def csv_multas(year: int, month: int, guion: bool = True) -> str:
    """CSV de multas con el formato del portal (separador ';').

    Incluye espacios sobrantes en valores y nombres de columna, un carácter nulo en una
    cabecera, valores vacíos en columnas numéricas y la HORA en formato HH.MM.
    Contiene 4 multas: 2 GRAVE, 1 LEVE y 1 MUY GRAVE.
    """
    cabecera = CABECERA_GUION if guion else CABECERA_BAJO
    filas = [
        f"GRAVE     ;CL ALCALA 1   ;{month};{year};10.42;200;SI ;4;POLICIA;MULTA A;50;80;440000;4470000",
        f"LEVE      ;CL MAYOR 2    ;{month};{year};10.05;90;NO ;0;SER;MULTA B;;;;",
        f"GRAVE     ;CL ATOCHA 3   ;{month};{year};23.59;300;SI ;2;POLICIA;MULTA C;30;45;   ;abc",
        f"MUY GRAVE ;CL PRADO 4    ;{month};{year};0.00;600;NO ;6;POLICIA;MULTA D;90;160;441000;4471000",
    ]
    return "\n".join([cabecera, *filas]) + "\n"


@pytest.fixture
def portal(fake_web):
    """Portal falso con mayo de 2019 (columnas con '_'), mayo y junio de 2023 (columnas con '-')."""
    meses = [(2019, 5), (2023, 5), (2023, 6)]
    fake_web.add(URL_PORTAL, html_portal(meses))
    fake_web.add(url_csv(2019, 5), csv_multas(2019, 5, guion=False))
    fake_web.add(url_csv(2023, 5), csv_multas(2023, 5))
    fake_web.add(url_csv(2023, 6), csv_multas(2023, 6))
    return fake_web
