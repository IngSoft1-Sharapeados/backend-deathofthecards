# Aplicacion web del juego Agatha Christie's Death on the Cards

## Descripcion
Este proyecto es una adaptacion del juego de mesa **Agatha Christie's Death on the Cards** a version web.
Para el backend se usa [FastAPI](https://fastapi.tiangolo.com/).

## Instrucciones
El proyecto usa la version de Python 3.12.3, por lo que se recomienda ejecutarlo en un entorno virtual en Linux.

- Para instalar el paquete que contiene el modulo ```venv``` para entornos virtuales, abrir una terminal y ejecutar:
 
 ```sudo apt install python3-venv```

- Luego, desde la terminal dirigirse al path donde se tiene descargado el repositorio:

```cd /path/to/repository```

- Crear el entorno virtual:

```python3 -m venv .venv```

- Activar el entorno virtual:

```source .venv/bin/activate```

- Con el entorno virtual activo, instalar los requerimientos del proyecto:

```pip install -r requirements.txt```

- Finalmente,para correr el servidor, dirigirse a la carpeta `src` del proyecto:

```cd src/```

- Ejecutar:

```uvicorn main:app --reload```



- Para correr los tests:

Dirigirse al directorio raiz del repositorio:

```cd path/to/repository```

Ejecutar

```pytest tests```
