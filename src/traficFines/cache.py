from pathlib import Path

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
            CacheError: Si los argumentos no son válidos o no se puede crear
                el directorio.
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

    # -- Métodos públicos --

    def set(self, name: str, data: str) -> None:
        """Almacena en cache_dir los datos en data con el nombre name.

        Excepciones:
            CacheError: Si name no es válido o no se puede escribir el fichero.
        """
        try:
            # Necesitamos crear el path completo.
            path_completo = Path(self._cache_dir / self._app_name / name)
            path_completo.write_text(data)
        except Exception as e:
            raise CacheError(f"No fué posible guardar {name}: {e}") from e

    def exists(self, name: str) -> bool:
        """Comprueba si ya existe un fichero con el nombre name en la caché cache_dir.

        Excepciones:
            CacheError si `name` no es válido o no se logra escribir en él.
        """

    def load(self, name: str) -> str:
        """Recupera los datos almacenados en caché, con el nombre name.

        Excepciones:
            CacheError si no existe dato asociado.
        """

    def how_old(self, name: str) -> float:
        """Determina la edad en milisegundos del fichero almacenado en la caché con
        el nombre name."""

    def delete(self, name: str) -> None:
        """Borra de la caché el fichero con el nombre name."""

    def clear(self) -> None:
        """Borra todos los elementos de la caché."""