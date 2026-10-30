from pyusbcameraindex import enumerate_usb_video_devices_windows

devices = enumerate_usb_video_devices_windows()
for device in devices:
    print(f"Índice {device.index}: {device.name} (VID: {device.vid})")