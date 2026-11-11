from pathlib import Path
import time, hashlib, requests, json

# Carpeta por defecto donde se almacenaran los datos.
CACHE_DIR = Path.home() / ".my_cache"
MS_POR_DIA = 24 * 60 * 60 * 1000   # 86_400_000 (Milisegundos en un día)

class CacheError(Exception):
    """Cualquier error producido en el módulo caché."""

class Cache:
    """
    Esta clase se encarga de guardar y recuperar datos en disco, de forma que estén disponibles incluso después
    de cerrar el programa.

    Atributos:
        app_name: Nombre asociado a la aplicación concreta. Se utilizará para
            crear una sub-carpeta dentro de la carpeta CACHE_DIR.
        cache_dir: Ruta completa de la sub-carpeta que se utilizará para
            almacenar datos en disco.
        obsolescence: Cantidad de días por los cuales se consideran válidos
            los datos de la caché.
    """

    def __init__(self, app_name: str, obsolescence: int):
        """Inicializa la caché con el nombre de la aplicación y el límite de obsolescencia.

        Args:
            app_name: Nombre asociado a la aplicación concreta. Se utilizará para
                crear una sub-carpeta dentro de la carpeta CACHE_DIR.
            obsolescence: Cantidad de días por los cuales se consideran válidos
                los datos de la caché.

        Excepciones:
            CacheError: Si app_name no es un string no vacío o si obsolescence no es un entero >= 0.
        """
        if not isinstance(app_name, str) or not app_name.strip():
            raise CacheError("app_name debe ser un string no vacío")
        if not isinstance(obsolescence, int) or obsolescence < 0:
            raise CacheError("obsolescence debe ser un entero >= 0")

        self._app_name = app_name
        self._cache_dir = CACHE_DIR
        self._obsolescence = obsolescence

    # -- Propiedades --

    @property
    def app_name(self) -> str:
        """Devuelve el nombre asociado a la aplicación.

        Args:
            Ninguno.

        Excepciones:
            Ninguna.
        """
        return self._app_name

    @property
    def cache_dir(self) -> str:
        """Devuelve la ruta de la carpeta raíz de la caché.

        Args:
            Ninguno.

        Excepciones:
            Ninguna.
        """
        return str(self._cache_dir)

    @property
    def obsolescence(self) -> int:
        """Devuelve la cantidad de días por los cuales se consideran válidos los datos de la caché.

        Args:
            Ninguno.

        Excepciones:
            Ninguna.
        """
        return self._obsolescence

    @cache_dir.setter
    def cache_dir(self, nueva_cache_dir: str) -> None:
        """Establece una nueva ruta para la carpeta raíz de la caché.

        Args:
            nueva_cache_dir: Nueva ruta de la carpeta raíz de la caché.

        Excepciones:
            CacheError: Si nueva_cache_dir no es un string no vacío.
        """
        if not isinstance(nueva_cache_dir, str) or not str(nueva_cache_dir).strip():
            raise CacheError("cache_dir debe ser una ruta no vacía")
        self._cache_dir = Path(nueva_cache_dir)

    # -- Métodos públicos --

    def set(self, name: str, data: str) -> None:
        """Almacena en cache_dir los datos en data con el nombre name.

        Args:
            name: Nombre del dato.
            data: Dato a almacenar.

        Excepciones:
            CacheError: Si name no es válido o no se puede escribir el fichero.
        """
        try:
            # Necesitamos crear el path completo.
            path_completo = self._obtener_ruta_completa(name)
            path_completo.write_text(data)
        except Exception as e:
            raise CacheError(f"No fué posible guardar {name}: {e}") from e

    def exists(self, name: str) -> bool:
        """Comprueba si ya existe un fichero con el nombre name en la caché cache_dir.

        Args:
            name: Nombre del dato a comprobar.

        Excepciones:
            Ninguna.
        """
        path_completo = self._obtener_ruta_completa(name)
        return path_completo.exists()

    def load(self, name: str) -> str:
        """Recupera los datos almacenados en caché, con el nombre name.

        Args:
            name: Nombre del fichero.

        Excepciones:
            CacheError: Si no existe dato asociado o si no se pudo leer el fichero.
        """
        path_completo = self._obtener_ruta_completa(name)
        try:
            return path_completo.read_text()
        except FileNotFoundError as e:
            raise CacheError(f"No existe ningún dato {path_completo}") from e
        except Exception as e:
            raise CacheError(f"No se pudo leer dato {path_completo}: {e}") from e

    def how_old(self, name: str) -> float:
        """Determina la edad en milisegundos del fichero almacenado en la caché con el nombre name.

        Args:
            name: Nombre del dato a consultar.

        Excepciones:
            CacheError: Si no existe dato o no se puede consultar su edad.
        """
        path_completo = self._obtener_ruta_completa(name)

        try:
            # Se utiliza st_mtime como fecha de última modificación de la metadata del archivo
            # en cuestión (Esto en Unix, en Windows es la fecha de creación).
            # Referencia: https://docs.python.org/3/library/stat.html
            tiempo_modificacion = path_completo.stat().st_mtime

            # Calcula la diferencia con la hora actual y pasa a milisegundos
            return (time.time() - tiempo_modificacion) * 1000
        except FileNotFoundError as e:
            raise CacheError(f"No existe dato {path_completo}") from e
        except Exception as e:
            raise CacheError(f"No se pudo consultar edad de dato: {e}") from e

    def delete(self, name: str) -> None:
        """Borra de la caché el fichero con el nombre name.

        Args:
            name: Nombre del dato a borrar.

        Excepciones:
            CacheError: Si no existe el dato especificado o si no se pudo borrar.
        """
        path_completo = self._obtener_ruta_completa(name)
        try:
            path_completo.unlink()
        except FileNotFoundError as e:
            raise CacheError(f"No existe ningún dato {path_completo}") from e
        except Exception as e:
            raise CacheError(f"No se pudo borrar {path_completo}: {e}") from e

    def clear(self) -> None:
        """Borra todos los elementos de la caché.

        Args:
            Ninguno.

        Excepciones:
            CacheError: Si no se logra limpiar la caché.
        """
        try:
            path_raiz = Path(self._cache_dir / self._app_name)

            # Referencia: https://docs-python-org.translate.goog/3/library/pathlib.html?_x_tr_sl=en&_x_tr_tl=es&_x_tr_hl=es&_x_tr_pto=tc
            # iterdir permite recorrer los elementos de primer nivel del path especificado.
            for path in path_raiz.iterdir():
                # Referencia: https://docs.python.org/3/library/pathlib.html#pathlib.Path.unlink.
                if path.is_file():
                    # Referencia: https://docs.python.org/3/library/pathlib.html#pathlib.Path.unlink.
                    path.unlink()
        except Exception as e:
            raise CacheError(f"No se pudo limpiar la caché: {e}") from e

    # -- Métodos privados

    def _obtener_ruta_completa(self, name: str) -> Path:
        """Genera la ruta completa para el dato especificado.

        Args:
            name: Nombre del dato del cual se desea obtener la ruta completa.

        Excepciones:
            Ninguna.
        """
        return Path(self._cache_dir / self._app_name / name)

    def _esta_caducado(self, name: str) -> bool:
        """Determina si el dato con el nombre name está caducado.

        Nota: Un dato caducado se define como aquel cuya edad es igual o mayor al límite de
        obsolescencia determinado.

        Args:
            name: Nombre del dato.

        Excepciones:
            CacheError: Si no existe el dato o no se puede consultar su edad.
        """
        # Obtenemos la edad en ms y la comparamos con el equivalente en ms del límite de obsolescencia.
        edad_ms = self.how_old(name)
        return edad_ms >= self.obsolescence * MS_POR_DIA


