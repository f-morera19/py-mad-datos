"""Pruebas de traficFines.cache: Cache, CacheUrl y CacheError."""
from pathlib import Path
import hashlib
import json
import os
import time

import pytest
import requests

import traficFines.cache as cache_mod
from traficFines.cache import Cache, CacheUrl, CacheError, MS_POR_DIA, TIMEOUT_PETICION
from conftest import CACHE_DIR_ORIGINAL

URL = "https://ejemplo.test/datos.csv"


def envejecer(path: Path, dias: float) -> None:
    """Cambia la fecha de modificación de `path` para que parezca creado hace `dias` días."""
    instante = time.time() - dias * 24 * 60 * 60
    os.utime(path, (instante, instante))


# --------------------------------------------------------------------------------------
# Cache: construcción y propiedades
# --------------------------------------------------------------------------------------

def test_constructor_y_propiedades(cache_en_pruebas):
    cache = Cache("app", 7)
    assert cache.app_name == "app"
    assert cache.obsolescence == 7
    # cache_dir es la sub-carpeta de la aplicación dentro de CACHE_DIR.
    assert cache.cache_dir == str(cache_en_pruebas / "app")


def test_cache_dir_por_defecto_es_my_cache():
    # Valor original de CACHE_DIR, guardado en conftest antes de redirigirlo a pruebas/data.
    assert CACHE_DIR_ORIGINAL == Path.home() / ".my_cache"
    assert cache_mod.CACHE_DIR != CACHE_DIR_ORIGINAL


def test_obsolescencia_cero_es_valida():
    assert Cache("app", 0).obsolescence == 0


@pytest.mark.parametrize("app_name", ["", "   ", None, 3])
def test_constructor_app_name_invalido(app_name):
    with pytest.raises(CacheError, match="app_name"):
        Cache(app_name, 1)


@pytest.mark.parametrize("obsolescence", [-1, 1.5, "7", None])
def test_constructor_obsolescence_invalida(obsolescence):
    with pytest.raises(CacheError, match="obsolescence"):
        Cache("app", obsolescence)


def test_cache_dir_es_de_solo_lectura():
    with pytest.raises(AttributeError):
        Cache("app", 1).cache_dir = "/otra/ruta"


def test_cache_dir_se_lee_al_crear_el_objeto(monkeypatch, cache_en_pruebas):
    otra = cache_en_pruebas / "otra"
    monkeypatch.setattr(cache_mod, "CACHE_DIR", str(otra))  # también admite un str
    cache = Cache("app", 1)
    cache.set("x", "1")
    assert cache.cache_dir == str(otra / "app")
    assert (otra / "app" / "x").read_text(encoding="utf-8") == "1"


# --------------------------------------------------------------------------------------
# Cache: set / exists / load / how_old / delete / clear
# --------------------------------------------------------------------------------------

def test_set_load_exists(cache_en_pruebas):
    cache = Cache("app", 1)
    assert not cache.exists("dato")
    cache.set("dato", "ñandú €")
    assert cache.exists("dato")
    assert cache.load("dato") == "ñandú €"
    # Se guarda en la sub-carpeta de la aplicación dentro de pruebas/data.
    assert (cache_en_pruebas / "app" / "dato").is_file()


def test_set_sobrescribe():
    cache = Cache("app", 1)
    cache.set("dato", "viejo")
    cache.set("dato", "nuevo")
    assert cache.load("dato") == "nuevo"


def test_set_error_si_no_se_puede_escribir(cache_en_pruebas):
    cache = Cache("app", 1)
    (cache_en_pruebas / "app" / "carpeta").mkdir(parents=True)
    with pytest.raises(CacheError, match="No fué posible guardar carpeta"):
        cache.set("carpeta", "datos")


def test_load_inexistente():
    with pytest.raises(CacheError, match="No existe ningún dato"):
        Cache("app", 1).load("nada")


def test_load_error_de_lectura(cache_en_pruebas):
    (cache_en_pruebas / "app" / "carpeta").mkdir(parents=True)
    with pytest.raises(CacheError, match="No se pudo leer dato"):
        Cache("app", 1).load("carpeta")


def test_how_old():
    cache = Cache("app", 1)
    cache.set("dato", "x")
    edad = cache.how_old("dato")
    assert 0 <= edad < 5_000  # recién creado: menos de 5 segundos, en milisegundos


