import subprocess
import cv2

# 1. Verificar si la app nativa de cámara de Windows abre
print("1. Procesos usando cámara...")
subprocess.run("tasklist /fi \"имя процесса eq Zoom.exe\" /fo LIST", shell=True)
subprocess.run("tasklist /fi \"имя процесса eq Teams.exe\" /fo LIST", shell=True)
subprocess.run("tasklist /fi \"имена процессов eq OBS.exe\" /fo LIST", shell=True)
subprocess.run("tasklist /fi \"имена процессов eq Camera.exe\" /fo LIST", shell=True)
subprocess.run("tasklist /fi \"имена процессов eq obsidian.exe\" /fo LIST", shell=True)

# 2. Probar con GStreamer backend
print("2. Probando backend GStreamer...")
for i in [0, 1]:
    cap = cv2.VideoCapture(i, cv2.CAP_GSTREAMER)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f"GStreamer indice {i}: OK, mean={frame.mean()}")
        else:
            print(f"GStreamer indice {i}: No leyó frame")
    cap.release()

# 3. Probar con V4L2 backend (Linux) - no aplica, skip
# 4. Probar con backend MS MJPG custom
print("3. Probando con MJPG fourcc...")
for i in [0, 1]:
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        ret, frame = cap.read()
        if ret:
            print(f"MJPG indice {i}: OK, mean={frame.mean()}")
        else:
            print(f"MJPG indice {i}: No leyó frame")
    cap.release()

print("Diagnostico completado")
