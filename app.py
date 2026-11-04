from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from fast_alpr import ALPR
import cv2
import base64
import csv
import hmac
import os
import re
from datetime import datetime, timedelta
import numpy as np
import io
import uuid
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))

UMBRAL_CONFIANZA = 0.70
DATA_DIR = os.path.abspath(os.environ.get('DATA_DIR', BASE_DIR))
ARCHIVO_CSV = os.path.join(DATA_DIR, 'registro_placas.csv')
CARPETA_STORAGE = os.path.join(DATA_DIR, 'storage')
os.makedirs(CARPETA_STORAGE, exist_ok=True)
CSV_LOCK = threading.Lock()
CSV_COLUMNS = ['id', 'fecha_hora', 'placa', 'confianza', 'fuente', 'imagen_path']


@app.before_request
def require_deployment_authentication():
    if os.environ.get('APP_ENV') != 'production' or request.endpoint == 'health_check':
        return None

    username = os.environ.get('PARKING_APP_USERNAME')
    password = os.environ.get('PARKING_APP_PASSWORD')
    if not username or not password:
        app.logger.error('La autenticación de producción no está configurada.')
        return jsonify({'error': 'El acceso de producción no está configurado.'}), 503

    credentials = request.authorization
    if (credentials is None
            or not hmac.compare_digest(credentials.username or '', username)
            or not hmac.compare_digest(credentials.password or '', password)):
        return 'Autenticación requerida.', 401, {
            'WWW-Authenticate': 'Basic realm="Parqueadero ALPR", charset="UTF-8"'
        }

    return None


