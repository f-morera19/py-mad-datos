"""Pruebas de traficFines.madridFines: MadridFines y MadridError."""
from io import StringIO

import pandas as pd
import pytest
import requests

import traficFines
import traficFines.madridFines as madrid_mod
from traficFines.cache import CacheUrl, CacheError, TIMEOUT_PETICION
from traficFines.madridFines import MadridFines, MadridError, get_url

from conftest import URL_PORTAL, item_portal, url_csv, csv_multas


@pytest.fixture
def multas() -> MadridFines:
    return MadridFines("multas", 30)


@pytest.fixture
def multas_2023(multas, portal) -> MadridFines:
    """Multas con mayo y junio de 2023 cargados."""
    multas.add(2023, 5)
    multas.add(2023, 6)
    return multas


# --------------------------------------------------------------------------------------
# __init__.py
# --------------------------------------------------------------------------------------

def test_main(capsys):
    traficFines.main()
    assert capsys.readouterr().out == "Hello from traficFines!\n"


# --------------------------------------------------------------------------------------
# Construcción y propiedades
# --------------------------------------------------------------------------------------

def test_constructor(multas, cache_en_pruebas):
    assert isinstance(multas.cacheurl, CacheUrl)
    assert multas.cacheurl.app_name == "multas"
    assert multas.cacheurl.obsolescence == 30
    assert multas.cacheurl.cache_dir == str(cache_en_pruebas / "multas")
    assert multas.data.empty
    assert multas.loaded == []


def test_constructor_parametros_invalidos():
    with pytest.raises(CacheError):
        MadridFines("", 30)
    with pytest.raises(CacheError):
        MadridFines("multas", -1)


def test_loaded_devuelve_una_copia(multas, portal):
    multas.add(2023, 5)
    copia = multas.loaded
    copia.append((1, 1999))
    assert multas.loaded == [(5, 2023)]


# --------------------------------------------------------------------------------------
# get_url
# --------------------------------------------------------------------------------------

def test_get_url_encuentra_csv_detalle(portal):
    assert MadridFines.get_url(2023, 5) == url_csv(2023, 5)
    assert MadridFines.get_url(2023, 6) == url_csv(2023, 6)
    assert MadridFines.get_url(2019, 5) == url_csv(2019, 5)
    assert portal.calls == [URL_PORTAL] * 3


def test_get_url_usa_timeout(portal_mayo):
    MadridFines.get_url(2023, 5)
    assert portal_mayo.calls == [URL_PORTAL]
    assert portal_mayo.last_kwargs == {"timeout": TIMEOUT_PETICION}


def test_get_url_funcion_del_modulo(portal):
    assert get_url(2023, 5) == MadridFines.get_url(2023, 5) == url_csv(2023, 5)


def test_get_url_enlace_absoluto_se_mantiene(fake_web):
    absoluto = "https://otro.servidor.test/multas/2024_01.csv"
    fake_web.add(URL_PORTAL, item_portal("2024-enero", "CSV Detalle", absoluto))
    assert MadridFines.get_url(2024, 1) == absoluto


@pytest.mark.parametrize("year, month", [(2023, 7), (2022, 5), (2023, None), (2023, 13)])
def test_get_url_mes_no_publicado(portal, year, month):
    with pytest.raises(MadridError, match="No se encontró el recurso"):
        MadridFines.get_url(year, month)


def test_get_url_sin_enlace_csv_detalle(fake_web):
    html = "".join([
        item_portal("2024-enero", "CSV Detalle", None),               # sin enlace
        item_portal("2024-enero", "CSV Detalle", "/enero.xlsx"),      # enlace que no es .csv
        item_portal("2024-enero", "TXT Detalle", "/enero.csv"),       # otro tipo de recurso
        item_portal("2024-enero", "CSV Agrupadas-excluidas", "/agrupadas.csv"),
    ])
    fake_web.add(URL_PORTAL, html)
    with pytest.raises(MadridError, match="No se encontró el recurso para Enero de 2024"):
        MadridFines.get_url(2024, 1)


@pytest.mark.parametrize("status", [403, 404, 500])
def test_get_url_status_distinto_de_200(fake_web, status):
    fake_web.add(URL_PORTAL, "error", status_code=status)
    with pytest.raises(MadridError, match=f"Error {status}"):
        MadridFines.get_url(2024, 1)


@pytest.mark.parametrize("exc", [requests.ConnectionError("sin red"), requests.Timeout("lento")])
def test_get_url_excepcion_de_requests(fake_web, exc):
    fake_web.fail(URL_PORTAL, exc)
    with pytest.raises(MadridError, match="No se logró acceder") as info:
        MadridFines.get_url(2024, 1)
    assert info.value.__cause__ is exc


# --------------------------------------------------------------------------------------
# load
# --------------------------------------------------------------------------------------

