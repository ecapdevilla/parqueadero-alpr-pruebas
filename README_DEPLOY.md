# Despliegue de pruebas en la web

## Arquitectura recomendada

La aplicación de captura en vivo necesita ejecutar Flask, cargar el modelo ALPR y conservar las capturas. Para una prueba funcional se recomienda desplegar **toda la aplicación como un servicio web de Render**, con HTTPS y un disco persistente. El navegador del supervisor usa su propia cámara y envía fotogramas al servidor; no se necesita conectar una cámara USB al servidor.

Vercel no se usa en esta configuración: sus funciones no ofrecen el almacenamiento local persistente que utiliza actualmente esta aplicación para el CSV y las imágenes. El modo local sigue funcionando con `python app.py`.

## Preparar el repositorio

El repositorio puede ser público, pero no se deben subir datos de detecciones. `.gitignore` excluye `registro_placas.csv`, `storage/`, las imágenes y archivos de respaldo. Antes de publicar, confirma que no hayas agregado esos archivos manualmente al índice de Git.

## Crear el servicio de prueba

1. Crea un servicio **Web Service** desde el repositorio en Render.
2. Usa el runtime Python y configura:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app --workers 1 --threads 1 --timeout 120 --bind 0.0.0.0:$PORT`
   - Health check path: `/healthz`
3. Selecciona un plan compatible con el modelo ALPR y agrega un disco persistente. El disco es un recurso de pago; confirma el costo en Render antes de crear el servicio. Móntalo en `/var/data`.
4. Configura estas variables de entorno:
   - `APP_ENV` = `production`
   - `DATA_DIR` = `/var/data`
   - `PARKING_APP_USERNAME` = nombre de usuario para el supervisor
   - `PARKING_APP_PASSWORD` = contraseña única y robusta, configurada en Render; no la incluyas en Git.
5. Espera a que termine el despliegue. Al abrir el sitio, el navegador solicitará las credenciales de acceso. Usa HTTPS y comparte esas credenciales solo con los supervisores autorizados.

La aplicación devuelve un error de configuración en vez de dejar rutas y capturas expuestas si `APP_ENV=production` y faltan las credenciales. `/healthz` queda disponible para las comprobaciones automáticas del proveedor.

## Almacenamiento y límites de la prueba

- Mantén una sola instancia y un solo trabajador del servidor: el prototipo usa un CSV y estado en memoria, no una base de datos compartida.
- El disco persistente guarda el CSV y las nuevas capturas en `/var/data`. Conserva respaldos fuera del servidor; un disco no es un sistema de copias de seguridad.
- Las revisiones y correcciones del operador siguen guardándose en el `localStorage` de su navegador. No se comparten entre supervisores ni navegadores.
- La primera carga del modelo puede tardar. Verifica que el plan seleccionado tenga memoria y CPU suficientes antes de invitar a usuarios.
- El usuario y contraseña de acceso protegen las rutas de la aplicación. No habilites un despliegue público sin configurar dichas credenciales.

## Ejecutar localmente

```powershell
python app.py
```

En local, si `APP_ENV` no es `production`, no se solicita autenticación. La aplicación escucha en `http://127.0.0.1:5000`.