def test_how_old_fichero_antiguo(cache_en_pruebas):
    cache = Cache("app", 1)
    cache.set("dato", "x")
    envejecer(cache_en_pruebas / "app" / "dato", 2)
    assert cache.how_old("dato") == pytest.approx(2 * MS_POR_DIA, rel=1e-3)


def test_how_old_inexistente():
    with pytest.raises(CacheError, match="No existe dato"):
        Cache("app", 1).how_old("nada")


def test_how_old_error_de_consulta():
    # Un nombre con carácter nulo hace que el sistema operativo rechace la ruta (ValueError).
    with pytest.raises(CacheError, match="No se pudo consultar edad"):
        Cache("app", 1).how_old("mal\x00nombre")


def test_delete():
    cache = Cache("app", 1)
    cache.set("dato", "x")
    cache.delete("dato")
    assert not cache.exists("dato")


def test_delete_inexistente_no_hace_nada():
    cache = Cache("app", 1)
    cache.delete("nada")
    assert not cache.exists("nada")


def test_delete_error_al_borrar():
    with pytest.raises(CacheError, match="No se pudo borrar"):
        Cache("app", 1).delete("mal\x00nombre")


def test_clear_borra_solo_ficheros_de_la_aplicacion(cache_en_pruebas):
    cache = Cache("app", 1)
    otra = Cache("otra_app", 1)
    cache.set("a", "1")
    cache.set("b", "2")
    otra.set("a", "3")
    (cache_en_pruebas / "app" / "subcarpeta").mkdir()

    cache.clear()

    assert not cache.exists("a") and not cache.exists("b")
    assert (cache_en_pruebas / "app" / "subcarpeta").is_dir()  # las carpetas no se tocan
    assert otra.load("a") == "3"  # otras aplicaciones no se ven afectadas


def test_clear_sin_carpeta_no_falla(cache_en_pruebas):
    Cache("nunca_usada", 1).clear()
    assert not (cache_en_pruebas / "nunca_usada").exists()


def test_clear_error(monkeypatch):
    cache = Cache("app", 1)
    cache.set("a", "1")

    def iterdir_roto(self):
        raise PermissionError("sin permisos")

    monkeypatch.setattr(Path, "iterdir", iterdir_roto)
    with pytest.raises(CacheError, match="No se pudo limpiar la caché"):
        cache.clear()


def test_esta_caducado(cache_en_pruebas):
    cache = Cache("app", 3)
    cache.set("dato", "x")
    assert not cache._esta_caducado("dato")
    envejecer(cache_en_pruebas / "app" / "dato", 3)
    assert cache._esta_caducado("dato")


def test_obsolescencia_cero_siempre_caducado():
    cache = Cache("app", 0)
    cache.set("dato", "x")
    assert cache._esta_caducado("dato")


# --------------------------------------------------------------------------------------
# CacheUrl
# --------------------------------------------------------------------------------------

def test_cacheurl_es_cache():
    assert isinstance(CacheUrl("app", 1), Cache)


def test_hash_es_md5_de_url_y_parametros():
    esperado = hashlib.md5(f"{URL}|{json.dumps({}, sort_keys=True)}".encode()).hexdigest()
    assert CacheUrl._obtener_hash_completo(URL, {}) == esperado


def test_hash_no_depende_del_orden_de_parametros():
    h1 = CacheUrl._obtener_hash_completo(URL, {"a": 1, "b": 2})
    h2 = CacheUrl._obtener_hash_completo(URL, {"b": 2, "a": 1})
    assert h1 == h2
    assert h1 != CacheUrl._obtener_hash_completo(URL, {"a": 1})
    assert h1 != CacheUrl._obtener_hash_completo(URL + "?x", {"a": 1, "b": 2})


def test_get_descarga_y_guarda(fake_web, cache_en_pruebas):
    fake_web.add(URL, "a;b\n1;2\n")
    cache = CacheUrl("app", 1)

    assert cache.get(URL) == "a;b\n1;2\n"
    assert fake_web.calls == [URL]
    nombre = CacheUrl._obtener_hash_completo(URL, {})
    assert (cache_en_pruebas / "app" / nombre).read_text(encoding="utf-8") == "a;b\n1;2\n"


