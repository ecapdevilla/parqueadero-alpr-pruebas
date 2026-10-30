# Parqueadero ALPR — versión con validación local

## Qué incorpora esta versión

- Panel principal con métricas de detecciones y estado de revisión.
- Bandeja para revisar las matrículas detectadas, abrir la imagen guardada, corregir la lectura, aprobar, dejar pendiente, descartar o marcar como duplicado.
- Búsqueda por matrícula/ID, filtros por estado, confianza y fechas.
- Informes con distribución de confianza, estados de revisión y actividad por hora.
- Exportación CSV con lectura original y validada, estado, fuente, confianza y observaciones.
- Exportación de respaldo JSON de las decisiones de revisión.
- Las revisiones se guardan en `localStorage` del navegador; no se ha añadido base de datos.
- La tabla permite corregir y guardar matrículas pendientes directamente, sin abrir el modal una por una.
- Al corregir una lectura OCR, se guarda una sugerencia local para futuras detecciones con exactamente la misma lectura original. La sugerencia sigue pendiente y debe confirmarse visualmente; no se aprueba automáticamente.
- El respaldo JSON incluye tanto las revisiones como la memoria de correcciones.
- Las capturas nuevas guardan una ruta de imagen en el CSV para que la interfaz pueda mostrarlas.
- Compatibilidad con el CSV antiguo: al iniciar, el programa crea una copia `registro_placas.csv.backup_FECHA_HORA` y normaliza las columnas.
- Validación básica del contenido de imagen enviado al endpoint `/procesar`.

## Cómo ejecutar en el computador de pruebas

1. Haz una copia completa de la carpeta del proyecto antes de sustituir archivos.
2. Conserva el entorno Python en el que ya funciona `fast-alpr` y sus dependencias.
3. Abre PowerShell dentro de la carpeta del proyecto.
4. Ejecuta:

   ```powershell
   python app.py
   ```

5. Abre `http://127.0.0.1:5000` en el mismo computador.
6. Entra en **Captura en vivo**, inicia la cámara y luego revisa los resultados en **Validar detecciones**.

La primera carga del modelo puede tardar. No cierres la consola mientras uses la aplicación.

## Importante sobre LocalStorage

Las decisiones de revisión y la memoria de correcciones se guardan en el navegador y perfil de usuario donde se hicieron. No se guardan en el CSV original ni se comparten automáticamente con otros navegadores. Usa **Exportar respaldo de revisiones** para guardar un JSON. La exportación CSV desde la interfaz sí combina los datos del servidor con las decisiones locales.

Si borras los datos del sitio del navegador, las revisiones locales pueden perderse. Exporta el respaldo periódicamente.

## Sobre los registros históricos

Los registros antiguos no tienen una ruta de imagen asociada de forma fiable. Se mostrarán como «Sin foto» en lugar de intentar relacionar automáticamente una imagen que pudiera pertenecer a otra matrícula. Las capturas nuevas sí quedan vinculadas al registro.

## Alcance actual

Esta versión sigue siendo un prototipo local de pruebas, sin autenticación y sin base de datos. No calcula todavía entradas/salidas reales ni tiempo de permanencia: las estadísticas cuentan detecciones, no vehículos únicos. Antes de usarlo operativamente, revisa manualmente los resultados, exporta copias de seguridad y define las reglas de conservación de imágenes.
