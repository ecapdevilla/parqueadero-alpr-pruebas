import cv2

print("Probando camaras...")

for i in range(10):
    cap = cv2.VideoCapture(i)
    opened = cap.isOpened()
    print(f"Indice {i}: opened={opened}")
    if opened:
        ret, frame = cap.read()
        if ret:
            mean_val = frame.mean()
            print(f"  Frame leido OK, shape={frame.shape}, mean={mean_val}")
        else:
            print("  No se pudo leer frame")
    cap.release()