def test_load_mes(portal, multas):
    df = MadridFines.load(2023, 5, multas.cacheurl)
    assert len(df) == 4
    assert "COORDENADA-X" in df.columns
    # load no limpia: los nombres de columna conservan los caracteres originales.
    assert "CALIFICACION\x00" in df.columns
    assert multas.cacheurl.exists(url_csv(2023, 5))


def test_load_usa_la_cache(portal, multas):
    MadridFines.load(2023, 5, multas.cacheurl)
    MadridFines.load(2023, 5, multas.cacheurl)
    # El portal se consulta siempre, pero el CSV solo se descarga una vez.
    assert portal.calls.count(url_csv(2023, 5)) == 1
    assert portal.calls.count(URL_PORTAL) == 2


def test_load_anio_completo(portal, multas):
    df = MadridFines.load(2023, None, multas.cacheurl)
    assert len(df) == 8
    assert sorted(df["MES"].unique()) == [5, 6]
    assert list(df.index) == list(range(8))  # ignore_index=True


def test_load_anio_sin_ningun_mes(portal, multas):
    with pytest.raises(MadridError, match="No hay datos de ningún mes de 2015"):
        MadridFines.load(2015, None, multas.cacheurl)


def test_load_csv_con_error_http(portal_mayo, multas):
    portal_mayo.add(url_csv(2023, 5), "error", status_code=500)
    with pytest.raises(MadridError, match="No se pudieron descargar") as info:
        MadridFines.load(2023, 5, multas.cacheurl)
    assert isinstance(info.value.__cause__, CacheError)


def test_load_csv_con_excepcion_de_requests(portal_mayo, multas):
    portal_mayo.fail(url_csv(2023, 5), requests.ConnectionError("cortado"))
    with pytest.raises(MadridError, match="No se pudieron descargar") as info:
        MadridFines.load(2023, 5, multas.cacheurl)
    assert isinstance(info.value.__cause__, requests.RequestException)


@pytest.mark.parametrize("contenido", ["", 'A;B\n"sin cerrar;1\n'])
def test_load_csv_ilegible(portal_mayo, multas, contenido):
    portal_mayo.add(url_csv(2023, 5), contenido)
    with pytest.raises(MadridError, match="No se pudo leer el CSV"):
        MadridFines.load(2023, 5, multas.cacheurl)


# --------------------------------------------------------------------------------------
# clean
# --------------------------------------------------------------------------------------

def df_crudo(year=2023, month=5, guion=True) -> pd.DataFrame:
    return pd.read_csv(StringIO(csv_multas(year, month, guion)), sep=";")


def test_clean_normaliza_nombres_de_columna():
    df = df_crudo()
    MadridFines.clean(df)
    assert "CALIFICACION" in df.columns
    assert "LUGAR" in df.columns
    assert all("\x00" not in c and c == c.strip() for c in df.columns)


def test_clean_nombres_con_nulos_y_espacios_internos():
    df = pd.DataFrame({"  A\x00\x00B  ": [1], "C\t D": [2], "ANIO": [2023], "MES": [1], "HORA": [1.0]})
    MadridFines.clean(df)
    assert list(df.columns) == ["A B", "C D", "ANIO", "MES", "HORA"]


def test_clean_quita_espacios_en_valores():
    df = df_crudo()
    MadridFines.clean(df)
    assert list(df["CALIFICACION"]) == ["GRAVE", "LEVE", "GRAVE", "MUY GRAVE"]
    assert df["LUGAR"].iloc[0] == "CL ALCALA 1"
    assert set(df["DESCUENTO"]) == {"SI", "NO"}


@pytest.mark.parametrize("guion, x, y", [(True, "COORDENADA-X", "COORDENADA-Y"),
                                         (False, "COORDENADA_X", "COORDENADA_Y")])
def test_clean_columnas_numericas(guion, x, y):
    df = df_crudo(guion=guion)
    MadridFines.clean(df)
    for columna in ["VEL_LIMITE", "VEL_CIRCULA", x, y]:
        assert pd.api.types.is_numeric_dtype(df[columna]), columna
    assert df["VEL_LIMITE"].iloc[0] == 50
    assert pd.isna(df["VEL_LIMITE"].iloc[1])  # vacío -> NaN
    assert df[x].iloc[0] == 440000
    assert pd.isna(df[x].iloc[2])  # espacios -> NaN
    assert pd.isna(df[y].iloc[2])  # texto no numérico -> NaN


def test_clean_crea_indice_fecha_con_hora_hhmm():
    df = df_crudo()
    MadridFines.clean(df)
    assert df.index.name == "fecha"
    assert list(df.index) == [
        pd.Timestamp("2023-05-01 10:42"),
        pd.Timestamp("2023-05-01 10:05"),
        pd.Timestamp("2023-05-01 23:59"),
        pd.Timestamp("2023-05-01 00:00"),
    ]
    assert "fecha" not in df.columns


