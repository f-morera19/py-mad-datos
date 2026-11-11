from traficFines.cache import CacheUrl
from bs4 import BeautifulSoup
import pandas as pd
import requests, re

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
            app_name: Nombre asociado a la aplicación concreta. Se utilizará para
                crear una sub-carpeta dentro de la carpeta CACHE_DIR.
            obsolescence: Cantidad de días por los cuales se consideran válidos
                los datos de la caché.
        """
        # Se inicializa el atributo de cacheUlr
        self.cacheurl = CacheUrl(app_name, obsolescence)

        # Se inicializan atributos restantes como elementos vacíos.
        self._data: pd.DataFrame = pd.DataFrame()

        # Lista de tuples de la forma (mes, año). Si el mes es None, entonces los datos cargados
        # corresponden al año general.
        self._loaded: list[tuple[int|None, int]] = []

    # -- Propiedades --

    @property
    def data(self) -> pd.DataFrame:
        return self._data

    @property
    def loaded(self) -> list[tuple[int|None, int]]:
        return self._loaded

    # -- Métodos estáticos --

    @staticmethod
    def load(year: int, month: int|None, cache: CacheUrl) -> pd.DataFrame:
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
    def get_url(year: int, month: int|None) -> str:
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

    @staticmethod
    def clean(df: pd.DataFrame) -> None:
        """Permite limpiar y normalizar los datos del dataframe `df`.

        Nota: La limpieza y preprocesamiento son los definidos en la sección ETAPA 1 del cuaderno `enunciado_original`.
        (elimina espacios en blanco en columnas de texto, convierte columnas numéricas (VEL_CIRCULA, VEL_LIMITE,
        COORDENADA-X, COORDENADA-Y), crea una columna fecha a partir de ANIO, MES y HORA, etc.). Es posible que
        no todos los meses tengan las mismas columnas. Por ejemplo, en Mayo de 2019, las columnas son COORDENADA_X,
        COORDENADA_Y, en lugar de COORDENADA-X, COORDENADA-Y.

         Args:
            df: Dataframe de Pandas al cual

        Excepciones:
            MadridError si el año y mes no se encuentra en el portal de datos.
        """
        # 1. Se eliminan espacios en blanco en columnas de texto.

        # Se eliminan valores nulos utilizando la expresión regular correspondiente, así como espacios en blanco.
        df = df.rename(columns=lambda c: re.sub(r'[\x00\s]+', ' ', c).strip())

        # 2. Se convierten columnas numéricas
        columnas_a_transformar = [
            "VEL_LIMITE",
            "VEL_CIRCULA",
            "COORDENADA-X",
            "COORDENADA-Y",
            "COORDENADA_X",
            "COORDENADA_Y"
        ]

        for columna in columnas_a_transformar:
            # Se debe utilizar errors="coerce" para transformar strings vacíos a NaN
            # y evitar errores de parsing.
            if columna in df.columns:
                df[columna] = pd.to_numeric(df[columna], errors="coerce")

        # 3. Crea columna nueva fecha, a partir del año, mes y hora.
        # Referencia: https://pandas-pydata-org.translate.goog/docs/reference/api/pandas.Series.str.zfill.html?_x_tr_sl=en&_x_tr_tl=es&_x_tr_hl=es&_x_tr_pto=tc
        fechas_str = (
                df["ANIO"].astype(str) + "-" +
                df["MES"].astype(str).str.zfill(2) + "-01 " +
                df["HORA"].astype(str).str.zfill(2) + ":00:00"
        )

        # Se convierte esa serie de textos a datetime de una sola vez.
        df["fecha"] = pd.to_datetime(fechas_str)

    # -- Métodos públicos --

    def clean_cache(self, ) -> None:
        """Elimina todos los elementos de la caché."""
        self.cacheurl.clear()

    def add(self, year: int, month: int|None = None) -> None:
        """Añade información de multas de un mes y un año concretos al dataset `data` actual.

        Args:
            year: Año por el cual filtrar multas.
            month: Mes por el cual filtrar multas.
        """
        # Se evalúa que el mes sea válido.
        if month is not None and not 1 <= month <= 12:
            raise ValueError(f"Mes no válido: {month!r}")

        # Se obtiene el url correspondiente al mes y año deseados.
        url = self.get_url(year, month)

        # Se evalúa que la consulta al mes no exista aún.
        if month is None:
            # Solo se envió parámetro año.
            if self.cacheurl.exists(url, ANIO = year):
                return
        else:
            # Se enviaron ambos parámetros.
            if self.cacheurl.exists(url, ANIO = year, MES = month):
                return

        # Se descargan los datos correspondientes al año y mes deseados y se guardan en caché.
        resultado = self.load(year, month, self.cacheurl)
        self.clean(resultado)

        # Se añade al dataframe data actual.
        self.data.add(resultado) # revisar esto

        # Se actualiza el atributo loaded con el mes y año cargados.
        nueva_registro_cargado = (month, year)
        self.loaded.append(nueva_registro_cargado)

    def fines_hour(self, fig_name: str) -> None:
        """Genera un gráfico de líneas que muestra la evolución del número de multas a lo largo de las horas del día.
        Si hay varios meses cargados, dibuja una línea por cada mes. Se guarda el gráfico con nombre fig_name

        Args:
            fig_name: Nombre del gráfico a generar.
        """

    def fines_calificacion(self) -> pd.DataFrame:
        """analiza la distribución de multas por calificación, mes y año. Devuelve un DataFrame con el número
         total de multas distinguiendo por tipo para cada uno de los meses.
        """

    def total_payments(self) -> pd.DataFrame:
        """Genera un resumen con el importe total (máximo y mínimo) recaudado por mes y año. Una multa puede tener
        descuento pronto pago del 50%, pero cabe la posibilidad de que el infractor no realice el pago en fecha para
        acogerse a dicho descuento."""