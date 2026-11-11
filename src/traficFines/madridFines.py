from idlelib import statusbar

from traficFines.cache import CacheUrl
from bs4 import BeautifulSoup
import pandas as pd
import  requests

RAIZ = "https://datos.madrid.es/"

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

class MadridError(Exception):
    """Cualquier error producido en el módulo caché."""

class MadridFines:
    """
    Esta clase tiene como objetivo gestionar, limpiar, almacenar y analizar datos de multas de tráfico del
    Ayuntamiento de Madrid descargados desde el portal de datos abiertos. Es una clase pensada para automatizar el
    ciclo completo de análisis de multas: desde la descarga y preprocesamiento de multas de varios meses, hasta la
    generación de resúmenes y gráficos explicativos.
    """

    def __init__(self, app_name: str, obsolescence: int) -> None:
        """Inicializa el objeto con la MadridFines.

            Args:
                cacheurl: Instancia de CacheURL que se usará para descargar y
                    almacenar en caché los datos de cada petición.
                data: DataFrame de pandas para almacenar los datos. Puede contener multas
                    de distintos meses.
                loaded: Lista de periodos en meses de datos contenidos en `data`, cada uno como una
                    tupla `(month, year)`, donde `month` es el mes (1-12) y `year`
                    el año. Sirve para evitar volver a descargar un periodo.
        """
        # Se inicializa el atributo de cacheUlr
        self.cacheurl = CacheUrl(app_name, obsolescence)
        # Se inicializan atributos restantes como elementos vacíos.
        self._data: pd.DataFrame = pd.DataFrame()
        self._loaded: list[tuple[int, int]] = []

    # -- Propiedades --

    @property
    def data(self) -> pd.DataFrame:
        return self._data

    @property
    def loaded(self) -> list[tuple[int, int]]:
        return self._loaded

    # -- Métodos públicos --

    @staticmethod
    def load(year: int, month: int, cache: CacheUrl) -> pd.DataFrame:
        """Utiliza el objeto de cacheUrl para acceder a los datos de multas
        del año `year` y mes `month`, a partir de los cuales se crea un dataframe
        de Pandas.

        Args:
            year:
            month: Int
            cache: String

        Excepciones:
            MadridError si el año y mes no se encuentra en el portal de datos.
        """
        datos = cache.get


    @staticmethod
    def get_url(year: int, month: int) -> str:
        """Función que recibe como argumentos un mes (1–12) y un año (con 4 cifras, ej. 2024) y devuelva la URL
        del fichero CSV con los datos de multas correspondiente a ese mes y año, disponible en el portal de datos
        abiertos del Ayuntamiento de Madrid.

        Args:
            year: Año (4 cifras, ej. 2024) para filtrar multas.
            month: Mes (1-12) para filtrar multas.

        Excepciones:
            MadridError si el año y mes no se encuentra en el portal de datos.
        """

        # Primer paso: Cargar página web en memoria.
        url_base = f"{RAIZ}/dataset/210104-0-multas-circulacion-detalle/downloads"

        # Se realiza petición a la web.
        req = requests.get(url_base)

        # Se comprueba que la petición nos devuelva un Status Code = 200
        status_code = req.status_code

        if status_code == 200:
            # Se pasa el contenido HTML a un objeto más fácil de manejar.
            soup = BeautifulSoup(req.text, "html.parser")

            # Obtenemos el nombre del mes esperado a partir de tu diccionario (ej: 6 -> "Junio")
            nombre_mes_buscado = MESES.get(month, "")

            # Se buscan elementos con selectores que correspondan a enlaces con mes/año buscados.
            # Nota: Cada fichero es un div.tracked-resource-item con un atributo data-key="Año-Mes"
            # (por ejemplo 2024-diciembre), y dentro está el enlace de descarga (a.resource-type-data, terminado en .csv).
            for item in soup.select("div.tracked-resource-item"):
                data_key = item.get("data-key")

                # Si el data_key no es un string se ignora.
                if not isinstance(data_key, str):
                    continue

                # Si la fecha no sigue el formato esperado, se ignora.
                partes_fecha = data_key.split("-")
                if len(partes_fecha) != 2:
                    continue

                anio_str, mes_str = partes_fecha

                # Validar que año se pueda parsear como un int.
                try:
                    anio_val = int(anio_str)
                except ValueError:
                    continue

                # Validar si el año y el mes en texto coinciden (ignorando mayúsculas/minúsculas por seguridad).
                if anio_val != year or mes_str.strip().lower() != nombre_mes_buscado.lower():
                    continue

                # Obtener el enlace al archivo .csv debajo del elemento con el año y mes deseados.
                enlace = item.select_one('a.resource-type-data[href$=".csv"]')
                if enlace is None:
                    continue

                href = enlace.get('href')

                # Hay que asegurarse de que href exista y sea un string.
                if not isinstance(href, str) or not href.strip():
                    continue

                return href
            raise MadridError(f"No se encontró el recurso para {nombre_mes_buscado} de {year} en {url_base}.")
        else:
            print(f"Error {status_code}")
            raise MadridError(f"No se logró obtener recursos de {url_base}. Error {status_code}")