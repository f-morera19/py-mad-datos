from pathlib import Path
from cache import Cache, CacheError
import hashlib, requests, json

class CacheUrl(Cache):
    """
        Especialización de la clase Cache para trabajar específicamente con datos cargados
        de internet (URLs).

        Atributos:
            app_name: Nombre asociado a la aplicación concreta. Se utilizará para
                crear una sub-carpeta dentro de la carpeta CACHE_DIR.
            cache_dir: Ruta completa de la sub-carpeta que se utilizará para
                almacenar datos en disco.
            obsolescence: Cantidad de días por los cuales se consideran válidos
                los datos de la caché.
    """

    def get(self, url: str, **kwargs) -> str:
        """Realiza un get a la URL indicada. Consulta si existe ya un objeto
        asociado a esta petición, si no lo tiene realiza la petición correspondiente,
        guarda el resultado en la caché y devuelve el objeto correspondiente.

        Args:
            url: URL indicada.
            **kwargs: Parámetros opcionales de la petición. Deben de ser filtros válidos para los datos de la url
            en cuestión

        Excepciones:
           CacheError
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
            **kwargs: Parámetros opcionales de la petición. Deben de ser filtros válidos para los datos de la url
            en cuestión. Por ejemplo: {"CALIFICACIÓN": "GRAVE"}, {"LUGAR": "CL CLARA DEL REY 36"}, etc.

        Excepciones:
            CacheError: Si la petición falla o el servidor no responde con 200.
        """
        # Buscamos por el hash del url + los parámetros recibidos.
        url_hashed = self._obtener_hash_completo(name, kwargs)
        return super().exists(url_hashed)

    def load(self, name: str, **kwargs) -> str:
        """Recupera los datos almacenados en caché, con el nombre name.

            Args:
                name: Nombre del dato a obtener.
                **kwargs: Parámetros opcionales de la petición.

            Excepciones:
                CacheError si no existe dato asociado o si no se pudo leer archivo.
        """
        url_hashed = self._obtener_hash_completo(name, kwargs)
        return super().load(url_hashed)

    def how_old(self, name: str, **kwargs) -> float:
        """Determina la edad en milisegundos del fichero almacenado en la caché con
            el nombre name.

        Args:
            name: Nombre del dato a obtener.
             **kwargs: Parámetros opcionales de la petición.

        Excepciones:
            CacheError: Si no existe dato o no se puede consultar edad.
        """
        url_hashed = self._obtener_hash_completo(name, kwargs)
        return super().how_old(url_hashed)

    def delete(self, name: str, **kwargs) -> None:
        """Borra de la caché el fichero con el nombre name.

        Excepciones:
            CacheError si no existe dato especificado o si no se pudo borrar.
            **kwargs: Parámetros opcionales de la petición.
        """
        url_hashed = self._obtener_hash_completo(name, kwargs)
        super().delete(url_hashed)

    @staticmethod
    def _obtener_hash_completo(url: str, kwargs : dict) -> str:
        """Hash de la url junto con los parámetros opcionales de la petición.

            Args:
                url: URL consultada.
                **kwargs: Parámetros opcionales de la petición. Deben de ser filtros válidos para los datos de la url
                en cuestión. Por ejemplo: {"CALIFICACIÓN": "GRAVE"}, {"LUGAR": "CL CLARA DEL REY 36"}, etc.

        """
        # Se serializa un diccionario en un objeto json que podemos representar como un string.
        params = json.dumps(kwargs, sort_keys=True, default=str)
        return hashlib.md5(f"{url}|{params}".encode("utf-8")).hexdigest()

