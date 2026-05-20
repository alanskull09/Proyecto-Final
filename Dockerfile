# Usar una imagen ligera de Python
FROM python:3.9-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar el código al contenedor
COPY . /app

# Dar permisos de ejecución al CLI
RUN chmod +x cli.py

# Establecer el CLI como punto de entrada por defecto
ENTRYPOINT ["python", "cli.py"]