def test_get_usa_timeout(fake_web):
    fake_web.add(URL, "ok")
    assert CacheUrl("app", 1).get(URL) == "ok"
    assert fake_web.last_kwargs == {"timeout": TIMEOUT_PETICION}


def test_get_segunda_vez_usa_la_cache(fake_web):
    fake_web.add(URL, "contenido")
    cache = CacheUrl("app", 1)
    cache.get(URL)
    fake_web.add(URL, "contenido cambiado")

    assert cache.get(URL) == "contenido"
    assert fake_web.calls == [URL]


def test_get_dato_caducado_vuelve_a_descargar(fake_web, cache_en_pruebas):
    fake_web.add(URL, "viejo")
    cache = CacheUrl("app", 2)
    cache.get(URL)
    envejecer(cache_en_pruebas / "app" / CacheUrl._obtener_hash_completo(URL, {}), 2)
    fake_web.add(URL, "nuevo")

    assert cache.get(URL) == "nuevo"
    assert cache.load(URL) == "nuevo"
    assert fake_web.calls == [URL, URL]


def test_get_parametros_distintos_son_entradas_distintas(fake_web):
    fake_web.add(URL, "todo")
    cache = CacheUrl("app", 1)
    cache.get(URL)
    cache.get(URL, CALIFICACION="GRAVE")

    assert len(fake_web.calls) == 2
    assert cache.exists(URL) and cache.exists(URL, CALIFICACION="GRAVE")
    assert not cache.exists(URL, CALIFICACION="LEVE")


@pytest.mark.parametrize("status", [404, 500, 301])
def test_get_status_distinto_de_200(fake_web, status):
    fake_web.add(URL, "error", status_code=status)
    cache = CacheUrl("app", 1)
    with pytest.raises(CacheError, match=f"código de estado {status}"):
        cache.get(URL)
    assert not cache.exists(URL)  # no se guarda nada en la caché


def test_get_excepcion_de_requests_se_propaga(fake_web):
    fake_web.fail(URL, requests.ConnectionError("sin conexión"))
    with pytest.raises(requests.ConnectionError):
        CacheUrl("app", 1).get(URL)


def test_get_contenido_latin1(fake_web):
    fake_web.add(URL, "CALIFICACIÓN;AÑO\n".encode("latin-1"))
    assert CacheUrl("app", 1).get(URL) == "CALIFICACIÓN;AÑO\n"


def test_decodificar():
    assert CacheUrl._decodificar("ñ".encode("utf-8")) == "ñ"
    assert CacheUrl._decodificar("ñ".encode("latin-1")) == "ñ"


def test_get_error_al_guardar(fake_web, cache_en_pruebas):
    # Si la carpeta de la aplicación es en realidad un fichero, no se puede guardar la descarga.
    fake_web.add(URL, "x")
    (cache_en_pruebas / "app").write_text("no soy una carpeta", encoding="utf-8")
    with pytest.raises(CacheError, match="No fué posible guardar"):
        CacheUrl("app", 1).get(URL)


def test_get_entrada_de_cache_ilegible(fake_web, cache_en_pruebas):
    fake_web.add(URL, "x")
    (cache_en_pruebas / "app" / CacheUrl._obtener_hash_completo(URL, {})).mkdir(parents=True)
    with pytest.raises(CacheError, match="No se pudo leer dato"):
        CacheUrl("app", 1).get(URL)
    assert fake_web.calls == []


def test_cacheurl_load_how_old_delete(fake_web):
    fake_web.add(URL, "dato")
    cache = CacheUrl("app", 1)
    cache.get(URL, LUGAR="CL MAYOR")

    assert cache.load(URL, LUGAR="CL MAYOR") == "dato"
    assert 0 <= cache.how_old(URL, LUGAR="CL MAYOR") < 5_000
    with pytest.raises(CacheError):
        cache.load(URL)  # sin parámetros es otra entrada

    cache.delete(URL, LUGAR="CL MAYOR")
    assert not cache.exists(URL, LUGAR="CL MAYOR")
    cache.delete(URL, LUGAR="CL MAYOR")  # borrar algo que ya no existe no es un error
    with pytest.raises(CacheError):
        cache.how_old(URL, LUGAR="CL MAYOR")


def test_cacheurl_clear(fake_web):
    fake_web.add(URL, "dato")
    cache = CacheUrl("app", 1)
    cache.get(URL)
    cache.clear()
    assert not cache.exists(URL)