class CacheUrl(Cache):
    """
        Especialización de la clase Cache para trabajar específicamente con datos cargados
        de internet (URLs).
    """

    def get(self, url: str, **kwargs) -> str:
        """Realiza un get a la URL indicada.

        Consulta si existe ya un objeto asociado a esta petición; si no lo tiene, realiza la
        petición correspondiente, guarda el resultado en la caché y devuelve el objeto correspondiente.

        Args:
            url: URL indicada.
            **kwargs: Parámetros opcionales de la petición. Deben ser filtros válidos para los
                datos de la url en cuestión.

        Excepciones:
            CacheError: Si el servidor no responde con código 200 o si falla el acceso a la caché.
            requests.RequestException: Si la petición HTTP no se puede realizar.
        """
        url_hashed = self._obtener_hash_completo(url, kwargs)

        # Hay que consultar si existe ya un objeto asociado a esta petición y, en ese caso, si aún es no está caducado.
        if self.exists(url_hashed) and not self._esta_caducado(url_hashed):
            print("clave ya existe y valor no esta caducado")
            return self.load(url_hashed)

        # Si no exsite aún, podemos hacer el request, guardar objeto asociado y retornarlo.
        datos = requests.get(url)
        if datos.status_code == 200:
            kwargs[url_hashed] = datos  # nuevo registro en el fichero.
            print("Nueva llave creada con éxito")
            return kwargs[url_hashed]
        else:
            raise CacheError(f"Se obtuvo error al tratar de obtener "
                             f"información de {url}, con código de estado {datos.status_code}")

    def exists(self, name: str, **kwargs) -> bool:
        """Comprueba si ya existe un dato para esta solicitud en la caché.

        Args:
            name: URL consultada.
            **kwargs: Parámetros opcionales de la petición. Deben ser filtros válidos para los
                datos de la url en cuestión. Por ejemplo: {"CALIFICACIÓN": "GRAVE"},
                {"LUGAR": "CL CLARA DEL REY 36"}, etc.

        Excepciones:
            Ninguna.
        """
        # Buscamos por el hash del url + los parámetros recibidos.
        url_hashed = self._obtener_hash_completo(name, kwargs)
        return super().exists(url_hashed)

    def load(self, name: str, **kwargs) -> str:
        """Recupera los datos almacenados en caché para la URL name y los parámetros indicados.

        Args:
            name: URL del dato a obtener.
            **kwargs: Parámetros opcionales de la petición.

        Excepciones:
            CacheError: Si no existe dato asociado o si no se pudo leer el fichero.
        """
        url_hashed = self._obtener_hash_completo(name, kwargs)
        return super().load(url_hashed)

    def how_old(self, name: str, **kwargs) -> float:
        """Determina la edad en milisegundos del dato almacenado en la caché para la URL name.

        Args:
            name: URL del dato a consultar.
            **kwargs: Parámetros opcionales de la petición.

        Excepciones:
            CacheError: Si no existe dato o no se puede consultar su edad.
        """
        url_hashed = self._obtener_hash_completo(name, kwargs)
        return super().how_old(url_hashed)

    def delete(self, name: str, **kwargs) -> None:
        """Borra de la caché el dato asociado a la URL name y los parámetros indicados.

        Args:
            name: URL del dato a borrar.
            **kwargs: Parámetros opcionales de la petición.

        Excepciones:
            CacheError: Si no existe el dato especificado o si no se pudo borrar.
        """
        url_hashed = self._obtener_hash_completo(name, kwargs)
        super().delete(url_hashed)

    @staticmethod
    def _obtener_hash_completo(url: str, kwargs : dict) -> str:
        """Calcula el hash MD5 de la url junto con los parámetros opcionales de la petición.

        Args:
            url: URL consultada.
            kwargs: Diccionario con los parámetros opcionales de la petición. Deben ser filtros
                válidos para los datos de la url en cuestión. Por ejemplo: {"CALIFICACIÓN": "GRAVE"},
                {"LUGAR": "CL CLARA DEL REY 36"}, etc.

        Excepciones:
            Ninguna.
        """
        # Se serializa un diccionario en un objeto json que podemos representar como un string.
        params = json.dumps(kwargs, sort_keys=True, default=str)
        return hashlib.md5(f"{url}|{params}".encode("utf-8")).hexdigest()
