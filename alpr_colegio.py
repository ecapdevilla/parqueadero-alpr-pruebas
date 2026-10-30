import cv2
import csv
import time
import sys
import os
from datetime import datetime
from fast_alpr import ALPR

# ============================================================
# CONFIGURACIÓN
# ============================================================
UMBRAL_CONFIANZA = 0.7
SEGUNDOS_ENTRE_ANALISIS = 2
ARCHIVO_CSV = "registro_placas.csv"

# ⚠️ Asegúrate de que este sea el índice de tu cámara USB (según listar_camaras.py)
INDICE_CAMARA = 0  # HP Webcam (USB)

# ============================================================
# INICIALIZAR MODELO
# ============================================================
print("Cargando modelo... (la primera vez puede tardar)")
alpr = ALPR(
    detector_model="yolo-v9-t-384-license-plate-end2end",
    ocr_model="global-plates-mobile-vit-v2-model",
)
print("Modelo cargado correctamente.\n")

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================
FUENTE_ACTUAL = "camara"

def guardar_en_csv(placa, confianza):
    archivo_nuevo = not os.path.exists(ARCHIVO_CSV)
    with open(ARCHIVO_CSV, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if archivo_nuevo:
            writer.writerow(["fecha_hora", "placa", "confianza", "fuente"])
        fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([fecha_hora, placa, f"{confianza:.2f}", FUENTE_ACTUAL])
        print(f"[{fecha_hora}] Guardado: {placa} (Confianza: {confianza:.2f})")

def procesar_resultados(resultados, fuente="camara"):
    encontrados = []
    for res in resultados:
        if hasattr(res, 'ocr') and res.ocr is not None:
            placa = res.ocr.text.strip().upper()
            confianza_raw = res.ocr.confidence

            if isinstance(confianza_raw, list):
                confianza = sum(confianza_raw) / len(confianza_raw) if confianza_raw else 0.0
            else:
                confianza = confianza_raw

            if placa and confianza >= UMBRAL_CONFIANZA:
                encontrados.append((placa, confianza))
                guardar_en_csv(placa, confianza)
            else:
                print(f"Descartada: '{placa}' (Confianza: {confianza:.2f})")
    return encontrados

# ============================================================
# CÁMARA: usar DirectShow + MJPG, verificar disponibilidad
# ============================================================
def modo_camara():
    global FUENTE_ACTUAL
    FUENTE_ACTUAL = "camara"

    print(f"Intentando abrir cámara USB en índice {INDICE_CAMARA} (DirectShow + MJPG)...")

    # Intentar DirectShow primero (recomendado para USB), luego fallback a backend por defecto
    cap = cv2.VideoCapture(INDICE_CAMARA, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("DirectShow falló, intentando backend por defecto...")
        cap = cv2.VideoCapture(INDICE_CAMARA)

    # Forzar formato MJPG inmediatamente después de abrir
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap.isOpened():
        print(f"ERROR: 无法打开索引 {INDICE_CAMARA} 的摄像头。")
        print("1. 确认 listar_camaras.py 显示的索引是否正确")
        print("2. 检查摄像头是否被其他程序占用")
        return

    # 关键2：先设 MJPG 压缩格式，再设分辨率。顺序很重要！
    # USB 2.0 带宽不够传未压缩的 1280x720，设 MJPG 才能出图
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print("Precalentando cámara (5 segundos)...")
    time.sleep(5)  # 有些 USB 摄像头需要更长时间稳定

    # 丢弃前 15 帧，等自动曝光/白平衡稳定
    for _ in range(15):
        cap.read()
        time.sleep(0.1)

    # 验证是否真的能读到非黑帧
    ret, frame_prueba = cap.read()
    if not ret or frame_prueba is None:
        print("ADVERTENCIA: 摄像头打开了但读不到帧。")
        cap.release()
        return

    if frame_prueba.mean() < 5:
        print("ADVERTENCIA: 摄像头打开了但返回黑屏。")
        print("最可能的原因：")
        print("1. Avast / 杀毒软件的『摄像头保护』正在拦截 OpenCV")
        print("2. Teams / Zoom / OBS / 浏览器 正在后台占用摄像头")
        print("3. 尝试关闭杀毒软件的摄像头防护，或结束所有视频相关进程后重试")
        cap.release()
        return

    print(f"✅ 摄像头 {INDICE_CAMARA} 工作正常。按 'q' 退出。\n")

    ultima_placa = ""
    ultimo_tiempo = 0
    frames_negros_seguidos = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("读取帧失败。")
            break

        if frame.mean() < 5:
            frames_negros_seguidos += 1
            if frames_negros_seguidos % 20 == 0:
                print(f"黑帧持续 ({frames_negros_seguidos} 帧)...")
            time.sleep(0.2)
            continue
        else:
            frames_negros_seguidos = 0

        cv2.imshow(f"Cámara USB {INDICE_CAMARA} - 'q' salir", frame)

        ahora = time.time()
        if ahora - ultimo_tiempo > SEGUNDOS_ENTRE_ANALISIS:
            ultimo_tiempo = ahora
            try:
                resultados = alpr.predict(frame)
            except Exception as e:
                print(f"识别出错: {e}")
                resultados = []

            for placa, confianza in procesar_resultados(resultados):
                if placa != ultima_placa:
                    ultima_placa = placa

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


# ============================================================
# MODO IMAGEN (sin cambios)
# ============================================================
def modo_imagen(ruta_imagen):
    global FUENTE_ACTUAL
    FUENTE_ACTUAL = "imagen"

    if not os.path.exists(ruta_imagen):
        print(f"ERROR: 不存在图片 '{ruta_imagen}'。")
        return

    print(f"Procesando imagen: {ruta_imagen}")
    frame = cv2.imread(ruta_imagen)
    if frame is None:
        print("ERROR: 无法读取图片。")
        return

    try:
        resultados = alpr.predict(frame)
    except Exception as e:
        print(f"识别出错: {e}")
        return

    print(f"检测结果数: {len(resultados)}")
    encontrados = procesar_resultados(resultados)

    if not encontrados:
        print("没有检测到足够可信的车牌。")

    try:
        cv2.imshow("Imagen procesada", frame)
        print("按任意键关闭...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    except cv2.error:
        print("(无法打开窗口，但结果已写入 CSV)")


# ============================================================
# ENTRADA
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("  PROTOTIPO ALPR - COLEGIO")
    print("=" * 50)
    print("用法:")
    print("  python alpr_colegio.py                  -> cámara en vivo")
    print("  python alpr_colegio.py foto.jpg         -> procesar imagen")
    print("=" * 50)

    if len(sys.argv) > 1:
        modo_imagen(sys.argv[1])
    else:
        modo_camara()