def asegurar_csv_compatible():
    """Normaliza el CSV antiguo y conserva una copia antes de modificarlo."""
    if not os.path.exists(ARCHIVO_CSV) or os.path.getsize(ARCHIVO_CSV) == 0:
        with open(ARCHIVO_CSV, 'w', newline='', encoding='utf-8-sig') as f:
            csv.DictWriter(f, fieldnames=CSV_COLUMNS).writeheader()
        return
    with open(ARCHIVO_CSV, 'r', newline='', encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))
    if not rows:
        return
    if rows[0] == CSV_COLUMNS:
        return
    backup = ARCHIVO_CSV + '.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S')
    try:
        import shutil
        shutil.copy2(ARCHIVO_CSV, backup)
    except Exception as exc:
        print(f'No se pudo crear copia del CSV: {exc}')
    old_header = [x.strip().lower() for x in rows[0]]
    data_rows = rows[1:] if any(x in old_header for x in ('fecha_hora', 'placa', 'confianza')) else rows
    normalized = []
    for i, row in enumerate(data_rows, start=1):
        if not row:
            continue
        # Compatibilidad con el formato antiguo de tres o cuatro columnas.
        if len(row) >= 4 and not old_header == CSV_COLUMNS:
            fecha, placa, confianza, fuente = row[:4]
        elif len(row) >= 3:
            fecha, placa, confianza = row[:3]
            fuente = row[3] if len(row) >= 4 else 'historico'
        else:
            continue
        normalized.append({
            'id': f'historico-{i:06d}',
            'fecha_hora': fecha,
            'placa': placa,
            'confianza': confianza,
            'fuente': fuente or 'historico',
            'imagen_path': ''
        })
    temp = ARCHIVO_CSV + '.tmp'
    with open(temp, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(normalized)
    os.replace(temp, ARCHIVO_CSV)
    print(f'CSV actualizado: {len(normalized)} registros. Copia previa: {os.path.basename(backup)}')


def leer_registros():
    asegurar_csv_compatible()
    records = []
    with CSV_LOCK:
        with open(ARCHIVO_CSV, 'r', newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                try:
                    conf = float(row.get('confianza') or 0)
                except (ValueError, TypeError):
                    conf = 0.0
                image_path = (row.get('imagen_path') or '').strip()
                image_url = None
                if image_path:
                    safe_name = os.path.basename(image_path.replace('\\', '/'))
                    if safe_name and os.path.isfile(os.path.join(CARPETA_STORAGE, safe_name)):
                        image_url = '/storage/' + safe_name
                records.append({
                    'id': row.get('id') or f'historico-{len(records)+1:06d}',
                    'fecha_hora': row.get('fecha_hora', ''),
                    'placa': row.get('placa', ''),
                    'confianza': conf,
                    'fuente': row.get('fuente', 'historico'),
                    'imagen_url': image_url,
                })
    return records


def guardar_en_csv(placa, confianza, fuente='web', imagen_path=''):
    fecha_hora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    record_id = uuid.uuid4().hex[:12]
    with CSV_LOCK:
        asegurar_csv_compatible()
        with open(ARCHIVO_CSV, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writerow({
                'id': record_id,
                'fecha_hora': fecha_hora,
                'placa': placa,
                'confianza': f'{float(confianza):.4f}',
                'fuente': fuente,
                'imagen_path': imagen_path,
            })
    return record_id, fecha_hora


print('Cargando modelo... (la primera vez puede tardar)')
alpr = ALPR(
    detector_model='yolo-v9-t-384-license-plate-end2end',
    ocr_model='global-plates-mobile-vit-v2-model',
)
print('Modelo cargado correctamente.')

contador_total = 0
placas_detectadas = []
placas_activas = {}
TIEMPO_DEDUPLICACION = 30.0


def procesar_resultados(resultados, frame=None):
    global contador_total, placas_detectadas, placas_activas
    encontrados = []
    ahora = datetime.now()
    placas_activas = {k: v for k, v in placas_activas.items()
                      if (ahora - v).total_seconds() < TIEMPO_DEDUPLICACION}
    for res in resultados:
        if not (hasattr(res, 'ocr') and res.ocr is not None):
            continue
        placa = re.sub(r'\s+', '', str(getattr(res.ocr, 'text', '') or '').upper())
        raw = getattr(res.ocr, 'confidence', 0.0)
        if isinstance(raw, (list, tuple)):
            confianza = sum(float(x) for x in raw) / len(raw) if raw else 0.0
        else:
            try:
                confianza = float(raw)
            except (ValueError, TypeError):
                confianza = 0.0
        if not placa or confianza < UMBRAL_CONFIANZA:
            print(f'Detección no registrada: {placa!r} (confianza {confianza:.2f})')
            continue
        if placa in placas_activas:
            print(f'Duplicado omitido temporalmente: {placa}')
            continue
        placas_activas[placa] = ahora
        image_path = ''
        if frame is not None:
            filename = f'captura_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.jpg'
            full_path = os.path.join(CARPETA_STORAGE, filename)
            if cv2.imwrite(full_path, frame):
                image_path = filename
        record_id, fecha_hora = guardar_en_csv(placa, confianza, 'web', image_path)
        contador_total += 1
        item = {
            'id': record_id,
            'placa': placa,
            'confianza': confianza,
            'timestamp': fecha_hora,
            'contador': contador_total,
            'imagen_url': ('/storage/' + image_path) if image_path else None,
        }
        placas_detectadas.append(item)
        placas_detectadas = placas_detectadas[-100:]
        encontrados.append(item)
        print(f'Detectada: {placa} (confianza: {confianza:.2f})')
    return encontrados


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/healthz')
def health_check():
    return jsonify({'status': 'ok'})


@app.route('/storage/<path:filename>')
def storage_file(filename):
    # Solo se sirven archivos dentro de la carpeta de capturas.
    return send_from_directory(CARPETA_STORAGE, filename, as_attachment=False, max_age=0)


@app.route('/api/estado', methods=['GET'])
def estado():
    registros = leer_registros()
    return jsonify({
        'total_placas': len(registros),
        'ultima_placa': registros[-1] if registros else None,
        'placas_recientes': registros[-10:],
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })


@app.route('/api/registros', methods=['GET'])
def api_registros():
    registros = leer_registros()
    return jsonify({'success': True, 'registros': registros, 'total': len(registros)})


@app.route('/procesar', methods=['POST'])
def procesar():
    try:
        data = request.get_json(silent=True) or {}
        image_data = data.get('image', '')
        if not isinstance(image_data, str) or ',' not in image_data:
            return jsonify({'success': False, 'error': 'No se recibió una imagen válida.'}), 400
        header, encoded = image_data.split(',', 1)
        if not header.startswith('data:image/'):
            return jsonify({'success': False, 'error': 'El contenido recibido no parece ser una imagen.'}), 400
        image_bytes = base64.b64decode(encoded, validate=True)
        if len(image_bytes) > 8 * 1024 * 1024:
            return jsonify({'success': False, 'error': 'La imagen supera el límite de 8 MB.'}), 413
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify({'success': False, 'error': 'No se pudo decodificar la imagen.'}), 400
        resultados = alpr.predict(frame)
        encontrados = procesar_resultados(resultados, frame)
        return jsonify({
            'success': True,
            'placas': encontrados,
            'contador_actual': len(leer_registros())
        })
    except Exception as e:
        app.logger.exception('Error procesando imagen')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/descargar_csv', methods=['GET'])
def descargar_csv():
    if not os.path.exists(ARCHIVO_CSV):
        return 'No hay datos disponibles', 404
    return send_file(ARCHIVO_CSV, mimetype='text/csv; charset=utf-8', as_attachment=True,
                     download_name='registro_placas.csv')


if __name__ == '__main__':
    asegurar_csv_compatible()
    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
