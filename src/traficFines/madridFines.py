from traficFines.cache import CacheUrl, CacheError, TIMEOUT_PETICION
from typing import cast
from io import StringIO
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib.pyplot as plt
import requests, re

RAIZ = "https://datos.madrid.es/"
DESCUENTO_PRONTO_PAGO = 0.5  # 50% de descuento por pronto pago.

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

class MadridError(Exception):
    """Cualquier error producido en el módulo caché."""


def get_url(year: int, month: int|None) -> str:
    """Devuelve la URL del fichero CSV de multas correspondiente a un mes y año concretos.

    Función del módulo pedida en el enunciado. Delega en `MadridFines.get_url`.

    Args:
        year: Año (4 cifras, ej. 2024) para filtrar multas.
        month: Mes (1-12) para filtrar multas.

    Excepciones:
        MadridError: Si no se puede acceder al portal o si el año y mes no se encuentran en él.
    """
    return MadridFines.get_url(year, month)


class MadridFines:
    """
    Esta clase tiene como objetivo gestionar, limpiar, almacenar y analizar datos de multas de tráfico del
    Ayuntamiento de Madrid descargados desde el portal de datos abiertos. Es una clase pensada para automatizar el
    ciclo completo de análisis de multas: desde la descarga y preprocesamiento de multas de varios meses, hasta la
    generación de resúmenes y gráficos explicativos.
    """

    def __init__(self, app_name: str, obsolescence: int) -> None:
        """Inicializa el objeto MadridFines con su caché y un dataset vacío.

        Args:
            app_name: Nombre asociado a la aplicación concreta. Se utilizará para
                crear una sub-carpeta dentro de la carpeta CACHE_DIR.
            obsolescence: Cantidad de días por los cuales se consideran válidos
                los datos de la caché.

        Excepciones:
            CacheError: Si app_name u obsolescence no son válidos.
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
        # Se devuelve una copia para que la lista interna no se pueda modificar desde fuera de la clase.
        return list(self._loaded)

    # -- Métodos estáticos --

    @staticmethod
    def load(year: int, month: int|None, cacheurl: CacheUrl) -> pd.DataFrame:
        """Crea un DataFrame de Pandas con los datos de multas del año `year` y mes `month`.

        Utiliza el objeto `cacheurl` para acceder a los datos.

        Args:
            year: Año (4 cifras, ej. 2024) de las multas.
            month: Mes (1-12) de las multas, o None para el año completo.
            cacheurl: Objeto CacheUrl utilizado para descargar y almacenar los datos.

        Excepciones:
            MadridError: Si el año y mes no se encuentran en el portal de datos, si no se
                pueden descargar o si el CSV no se puede leer.
        """
        # Año completo: se concatenan todos los meses disponibles en el portal.
        if month is None:
            meses = []
            for mes in MESES:
                try:
                    # Se llama de forma recursiva para un mes específico.
                    # Esto debería retornar un Dataframe de Pandas que se agrega a la lista total.
                    meses.append(MadridFines.load(year, mes, cacheurl))
                except MadridError:
                    # Ese mes no está publicado (por ejemplo, meses futuros del año en curso).
                    continue
            if not meses:
                raise MadridError(f"No hay datos de ningún mes de {year} en el portal.")
            return pd.concat(meses, ignore_index=True)

        url = MadridFines.get_url(year, month)
        try:
            # Se obtiene el dato de la url definida
            texto = cacheurl.get(url)
        except (CacheError, requests.RequestException) as e:
            raise MadridError(f"No se pudieron descargar los datos de {url}: {e}") from e

        try:
            # StringIO trata el texto descargado como un fichero; los CSV del portal usan ';' como separador.
            return pd.read_csv(StringIO(texto), sep=";")
        except Exception as e:
            raise MadridError(f"No se pudo leer el CSV de {url}: {e}") from e

    @staticmethod
    def get_url(year: int, month: int|None) -> str:
        """Devuelve la URL del fichero CSV de multas correspondiente a un mes y año concretos.

        El fichero se busca en el portal de datos abiertos del Ayuntamiento de Madrid.

        Args:
            year: Año (4 cifras, ej. 2024) para filtrar multas.
            month: Mes (1-12) para filtrar multas.

        Excepciones:
            MadridError: Si no se puede acceder al portal o si el año y mes no se encuentran en él.
        """

        # Primer paso: Cargar página web en memoria.
        url_base = urljoin(RAIZ, "dataset/210104-0-multas-circulacion-detalle/downloads")

        # Se realiza petición a la web.
        try:
            req = requests.get(url_base, timeout=TIMEOUT_PETICION)
        except requests.RequestException as e:
            raise MadridError(f"No se logró acceder a {url_base}: {e}") from e

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

                # Cada mes publica varios ficheros ("CSV Detalle", "CSV Agrupadas-excluidas", "TXT Detalle"...).
                # Solo interesa el CSV con el detalle de las multas; los demás son resúmenes o duplicados.
                # Nota aclaratoria: Esta condición se generó con ayuda de una herramienta de inteligencia artificial
                # (Claude, de Anthropic). El contenido ha sido revisado por el autor.
                if not item.get_text(" ", strip=True).upper().startswith("CSV DETALLE"):
                    continue

                # Obtener el enlace al archivo .csv debajo del elemento con el año y mes deseados.
                enlace = item.select_one('a.resource-type-data[href$=".csv"]')
                if enlace is None:
                    continue

                href = enlace.get('href')

                # Hay que asegurarse de que href exista y sea un string.
                if not isinstance(href, str) or not href.strip():
                    continue

                # El enlace puede ser relativo al portal, así que se convierte en absoluto.
                return urljoin(RAIZ, href.strip())
            raise MadridError(f"No se encontró el recurso para {nombre_mes_buscado} de {year} en {url_base}.")
        else:
            raise MadridError(f"No se logró obtener recursos de {url_base}. Error {status_code}")

    @staticmethod
    def clean(df: pd.DataFrame) -> None:
        """Limpia y normaliza los datos del DataFrame `df`.

        Nota: La limpieza y preprocesamiento son los definidos en la sección ETAPA 1 del cuaderno
        `enunciado_original` (elimina espacios en blanco en columnas de texto, convierte columnas
        numéricas (VEL_CIRCULA, VEL_LIMITE, COORDENADA-X, COORDENADA-Y), crea una columna fecha a
        partir de ANIO, MES y HORA, etc.). Es posible que no todos los meses tengan las mismas columnas.
        Por ejemplo, en Mayo de 2019, las columnas son COORDENADA_X, COORDENADA_Y, en lugar de
        COORDENADA-X, COORDENADA-Y.

        Args:
            df: DataFrame de Pandas a limpiar.

        Excepciones:
            KeyError: Si faltan las columnas ANIO, MES u HORA.
        """
        # 1. Se normalizan los nombres de columna: se eliminan caracteres nulos (\x00) y espacios sobrantes.
        # La expresión [\x00\s]+ encaja con cualquier secuencia de uno o más caracteres que sean nulos o espacios
        # en blanco

        # Nota aclaratoria: Esta condición se generó con ayuda de una herramienta de inteligencia artificial
        # (Claude, de Anthropic). El contenido ha sido revisado por el autor.
        df.rename(columns=lambda c: re.sub(r'[\x00\s]+', ' ', str(c)).strip(), inplace=True)

        # 2. Se eliminan espacios en blanco en los valores de las columnas de texto.
        for columna in df.columns:
            if pd.api.types.is_string_dtype(df[columna]):
                df[columna] = df[columna].str.strip()

        # 3. Se convierten columnas numéricas. Según el mes, las coordenadas usan '-' o '_'.
        columnas_a_transformar = [
            "VEL_LIMITE",
            "VEL_CIRCULA",
            "COORDENADA-X",
            "COORDENADA-Y",
            "COORDENADA_X",
            "COORDENADA_Y",
        ]

        for columna in columnas_a_transformar:
            # Se debe utilizar errors="coerce" para transformar strings vacíos a NaN
            # y evitar errores de parsing.
            if columna in df.columns:
                df[columna] = pd.to_numeric(df[columna], errors="coerce")

        # 4. Se crea la columna fecha a partir del año, mes y hora (día 1), y se usa como índice.
        # La hora viene en formato HH.MM (ej. 10.42 son las 10:42): en los datos reales la parte decimal
        # nunca supera 59, así que son minutos y no una fracción de hora.
        hora = pd.to_numeric(df["HORA"], errors="coerce")
        horas = hora.floordiv(1)
        minutos = ((hora - horas) * 100).round()
        df["fecha"] = pd.to_datetime(
            pd.DataFrame({
                "year": df["ANIO"],
                "month": df["MES"],
                "day": 1,
                "hour": horas,
                "minute": minutos,
            }),
            errors="coerce"
        )
        df.set_index("fecha", inplace=True)

    # -- Métodos públicos --

    def clean_cache(self, ) -> None:
        """Elimina todos los elementos de la caché.

        Args:
            Ninguno.

        Excepciones:
            CacheError: Si no se logra limpiar la caché.
        """
        self.cacheurl.clear()

    def add(self, year: int, month: int|None = None) -> None:
        """Añade información de multas de un mes y un año concretos al dataset `data` actual.

        Args:
            year: Año por el cual filtrar multas.
            month: Mes (1-12) por el cual filtrar multas, o None para el año completo.

        Excepciones:
            ValueError: Si el mes no está entre 1 y 12.
            MadridError: Si el año y mes no se encuentran en el portal de datos.
        """
        # Se evalúa que el mes sea válido.
        if month is not None and not 1 <= month <= 12:
            raise ValueError(f"Mes no válido: {month!r}")

        # Si el mes (o el año completo) ya está cargado, no se hace nada para no duplicar multas.
        if self._esta_cargado(year, month):
            return

        # Se descargan (o se recuperan de la caché) los datos y se limpian.
        resultado = self.load(year, month, self.cacheurl)
        self.clean(resultado)

        # Al añadir un año completo, se descartan los meses de ese año que ya estaban cargados sueltos.
        if month is None:
            meses_previos = [m for (m, a) in self._loaded if a == year and m is not None]
            if meses_previos:
                resultado = resultado[~resultado["MES"].isin(meses_previos)]

                # Nota aclaratoria: Esta condición se generó con ayuda de una herramienta de inteligencia artificial
                # (Claude, de Anthropic). El contenido ha sido revisado por el autor.
                self._loaded = [(m, a) for (m, a) in self._loaded if a != year]

        # Se añade al dataframe data actual (concatenando filas).
        if self._data.empty:
            self._data = resultado
        else:
            self._data = pd.concat([self._data, resultado])

        # Se actualiza el atributo loaded con el mes y año cargados.
        self._loaded.append((month, year))

    def fines_hour(self, fig_name: str) -> None:
        """Genera un gráfico de líneas con la evolución del número de multas a lo largo de las horas del día.

        Si hay varios meses cargados, dibuja una línea por cada mes. Se guarda el gráfico con nombre fig_name.

        Args:
            fig_name: Nombre (o ruta) del fichero de imagen a generar, por ejemplo `evolucion_multas.png`.

        Excepciones:
            MadridError: Si no hay datos cargados o no se puede guardar el gráfico.
        """
        df = self._datos_para_analisis(["ANIO", "MES", "HORA"])

        # La hora viene en formato decimal (ej. 10.42), así que la parte entera corresponde a la hora del día.
        horas = pd.to_numeric(df["HORA"], errors="coerce").floordiv(1)
        conteo = (
            df.assign(HORA_DIA=horas)
            .dropna(subset=["HORA_DIA"])
            .astype({"HORA_DIA": int})
            .groupby(["ANIO", "MES", "HORA_DIA"])
            .size()
        )

        fig, ax = plt.subplots(figsize=(10, 5))
        try:
            # Una línea por cada (año, mes); las horas sin multas se representan con 0.
            for (anio, mes), serie in conteo.groupby(level=["ANIO", "MES"]):
                serie = serie.droplevel(["ANIO", "MES"]).reindex(range(24), fill_value=0)
                ax.plot(serie.index, serie.values, marker="o", label=f"{anio}-{mes}")

            ax.set_title("Multas por hora")
            ax.set_xlabel("Hora")
            ax.set_ylabel("Número de multas")
            ax.legend()
            fig.savefig(fig_name)
        except OSError as e:
            raise MadridError(f"No se pudo guardar el gráfico {fig_name}: {e}") from e
        finally:
            plt.close(fig)

    def fines_calificacion(self) -> pd.DataFrame:
        """Analiza la distribución de multas por calificación, mes y año.

        Devuelve un DataFrame indexado por (MES, ANIO) con una columna por cada calificación
        (GRAVE, LEVE, MUY GRAVE) y el número total de multas de ese tipo en cada mes.

        Args:
            Ninguno.

        Excepciones:
            MadridError: Si no hay datos cargados o faltan columnas necesarias.
        """
        df = self._datos_para_analisis(["ANIO", "MES", "CALIFICACION"])
        calificacion = df["CALIFICACION"].astype(str).str.strip()

        # Nota aclaratoria: Este cast se generó con ayuda de una herramienta de inteligencia artificial
        # (Claude, de Anthropic). El contenido ha sido revisado y probado por el autor.
        return cast(
            pd.DataFrame,
            df.assign(CALIFICACION=calificacion)
            .groupby(["MES", "ANIO", "CALIFICACION"])
            .size()
            .unstack("CALIFICACION", fill_value=0)
        )

    def total_payments(self) -> pd.DataFrame:
        """Genera un resumen con el importe total (máximo y mínimo) recaudado por mes y año.

        Una multa puede tener descuento pronto pago del 50%, pero cabe la posibilidad de que el
        infractor no realice el pago en fecha para acogerse a dicho descuento. Por ello:
        el importe máximo supone que nadie se acoge al descuento (suma de IMP_BOL) y el mínimo
        supone que todas las multas con DESCUENTO = "SI" se pagan con el 50% de descuento.

        Args:
            Ninguno.

        Excepciones:
            MadridError: Si no hay datos cargados o faltan columnas necesarias.
        """
        df = self._datos_para_analisis(["ANIO", "MES", "IMP_BOL", "DESCUENTO"])

        importe = pd.to_numeric(df["IMP_BOL"], errors="coerce").fillna(0)
        con_descuento = df["DESCUENTO"].astype(str).str.strip().str.upper() == "SI"
        importe_minimo = importe.where(~con_descuento, importe * (1 - DESCUENTO_PRONTO_PAGO))

        return (
            pd.DataFrame({
                "MES": df["MES"],
                "ANIO": df["ANIO"],
                "IMPORTE_MAXIMO": importe,
                "IMPORTE_MINIMO": importe_minimo,
            })
            .groupby(["MES", "ANIO"])
            .sum()
        )

    # -- Nombres del enunciado --

    def fines_calification(self) -> pd.DataFrame:
        """Nombre del enunciado para `fines_calificacion`; devuelve el mismo resultado.

        Args:
            Ninguno.

        Excepciones:
            MadridError: Si no hay datos cargados o faltan columnas necesarias.
        """
        return self.fines_calificacion()

    def total_payment(self) -> pd.DataFrame:
        """Nombre del enunciado para `total_payments`; devuelve el mismo resultado.

        Args:
            Ninguno.

        Excepciones:
            MadridError: Si no hay datos cargados o faltan columnas necesarias.
        """
        return self.total_payments()

    # -- Métodos privados --

    def _esta_cargado(self, year: int, month: int|None) -> bool:
        """Comprueba si los datos del mes `month` (o del año completo) de `year` ya están en `data`.

        Args:
            year: Año a comprobar.
            month: Mes (1-12) a comprobar, o None para el año completo.

        Excepciones:
            Ninguna.
        """
        # Si el año completo ya está cargado, cualquiera de sus meses también lo está.
        if (None, year) in self._loaded:
            return True
        return month is not None and (month, year) in self._loaded

    def _datos_para_analisis(self, columnas: list[str]) -> pd.DataFrame:
        """Devuelve el dataset `data`, comprobando que tenga datos y las columnas indicadas.

        Args:
            columnas: Columnas que deben existir en el dataset.

        Excepciones:
            MadridError: Si no hay datos cargados o falta alguna de las columnas.
        """
        if self._data.empty:
            raise MadridError("No hay datos cargados. Usa add() antes de analizar.")

        faltan = [c for c in columnas if c not in self._data.columns]
        if faltan:
            raise MadridError(f"Faltan columnas en los datos: {', '.join(faltan)}")

        return self._data