def test_clean_hora_invalida_da_fecha_nula():
    df = pd.DataFrame({"ANIO": [2023, 2023], "MES": [5, 5], "HORA": ["10.30", "xx"]})
    MadridFines.clean(df)
    assert df.index[0] == pd.Timestamp("2023-05-01 10:30")
    assert pd.isna(df.index[1])


def test_clean_es_in_situ():
    df = df_crudo()
    assert MadridFines.clean(df) is None
    assert df.index.name == "fecha"


def test_clean_sin_columnas_obligatorias():
    with pytest.raises(KeyError):
        MadridFines.clean(pd.DataFrame({"ANIO": [2023], "MES": [5]}))


# --------------------------------------------------------------------------------------
# add y clean_cache
# --------------------------------------------------------------------------------------

def test_add_mes(multas, portal):
    multas.add(2023, 5)
    assert multas.loaded == [(5, 2023)]
    assert len(multas.data) == 4
    assert multas.data.index.name == "fecha"
    assert "CALIFICACION" in multas.data.columns


def test_add_varios_meses_concatena(multas, portal):
    multas.add(2019, 5)
    multas.add(2023, 5)
    assert multas.loaded == [(5, 2019), (5, 2023)]
    assert len(multas.data) == 8
    # Las dos variantes de coordenadas conviven en el dataset.
    assert {"COORDENADA_X", "COORDENADA-X"} <= set(multas.data.columns)


def test_add_mismo_mes_no_duplica(multas, portal):
    multas.add(2023, 5)
    multas.add(2023, 5)
    assert multas.loaded == [(5, 2023)]
    assert len(multas.data) == 4
    assert portal.calls.count(URL_PORTAL) == 1


def test_add_anio_completo(multas, portal):
    multas.add(2023)
    assert multas.loaded == [(None, 2023)]
    assert len(multas.data) == 8


def test_add_mes_de_anio_ya_cargado_no_hace_nada(multas, portal):
    multas.add(2023)
    llamadas = len(portal.calls)
    multas.add(2023, 6)
    multas.add(2023)
    assert multas.loaded == [(None, 2023)]
    assert len(multas.data) == 8
    assert len(portal.calls) == llamadas


def test_add_anio_tras_meses_sueltos_no_duplica(multas, portal):
    multas.add(2019, 5)
    multas.add(2023, 5)
    multas.add(2023)
    assert multas.loaded == [(5, 2019), (None, 2023)]
    assert len(multas.data) == 12  # 4 de 2019 + 8 de 2023, sin repetir mayo de 2023
    assert (multas.data["MES"] == 5).sum() == 8
    assert ((multas.data["MES"] == 5) & (multas.data["ANIO"] == 2023)).sum() == 4


def test_add_anio_sin_meses_previos_de_ese_anio(multas, portal):
    multas.add(2019, 5)
    multas.add(2023)
    assert multas.loaded == [(5, 2019), (None, 2023)]
    assert len(multas.data) == 12


@pytest.mark.parametrize("month", [0, 13, -1])
def test_add_mes_invalido(multas, month):
    with pytest.raises(ValueError, match="Mes no válido"):
        multas.add(2023, month)
    assert multas.loaded == []


def test_add_mes_no_publicado(multas, portal):
    with pytest.raises(MadridError):
        multas.add(2023, 9)
    assert multas.loaded == []
    assert multas.data.empty


def test_clean_cache(multas, portal):
    multas.add(2023, 5)
    assert multas.cacheurl.exists(url_csv(2023, 5))
    multas.clean_cache()
    assert not multas.cacheurl.exists(url_csv(2023, 5))


def test_datos_se_reutilizan_entre_instancias(portal):
    MadridFines("multas", 30).add(2023, 5)
    MadridFines("multas", 30).add(2023, 5)
    assert portal.calls.count(url_csv(2023, 5)) == 1


# --------------------------------------------------------------------------------------
# Análisis: fines_hour, fines_calificacion, total_payments
# --------------------------------------------------------------------------------------

def test_fines_hour_genera_png(multas_2023, graficos_dir):
    destino = graficos_dir / "evolucion_multas.png"
    destino.unlink(missing_ok=True)

    multas_2023.fines_hour(str(destino))

    assert destino.is_file()
    assert destino.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_fines_hour_una_linea_por_mes(multas, portal, graficos_dir, monkeypatch):
    multas.add(2019, 5)
    multas.add(2023, 5)
    multas.add(2023, 6)
    lineas = {}

    def savefig(self, fname, *args, **kwargs):
        for linea in self.axes[0].get_lines():
            lineas[linea.get_label()] = list(linea.get_ydata())

    monkeypatch.setattr(madrid_mod.plt.Figure, "savefig", savefig)
    multas.fines_hour(str(graficos_dir / "no_se_escribe.png"))

    assert set(lineas) == {"2019-5", "2023-5", "2023-6"}
    esperado = [0] * 24
    esperado[0], esperado[10], esperado[23] = 1, 2, 1
    assert lineas["2023-5"] == esperado


