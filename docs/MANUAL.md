# Manual de Usuario - Sistema Básico de Administración de Configuración (SBAC)

## Requisitos Previos
* Python 3.9 o superior instalado en el sistema.
* No se requieren dependencias externas.

## Uso Básico
El sistema se opera a través de la línea de comandos utilizando el archivo `cli.py`. La sintaxis general es:
`python cli.py <comando> [argumentos]`

### Comandos Disponibles:

**1. Iniciar un repositorio**
Inicializa un nuevo repositorio en el directorio actual, creando la estructura oculta `.sbac`.
> `python cli.py init`

**2. Añadir archivos al seguimiento**
Prepara un archivo para ser incluido en la siguiente versión.
> `python cli.py add <ruta_del_archivo>`

**3. Ver el estado del repositorio**
Muestra una lista de todos los archivos que actualmente están siendo rastreados por SBAC.
> `python cli.py status`

**4. Crear una nueva versión (Commit)**
Guarda una versión inmutable de todos los archivos rastreados con un mensaje descriptivo.
> `python cli.py commit "Tu mensaje descriptivo aquí"`

**5. Ver el historial de versiones**
Muestra la lista de commits realizados, incluyendo su ID, fecha y mensaje.
> `python cli.py history`

**6. Crear una Línea Base**
Asigna un nombre legible a un commit específico. Si no se proporciona un ID de commit, se asignará al último commit realizado.
> `python cli.py baseline "NOMBRE_LINEA_BASE" [--commit ID_OPCIONAL]`

**7. Listar Líneas Base**
Muestra todas las líneas base registradas y a qué ID de commit apuntan.
> `python cli.py list-baselines`

**8. Mostrar diferencias entre versiones**
Compara dos versiones (pueden ser IDs de commits o nombres de líneas base) y muestra las diferencias exactas en el código.
> `python cli.py diff <versión_1> <versión_2>`

**9. Regresar a una versión anterior (Checkout)**
Restaura los archivos en tu directorio de trabajo a como estaban en la versión o línea base indicada.
> `python cli.py checkout <versión>`