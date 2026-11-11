from pathlib import Path
import time

# Carpeta por defecto donde se almacenaran los datos.
CACHE_DIR = Path.home() / ".my_cache"

class CacheError(Exception):
    """Cualquier error producido en el módulo caché."""

class Cache:
    """
    Se encarga de guardar y recuperar datos en disco, de forma que estén disponibles incluso después
    de cerrar el programa.

    Atributos:
        app_name: Nombre asociado a la aplicación concreta. Se utilizará para
            crear una sub-carpeta dentro de la carpeta CACHE_DIR.
        cache_dir: Ruta completa de la sub-carpeta que se utilizará para
            almacenar datos en disco.
        obsolescence: Cantidad de días por los cuales se consideran válidos
            los datos de la caché.

    Excepciones:
        CacheError: Si los argumentos no son válidos.
    """
    def __init__(self, app_name: str, obsolescence: int):
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
        return self._app_name

    @property
    def cache_dir(self) -> str:
        return str(self._cache_dir)

    @property
    def obsolescence(self) -> int:
        return self._obsolescence

    @cache_dir.setter
    def cache_dir(self, nueva_cache_dir: str) -> None:
        if not isinstance(nueva_cache_dir, str) or not str(nueva_cache_dir).strip():
            raise CacheError("cache_dir debe ser una ruta no vacía")
        self._cache_dir = Path(nueva_cache_dir)

    # -- Métodos públicos --

    def set(self, name: str, data: str) -> None:
        """Almacena en cache_dir los datos en data con el nombre name.

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
        """Comprueba si ya existe un fichero con el nombre name en la caché cache_dir."""
        path_completo = self._obtener_ruta_completa(name)
        return path_completo.exists()

    def load(self, name: str) -> str:
        """Recupera los datos almacenados en caché, con el nombre name.

        Excepciones:
            CacheError si no existe dato asociado o si no se pudo leer archivo.
        """
        path_completo = self._obtener_ruta_completa(name)
        try:
            return path_completo.read_text()
        except FileNotFoundError as e:
            raise CacheError(f"No existe ningún dato {path_completo}") from e
        except Exception as e:
            raise CacheError(f"No se pudo leer dato {path_completo}: {e}") from e

    def how_old(self, name: str) -> float:
        """Determina la edad en milisegundos del fichero almacenado en la caché con
        el nombre name.

        Excepciones:
            CacheError: Si no existe dato o no se puede consultar edad.
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

        Excepciones:
            CacheError si no existe dato especificado o si no se pudo borrar.
        """
        path_completo = self._obtener_ruta_completa(name)
        try:
            path_completo.unlink()
        except FileNotFoundError as e:
            raise CacheError(f"No existe ningún dato {path_completo}") from e
        except Exception as e:
            raise CacheError(f"No se pudo borrar {path_completo}: {e}") from e

    def clear(self) -> None:
        """Borra todos los elementos de la caché."""
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
        return Path(self._cache_dir / self._app_name / name)