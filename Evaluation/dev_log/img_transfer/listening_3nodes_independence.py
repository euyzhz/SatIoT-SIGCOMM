import atexit
import signal
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List

import serial


BAUD = 115200
TIMEOUT = 0
READ_CYCLE_SLEEP = 0.01

DEVICE_CONFIGS = [
    {"logical_id": 1, "hw_id": 12171, "port": "COM9"},
    {"logical_id": 2, "hw_id": 12174, "port": "COM6"},
    {"logical_id": 3, "hw_id": 12185, "port": "COM5"},
]

RUN = True


@dataclass
class DeviceState:
    logical_id: int
    hw_id: int
    port: str
    ser: serial.Serial = None
    log_file = None


DEVICE_STATES: List[DeviceState] = []


def get_timestamp() -> str:
    now = datetime.now()
    return f"[{now.strftime('%H:%M:%S.%f')[:-3]}]"


def get_log_filename(device: DeviceState) -> str:
    ts = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    return f"{ts}_dev{device.logical_id}_{device.port}.TXT"


def write_raw_log(device: DeviceState, data: bytes):
    if device.log_file and data:
        timestamp = get_timestamp().encode()
        device.log_file.write(timestamp + data)
        device.log_file.flush()


def read_monitor_data(device: DeviceState):
    if device.ser.in_waiting > 0:
        data = device.ser.read(device.ser.in_waiting)
        write_raw_log(device, b"recv:\n" + data)
        text = data.decode("ascii", errors="ignore")
        if text:
            print(f"{get_timestamp()} [DEV{device.logical_id} {device.port}] recv:")
            print(text.replace("\r", ""))
        return True
    return False


def init_listeners():
    global DEVICE_STATES

    print("LoRa three-node listen-only monitor")
    print("====================================")
    print("Mode: listen only")
    print("No queue clear, no device init, no send")
    print("Press Ctrl+C to exit")
    print()

    DEVICE_STATES = []

    for cfg in DEVICE_CONFIGS:
        dev = DeviceState(
            logical_id=cfg["logical_id"],
            hw_id=cfg["hw_id"],
            port=cfg["port"],
        )

        log_filename = get_log_filename(dev)
        dev.log_file = open(log_filename, "ab", buffering=0)
        print(f"{get_timestamp()} [DEV{dev.logical_id}] log file: {log_filename}")

        dev.ser = serial.Serial(dev.port, BAUD, timeout=TIMEOUT)
        print(f"{get_timestamp()} [DEV{dev.logical_id}] connected: {dev.port}")

        DEVICE_STATES.append(dev)


def main_loop():
    print(f"{get_timestamp()} Listening on all configured serial ports...")
    while RUN:
        for dev in DEVICE_STATES:
            if dev.ser and dev.ser.is_open:
                read_monitor_data(dev)
        time.sleep(READ_CYCLE_SLEEP)


def cleanup():
    global RUN
    RUN = False

    print(f"\n{get_timestamp()} === cleanup ===")

    for dev in DEVICE_STATES:
        try:
            if dev.ser and dev.ser.is_open:
                dev.ser.close()
                print(f"{get_timestamp()} [DEV{dev.logical_id}] serial closed")
        except Exception as e:
            print(f"{get_timestamp()} [DEV{dev.logical_id}] serial close error: {e}")

        try:
            if dev.log_file:
                dev.log_file.close()
                print(f"{get_timestamp()} [DEV{dev.logical_id}] log file closed")
        except Exception as e:
            print(f"{get_timestamp()} [DEV{dev.logical_id}] log close error: {e}")

    print(f"{get_timestamp()} Program exit")


def signal_handler(signum, frame):
    global RUN
    print(f"\n\n{get_timestamp()} Exit signal received, shutting down...")
    RUN = False


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    atexit.register(cleanup)

    init_listeners()
    main_loop()