def test_fines_hour_ignora_horas_nulas(multas, portal, graficos_dir):
    multas.add(2023, 5)
    multas.data.loc[multas.data.index[0], "HORA"] = float("nan")
    destino = graficos_dir / "con_nulos.png"
    multas.fines_hour(str(destino))
    assert destino.is_file()


def test_fines_hour_cierra_la_figura_aunque_falle(multas, portal, graficos_dir):
    multas.add(2023, 5)
    antes = len(madrid_mod.plt.get_fignums())
    multas.fines_hour(str(graficos_dir / "cierre.png"))
    with pytest.raises(MadridError, match="No se pudo guardar el gráfico"):
        multas.fines_hour(str(graficos_dir / "no_existe" / "x.png"))
    assert len(madrid_mod.plt.get_fignums()) == antes


def test_fines_calificacion(multas, portal):
    multas.add(2019, 5)
    multas.add(2023, 5)
    resultado = multas.fines_calificacion()

    assert list(resultado.index.names) == ["MES", "ANIO"]
    assert list(resultado.columns) == ["GRAVE", "LEVE", "MUY GRAVE"]
    assert resultado.loc[(5, 2023)].to_dict() == {"GRAVE": 2, "LEVE": 1, "MUY GRAVE": 1}
    assert resultado.loc[(5, 2019)].to_dict() == {"GRAVE": 2, "LEVE": 1, "MUY GRAVE": 1}


def test_fines_calificacion_rellena_con_cero(multas_2023):
    datos = multas_2023.data
    multas_2023._data = datos[~((datos["MES"] == 6) & (datos["CALIFICACION"] == "LEVE"))]
    assert multas_2023.fines_calificacion().loc[(6, 2023), "LEVE"] == 0


def test_total_payments(multas_2023):
    resultado = multas_2023.total_payments()

    assert list(resultado.index.names) == ["MES", "ANIO"]
    assert list(resultado.columns) == ["IMPORTE_MAXIMO", "IMPORTE_MINIMO"]
    # 200 (SI) + 90 (NO) + 300 (SI) + 600 (NO): máximo 1190; mínimo 100 + 90 + 150 + 600 = 940.
    for mes in (5, 6):
        assert resultado.loc[(mes, 2023), "IMPORTE_MAXIMO"] == pytest.approx(1190)
        assert resultado.loc[(mes, 2023), "IMPORTE_MINIMO"] == pytest.approx(940)


def test_total_payments_importes_no_numericos_cuentan_cero(multas, portal):
    multas.add(2023, 5)
    multas.data["IMP_BOL"] = multas.data["IMP_BOL"].astype(object)
    multas.data.iloc[0, multas.data.columns.get_loc("IMP_BOL")] = "n/d"
    resultado = multas.total_payments()
    assert resultado.loc[(5, 2023), "IMPORTE_MAXIMO"] == pytest.approx(990)
    assert resultado.loc[(5, 2023), "IMPORTE_MINIMO"] == pytest.approx(840)


def argumentos(metodo, graficos_dir) -> list[str]:
    """fines_hour necesita una ruta de destino; el resto de análisis no recibe argumentos."""
    return [str(graficos_dir / "no_se_escribe.png")] if metodo == "fines_hour" else []


@pytest.mark.parametrize("metodo", ["fines_hour", "fines_calificacion", "total_payments"])
def test_analisis_sin_datos(multas, graficos_dir, metodo):
    with pytest.raises(MadridError, match="No hay datos cargados"):
        getattr(multas, metodo)(*argumentos(metodo, graficos_dir))


@pytest.mark.parametrize("metodo, falta", [
    ("fines_calificacion", "CALIFICACION"),
    ("total_payments", "IMP_BOL"),
    ("fines_hour", "HORA"),
])
def test_analisis_faltan_columnas(multas, portal, graficos_dir, metodo, falta):
    multas.add(2023, 5)
    multas._data = multas.data.drop(columns=[falta])
    with pytest.raises(MadridError, match=f"Faltan columnas en los datos: {falta}"):
        getattr(multas, metodo)(*argumentos(metodo, graficos_dir))


def test_nombres_del_enunciado(multas_2023):
    pd.testing.assert_frame_equal(multas_2023.fines_calification(), multas_2023.fines_calificacion())
    pd.testing.assert_frame_equal(multas_2023.total_payment(), multas_2023.total_payments())
