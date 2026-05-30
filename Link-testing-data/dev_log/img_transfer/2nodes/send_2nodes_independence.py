import time
import signal
import atexit
import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple

import numpy as np
import serial
from PIL import Image


# =========================================================
# ========== 依赖 ==========
# pip install pyserial pillow numpy
# =========================================================


# =========================================================
# ========== 串口/设备配置 ==========
# 这是“2设备共发版”
# =========================================================

BAUD = 115200
TIMEOUT = 0

# 本程序实际运行的设备（2台）
DEVICE_CONFIGS = [
    {"logical_id": 1, "hw_id": 14149, "port": "COM14"},
    {"logical_id": 2, "hw_id": 12185, "port": "COM5"},
]

# 三设备原始逻辑ID全集
# 注意：EL 分配仍然按 1/2/3 三个 logical_id 做三分之一分配
ALL_LOGICAL_DEVICE_IDS = [1, 2, 3]

# =========================================================
# ========== AT 命令 ==========
# =========================================================

CMD_LOG_ON = "AT+CLOG=1"
CMD_QUEUE_CHECK = "AT+CMMQ?"
CMD_CLEAR = "AT+CCLR"
CMD_OVERFLOW_MODE = "AT+SVMD=1"

# =========================================================
# ========== AT 命令重试配置 ==========
# =========================================================

AT_RESPONSE_WAIT = 0.5
AT_EMPTY_RETRY_GAP = 0.3
INIT_RETRY_COUNT = 3
CMMQ_RETRY_COUNT = 5

# =========================================================
# ========== 重启识别配置 ==========
# =========================================================

# 检测到重启后，等待 7 秒再补发 AT+CLOG=1
REBOOT_RECOVER_DELAY = 5.0

# 防止短时间内重复触发
REBOOT_RECOVER_COOLDOWN = 1.0

# =========================================================
# ========== 图片/协议配置 ==========
# =========================================================

IMAGE_FILE = r"D:\tianqicmd\260309\mmexport1773062552088.jpg"

FRAME_SIZE_BYTES = 120
HEADER_SIZE_BYTES = 12
MAX_PAYLOAD_BYTES = FRAME_SIZE_BYTES - HEADER_SIZE_BYTES  # 108

L0_WIDTH = 48
L0_HEIGHT = 36

EL_WIDTH = 160
EL_HEIGHT = 120

TILE_WIDTH = 10
TILE_HEIGHT = 10

SEND_INTERVAL = 0.1
READ_CYCLE_SLEEP = 0.01

# 图片发送完后，每小时轮询一次当前程序内的设备
RESTART_POLL_INTERVAL = 3600.0

SAVE_DEBUG_IMAGES = True
DEBUG_OUTPUT_DIR = Path("./debug_output_2dev")

IMAGE_FINISH_RECORD_DIR = Path(".")
IMAGE_FINISH_LOG_FILE = IMAGE_FINISH_RECORD_DIR / "image_finish_log_2dev.txt"

DEVICE_LOG_ROOT_DIR = Path("./log_2dev")

PROTO_VERSION = 1
LAYER_L0 = 0
LAYER_EL = 1
FLAGS_DEFAULT = 0


# =========================================================
# ========== 数据结构 ==========
# =========================================================

RUN = True
SENDING_ACTIVE = False
CURRENT_IMAGE_ID = None
BASE_FRAMES_PER_DEVICE: Dict[int, List["EncodedFrame"]] = {}
CURRENT_CYCLE_FINISH_RECORDED = False
LAST_RESTART_POLL_TIME = 0.0


@dataclass
class EncodedFrame:
    layer_id: int
    fragment_index: int
    total_count: int
    payload: bytes
    aux: int = 0


@dataclass
class DeviceState:
    logical_id: int
    hw_id: int
    port: str
    ser: serial.Serial = None
    log_file = None
    frames: List[EncodedFrame] = field(default_factory=list)
    send_index: int = 0
    stats: Dict[str, int] = field(default_factory=lambda: {"total": 0, "success": 0})
    last_send_time: float = 0.0

    # 重启恢复相关
    last_reboot_recover_time: float = 0.0
    pending_reboot_recover: bool = False
    reboot_detect_time: float = 0.0


DEVICE_STATES: List[DeviceState] = []


# =========================================================
# ========== 通用工具 ==========
# =========================================================

def get_timestamp() -> str:
    now = datetime.now()
    return f"[{now.strftime('%H:%M:%S.%f')[:-3]}]"


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def generate_image_id() -> int:
    return int(time.time() * 1000) & 0xFFFF


def image_id_to_hex(image_id: int) -> str:
    return f"{image_id & 0xFFFF:04X}"


def record_image_finish_time(image_id: int):
    ensure_dir(IMAGE_FINISH_RECORD_DIR)
    finish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{image_id_to_hex(image_id)} {finish_time}\n"
    with open(IMAGE_FINISH_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    print(f"{get_timestamp()} 已追加图片完成时间到总日志: {line.strip()}")


# =========================================================
# ========== 日志 ==========
# =========================================================

def get_device_log_dir(device: DeviceState) -> Path:
    device_dir = DEVICE_LOG_ROOT_DIR / str(device.hw_id)
    ensure_dir(device_dir)
    return device_dir


def get_log_filename(device: DeviceState) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    filename = f"{ts}_dev{device.logical_id}_{device.port}.TXT"
    return get_device_log_dir(device) / filename


def write_raw_log(device: DeviceState, data: bytes):
    if device.log_file and data:
        timestamp = get_timestamp().encode()
        device.log_file.write(timestamp + data)
        device.log_file.flush()


# =========================================================
# ========== 串口函数 ==========
# =========================================================

def send_at_command_once(device: DeviceState, command: str, wait_time: float = AT_RESPONSE_WAIT) -> str:
    send_data = f"{command}\r\n".encode()
    write_raw_log(device, "发→◇".encode("utf-8") + send_data)
    print(f"{get_timestamp()} [DEV{device.logical_id} {device.port}] 发→◇{command}")
    print("□")

    device.ser.reset_input_buffer()
    device.ser.write(send_data)

    time.sleep(wait_time)
    response = b""
    while device.ser.in_waiting > 0:
        chunk = device.ser.read(device.ser.in_waiting)
        response += chunk
        time.sleep(0.01)

    if response:
        write_raw_log(device, "收←◆\n".encode("utf-8") + response)
        text = response.decode("ascii", errors="ignore")
        print(f"{get_timestamp()} [DEV{device.logical_id} {device.port}] 收←◆")
        print(text.replace("\r", ""))
        return text

    print(f"{get_timestamp()} [DEV{device.logical_id} {device.port}] ⚠️ 指令无响应: {command}")
    return ""


def send_at_command_with_retry(
    device: DeviceState,
    command: str,
    retry_count: int,
    retry_gap: float = AT_EMPTY_RETRY_GAP,
    wait_time: float = AT_RESPONSE_WAIT,
) -> str:
    total_attempts = 1 + max(0, retry_count)

    for attempt in range(1, total_attempts + 1):
        resp = send_at_command_once(device, command, wait_time=wait_time)
        if resp.strip():
            return resp

        if attempt < total_attempts:
            print(
                f"{get_timestamp()} [DEV{device.logical_id} {device.port}] "
                f"⚠️ 第 {attempt}/{total_attempts} 次无响应，准备重发: {command}"
            )
            time.sleep(retry_gap)

    print(
        f"{get_timestamp()} [DEV{device.logical_id} {device.port}] "
        f"✗ 指令连续无响应，已放弃: {command}"
    )
    return ""


def detect_reboot_and_schedule_log_reenable(device: DeviceState, text: str):
    """
    识别到任意一条重启签名，就登记重启恢复任务：
    +CGMI:GDGK_Ltd
    +CGMM:TQZD-10

    注意：不是立刻发，而是等待 REBOOT_RECOVER_DELAY 秒后再发 AT+CLOG=1
    """
    if not text:
        return

    reboot_detected = (
        "+CGMI:GDGK_Ltd" in text
        or "+CGMM:TQZD-10" in text
    )

    if not reboot_detected:
        return

    now = time.time()

    # 已经在等待补发，不重复登记
    if device.pending_reboot_recover:
        print(
            f"{get_timestamp()} [DEV{device.logical_id} {device.port}] "
            f"检测到重启签名，但已在等待补发 {CMD_LOG_ON}"
        )
        return

    # 冷却期内避免重复触发
    if (now - device.last_reboot_recover_time) < REBOOT_RECOVER_COOLDOWN:
        print(
            f"{get_timestamp()} [DEV{device.logical_id} {device.port}] "
            f"检测到重启签名，但仍在冷却期内，跳过登记"
        )
        return

    device.pending_reboot_recover = True
    device.reboot_detect_time = now

    print(
        f"{get_timestamp()} [DEV{device.logical_id} {device.port}] "
        f"检测到设备重启签名，已登记，{REBOOT_RECOVER_DELAY:.0f}s 后补发 {CMD_LOG_ON}"
    )


def process_pending_reboot_recover(device: DeviceState):
    """
    到时间后再补发 AT+CLOG=1
    """
    if not device.pending_reboot_recover:
        return

    now = time.time()
    if (now - device.reboot_detect_time) < REBOOT_RECOVER_DELAY:
        return

    print(
        f"{get_timestamp()} [DEV{device.logical_id} {device.port}] "
        f"等待 {REBOOT_RECOVER_DELAY:.0f}s 完成，补发 {CMD_LOG_ON}"
    )

    device.pending_reboot_recover = False
    device.last_reboot_recover_time = now

    resp = send_at_command_with_retry(
        device,
        CMD_LOG_ON,
        retry_count=INIT_RETRY_COUNT
    )

    if "OK" in resp:
        print(f"{get_timestamp()} [DEV{device.logical_id}] ✓ 重启后日志已重新启用")
    else:
        print(f"{get_timestamp()} [DEV{device.logical_id}] ✗ 重启后日志重新启用失败")


def read_monitor_data(device: DeviceState):
    if device.ser.in_waiting > 0:
        data = device.ser.read(device.ser.in_waiting)
        write_raw_log(device, "收←◆\n".encode("utf-8") + data)
        text = data.decode("ascii", errors="ignore")
        if text:
            print(f"{get_timestamp()} [DEV{device.logical_id} {device.port}] 收←◆")
            print(text.replace("\r", ""))

            detect_reboot_and_schedule_log_reenable(device, text)

        return True
    return False


def initialize_device(device: DeviceState):
    print(f"{get_timestamp()} [DEV{device.logical_id} {device.port}] 设备初始化开始")

    resp = send_at_command_with_retry(device, CMD_CLEAR, retry_count=INIT_RETRY_COUNT)
    if "+CCLR:OK" in resp and "OK" in resp:
        print(f"{get_timestamp()} [DEV{device.logical_id}] ✓ 缓冲区清空成功")
    else:
        print(f"{get_timestamp()} [DEV{device.logical_id}] ✗ 缓冲区清空失败")
    time.sleep(1)

    resp = send_at_command_with_retry(device, CMD_LOG_ON, retry_count=INIT_RETRY_COUNT)
    if "OK" in resp:
        print(f"{get_timestamp()} [DEV{device.logical_id}] ✓ 设备日志已启用")
    else:
        print(f"{get_timestamp()} [DEV{device.logical_id}] ✗ 设备日志启用失败")
    time.sleep(1)

    resp = send_at_command_with_retry(device, CMD_OVERFLOW_MODE, retry_count=INIT_RETRY_COUNT)
    if "OK" in resp:
        print(f"{get_timestamp()} [DEV{device.logical_id}] ✓ 溢出模式已启用")
    else:
        print(f"{get_timestamp()} [DEV{device.logical_id}] ✗ 溢出模式启用失败")
    time.sleep(1)


def check_queue_status(device: DeviceState) -> int:
    resp = send_at_command_with_retry(device, CMD_QUEUE_CHECK, retry_count=CMMQ_RETRY_COUNT)

    if not resp.strip():
        print(f"{get_timestamp()} [DEV{device.logical_id}] ✗ CMMQ 查询无响应")
        return -1

    if "+CMMQ:" in resp:
        try:
            start = resp.find("+CMMQ:") + 6
            end = start
            while end < len(resp) and resp[end].isdigit():
                end += 1
            if end > start:
                count = int(resp[start:end])
                if count > 0:
                    print(f"{get_timestamp()} [DEV{device.logical_id}] ⚠️ 队列中有 {count} 条待处理数据")
                else:
                    print(f"{get_timestamp()} [DEV{device.logical_id}] ✓ 队列为空")
                return count
        except ValueError:
            pass

    print(f"{get_timestamp()} [DEV{device.logical_id}] ✗ CMMQ 返回格式异常: {resp!r}")
    return -1


# =========================================================
# ========== 协议打包 ==========
# =========================================================

HEADER_STRUCT = struct.Struct(">BBHBBHHBB")


def pack_frame_bytes(
    image_id: int,
    device_id: int,
    layer_id: int,
    fragment_index: int,
    total_count: int,
    payload: bytes,
    aux: int = 0,
    flags: int = FLAGS_DEFAULT,
) -> bytes:
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise ValueError(f"payload 过长: {len(payload)} > {MAX_PAYLOAD_BYTES}")

    header = HEADER_STRUCT.pack(
        PROTO_VERSION,
        flags,
        image_id & 0xFFFF,
        device_id & 0xFF,
        layer_id & 0xFF,
        fragment_index & 0xFFFF,
        total_count & 0xFFFF,
        len(payload) & 0xFF,
        aux & 0xFF,
    )

    if len(header) != HEADER_SIZE_BYTES:
        raise RuntimeError("协议头长度不是 12 字节，请检查 HEADER_STRUCT")

    return header + payload


def make_send_command(frame_bytes: bytes) -> str:
    hex_str = frame_bytes.hex().upper()
    length_bytes = len(frame_bytes)
    return f"AT+SEND={length_bytes},{hex_str}"


# =========================================================
# ========== 图像编码 ==========
# =========================================================

def load_image(path: str) -> Image.Image:
    img_path = Path(path)
    if not img_path.is_file():
        raise FileNotFoundError(f"图片文件不存在: {img_path}")
    return Image.open(img_path).convert("RGB")


def image_to_gray_array(img: Image.Image, width: int, height: int) -> np.ndarray:
    gray = img.convert("L").resize((width, height), Image.BILINEAR)
    return np.array(gray, dtype=np.uint8)


def upsample_gray(arr: np.ndarray, width: int, height: int) -> np.ndarray:
    img = Image.fromarray(arr, mode="L")
    up = img.resize((width, height), Image.BILINEAR)
    return np.array(up, dtype=np.uint8)


def build_l0_payloads(l0_arr: np.ndarray) -> List[bytes]:
    raw = l0_arr.tobytes()
    if len(raw) != L0_WIDTH * L0_HEIGHT:
        raise ValueError("L0 数据尺寸不对")

    chunks = [raw[i:i + MAX_PAYLOAD_BYTES] for i in range(0, len(raw), MAX_PAYLOAD_BYTES)]

    if len(chunks) != 16:
        raise RuntimeError(f"L0 分片数不是 16，而是 {len(chunks)}，请检查参数")

    return chunks


def compute_el_tiles(g_target_arr: np.ndarray) -> List[Tuple[int, bytes, int]]:
    h, w = g_target_arr.shape
    result = []
    tile_id = 0

    gx = np.zeros_like(g_target_arr, dtype=np.int16)
    gy = np.zeros_like(g_target_arr, dtype=np.int16)
    gx[:, 1:] = np.abs(g_target_arr[:, 1:].astype(np.int16) - g_target_arr[:, :-1].astype(np.int16))
    gy[1:, :] = np.abs(g_target_arr[1:, :].astype(np.int16) - g_target_arr[:-1, :].astype(np.int16))
    energy_map = gx + gy

    for ty in range(0, h, TILE_HEIGHT):
        for tx in range(0, w, TILE_WIDTH):
            tile = g_target_arr[ty:ty + TILE_HEIGHT, tx:tx + TILE_WIDTH]
            energy_tile = energy_map[ty:ty + TILE_HEIGHT, tx:tx + TILE_WIDTH]

            if tile.shape != (TILE_HEIGHT, TILE_WIDTH):
                raise ValueError("tile 尺寸不完整，请检查 EL 尺寸与 tile 尺寸是否整除")

            payload = tile.tobytes()
            score = int(energy_tile.sum())
            result.append((tile_id, payload, score))
            tile_id += 1

    result.sort(key=lambda x: x[2], reverse=True)
    return result


def distribute_el_tiles_round_robin(
    scored_tiles: List[Tuple[int, bytes, int]],
    logical_device_ids: List[int],
) -> Dict[int, List[Tuple[int, bytes, int]]]:
    out = {did: [] for did in logical_device_ids}
    for i, item in enumerate(scored_tiles):
        did = logical_device_ids[i % len(logical_device_ids)]
        out[did].append(item)
    return out


def save_debug_artifacts(
    src_img: Image.Image,
    l0_arr: np.ndarray,
    g_target_arr: np.ndarray,
    el_tiles_sorted: List[Tuple[int, bytes, int]],
):
    if not SAVE_DEBUG_IMAGES:
        return

    ensure_dir(DEBUG_OUTPUT_DIR)

    src_img.save(DEBUG_OUTPUT_DIR / "src_original.png")
    Image.fromarray(l0_arr, mode="L").save(DEBUG_OUTPUT_DIR / "l0_48x36.png")
    Image.fromarray(upsample_gray(l0_arr, EL_WIDTH, EL_HEIGHT), mode="L").save(
        DEBUG_OUTPUT_DIR / f"l0_upsampled_{EL_WIDTH}x{EL_HEIGHT}.png"
    )
    Image.fromarray(g_target_arr, mode="L").save(
        DEBUG_OUTPUT_DIR / f"g_target_{EL_WIDTH}x{EL_HEIGHT}.png"
    )

    order_vis = np.zeros((EL_HEIGHT, EL_WIDTH), dtype=np.uint8)
    total = max(1, len(el_tiles_sorted) - 1)

    tile_rank = {}
    for rank, (tile_id, _, _) in enumerate(el_tiles_sorted):
        tile_rank[tile_id] = rank

    idx = 0
    for ty in range(0, EL_HEIGHT, TILE_HEIGHT):
        for tx in range(0, EL_WIDTH, TILE_WIDTH):
            rank = tile_rank[idx]
            val = int(rank * 255 / total)
            order_vis[ty:ty + TILE_HEIGHT, tx:tx + TILE_WIDTH] = val
            idx += 1

    Image.fromarray(order_vis, mode="L").save(
        DEBUG_OUTPUT_DIR / f"el_tile_priority_map_{EL_WIDTH}x{EL_HEIGHT}.png"
    )

    with open(DEBUG_OUTPUT_DIR / "tile_scores.txt", "w", encoding="utf-8") as f:
        for tile_id, _, score in el_tiles_sorted:
            f.write(f"tile_id={tile_id}, score={score}\n")


def encode_image_for_devices(image_file: str) -> Dict[int, List[EncodedFrame]]:
    """
    两设备版新规则：
    - 两台设备合计发送完整 240 帧
    - L0: 48 帧（16帧基础层复制3份），平均给两台 => 每台24帧
    - EL: 192 帧，平均给两台 => 每台96帧
    """
    img = load_image(image_file)
    print(f"{get_timestamp()} 图片文件: {image_file}")
    print(f"{get_timestamp()} 原始尺寸: {img.size[0]}x{img.size[1]}")

    l0_arr = image_to_gray_array(img, L0_WIDTH, L0_HEIGHT)
    g_target_arr = image_to_gray_array(img, EL_WIDTH, EL_HEIGHT)

    # 原始 16 个 L0 分片
    l0_payloads_base = build_l0_payloads(l0_arr)
    print(f"{get_timestamp()} L0原始: {L0_WIDTH}x{L0_HEIGHT}, 共 {len(l0_payloads_base)} 帧")

    # 复制 3 份 => 48 帧
    l0_payloads_full = l0_payloads_base * 3
    total_l0_full = len(l0_payloads_full)
    print(f"{get_timestamp()} 两设备版 L0扩展后: 共 {total_l0_full} 帧")

    if total_l0_full != 48:
        raise RuntimeError(f"L0 总帧数异常: {total_l0_full} != 48")

    # 全部 EL tile，共 192 个
    el_tiles_sorted = compute_el_tiles(g_target_arr)
    total_tiles = len(el_tiles_sorted)
    expected_tiles = (EL_WIDTH // TILE_WIDTH) * (EL_HEIGHT // TILE_HEIGHT)

    print(
        f"{get_timestamp()} EL: {EL_WIDTH}x{EL_HEIGHT}, "
        f"tile={TILE_WIDTH}x{TILE_HEIGHT}, 共 {total_tiles} 个 tile"
    )

    if total_tiles != expected_tiles:
        raise RuntimeError(f"EL tile 数异常: 实际 {total_tiles}, 预期 {expected_tiles}")

    if total_tiles != 192:
        raise RuntimeError(f"EL 总帧数异常: {total_tiles} != 192")

    save_debug_artifacts(img, l0_arr, g_target_arr, el_tiles_sorted)

    running_ids = [cfg["logical_id"] for cfg in DEVICE_CONFIGS]
    if len(running_ids) != 2:
        raise RuntimeError("两设备版 DEVICE_CONFIGS 必须只有 2 台设备")

    out: Dict[int, List[EncodedFrame]] = {did: [] for did in running_ids}

    # -----------------------------------------------------
    # 48 个 L0 平均给两台 => 每台 24
    # -----------------------------------------------------
    l0_alloc = {did: [] for did in running_ids}
    for i, payload in enumerate(l0_payloads_full):
        did = running_ids[i % 2]
        l0_alloc[did].append(payload)

    for did in running_ids:
        my_l0 = l0_alloc[did]
        total_l0 = len(my_l0)

        if total_l0 != 24:
            raise RuntimeError(f"DEV{did} 的 L0 数量异常: {total_l0} != 24")

        for i, payload in enumerate(my_l0):
            out[did].append(
                EncodedFrame(
                    layer_id=LAYER_L0,
                    fragment_index=i,
                    total_count=total_l0,
                    payload=payload,
                    aux=0,
                )
            )

    # -----------------------------------------------------
    # 192 个 EL 平均给两台 => 每台 96
    # -----------------------------------------------------
    el_alloc = {did: [] for did in running_ids}
    for i, item in enumerate(el_tiles_sorted):
        did = running_ids[i % 2]
        el_alloc[did].append(item)

    for did in running_ids:
        my_tiles = el_alloc[did]
        total_el = len(my_tiles)

        if total_el != 96:
            raise RuntimeError(f"DEV{did} 的 EL 数量异常: {total_el} != 96")

        print(f"{get_timestamp()} DEV{did} 分配到 EL tile 数: {total_el}")

        for i, (tile_id, tile_payload, _score) in enumerate(my_tiles):
            expected_payload_len = TILE_WIDTH * TILE_HEIGHT
            if len(tile_payload) != expected_payload_len:
                raise RuntimeError(
                    f"EL tile payload 长度不对: {len(tile_payload)} != {expected_payload_len}"
                )

            if len(tile_payload) > MAX_PAYLOAD_BYTES:
                raise RuntimeError(
                    f"EL tile 太大，无法放进单帧: {len(tile_payload)} > {MAX_PAYLOAD_BYTES}"
                )

            out[did].append(
                EncodedFrame(
                    layer_id=LAYER_EL,
                    fragment_index=i,
                    total_count=total_el,
                    payload=tile_payload,
                    aux=tile_id,
                )
            )

    for did in running_ids:
        l0_count = sum(1 for x in out[did] if x.layer_id == LAYER_L0)
        el_count = sum(1 for x in out[did] if x.layer_id == LAYER_EL)
        print(
            f"{get_timestamp()} DEV{did} 单轮待发送总数: {len(out[did])} 帧 "
            f"(L0={l0_count}, EL={el_count})"
        )

    return out


# =========================================================
# ========== 轮次控制 ==========
# =========================================================

def start_new_image_cycle():
    global CURRENT_IMAGE_ID, SENDING_ACTIVE, CURRENT_CYCLE_FINISH_RECORDED, LAST_RESTART_POLL_TIME

    CURRENT_IMAGE_ID = generate_image_id()
    CURRENT_CYCLE_FINISH_RECORDED = False
    SENDING_ACTIVE = True

    now = time.time()
    for dev in DEVICE_STATES:
        dev.frames = BASE_FRAMES_PER_DEVICE[dev.logical_id]
        dev.send_index = 0
        dev.last_send_time = now - SEND_INTERVAL

    print()
    print("====================================================")
    print(f"{get_timestamp()} 启动新一轮图片发送（2设备共发版）")
    print(f"{get_timestamp()} 当前图片ID: {image_id_to_hex(CURRENT_IMAGE_ID)}")
    print("====================================================")
    print()


def finish_current_image_cycle():
    global SENDING_ACTIVE, CURRENT_CYCLE_FINISH_RECORDED, LAST_RESTART_POLL_TIME

    if not CURRENT_CYCLE_FINISH_RECORDED:
        print(f"{get_timestamp()} 当前程序内所有设备帧已发送完成")
        record_image_finish_time(CURRENT_IMAGE_ID)
        CURRENT_CYCLE_FINISH_RECORDED = True

    SENDING_ACTIVE = False
    LAST_RESTART_POLL_TIME = time.time()


def all_devices_finished() -> bool:
    for dev in DEVICE_STATES:
        if dev.send_index < len(dev.frames):
            return False
    return True


def try_restart_when_all_queues_empty():
    """
    2设备共发版规则：
    只要两个设备里有一个还有待发数据，就不启动下一轮；
    必须两个都为 0，才开始下一轮。
    """
    print(f"{get_timestamp()} 开始执行双设备队列检查（AT+CMMQ?）...")

    queue_counts = []
    for dev in DEVICE_STATES:
        count = check_queue_status(dev)
        queue_counts.append(count)

    if all(count == 0 for count in queue_counts):
        print(f"{get_timestamp()} 两个设备都没有待发数据，启动下一轮图片发送")
        start_new_image_cycle()
    else:
        print(f"{get_timestamp()} 至少一个设备仍有待发数据，暂不启动下一轮")
        print(f"{get_timestamp()} CMMQ结果: {queue_counts}")


# =========================================================
# ========== 发送逻辑 ==========
# =========================================================

def send_next_frame(device: DeviceState) -> bool:
    if device.send_index >= len(device.frames):
        return False

    frame = device.frames[device.send_index]
    frame_bytes = pack_frame_bytes(
        image_id=CURRENT_IMAGE_ID,
        device_id=device.logical_id,
        layer_id=frame.layer_id,
        fragment_index=frame.fragment_index,
        total_count=frame.total_count,
        payload=frame.payload,
        aux=frame.aux,
    )

    if len(frame_bytes) > FRAME_SIZE_BYTES:
        raise RuntimeError(f"帧长度超过 120B: {len(frame_bytes)}")

    layer_name = "L0" if frame.layer_id == LAYER_L0 else "EL"

    print(
        f"{get_timestamp()} [DEV{device.logical_id} {device.port}] "
        f"=== 发送 {layer_name} 帧 {device.send_index + 1}/{len(device.frames)} "
        f"(img={image_id_to_hex(CURRENT_IMAGE_ID)}, layer_idx={frame.fragment_index}/{frame.total_count - 1}, aux={frame.aux}) ==="
    )

    command = make_send_command(frame_bytes)
    resp = send_at_command_once(device, command)

    device.stats["total"] += 1
    if "OK" in resp or "+FrameNo" in resp:
        device.stats["success"] += 1
        print(f"{get_timestamp()} [DEV{device.logical_id}] ✓ 发送成功")
    else:
        print(f"{get_timestamp()} [DEV{device.logical_id}] ✗ 发送失败")

    device.send_index += 1
    device.last_send_time = time.time()
    return True


def main_loop():
    global LAST_RESTART_POLL_TIME

    print(f"{get_timestamp()} 进入图片循环发送模式（2设备共发版）")
    print(f"{get_timestamp()} 每个设备独立发送间隔: {SEND_INTERVAL} 秒")
    print(f"{get_timestamp()} 图片发送完毕后，每 {int(RESTART_POLL_INTERVAL)} 秒检查一次当前这2个设备的 CMMQ")
    print()

    LAST_RESTART_POLL_TIME = time.time()
    start_new_image_cycle()

    while RUN:
        now = time.time()

        for dev in DEVICE_STATES:
            if dev.ser and dev.ser.is_open:
                read_monitor_data(dev)
                process_pending_reboot_recover(dev)

        if SENDING_ACTIVE:
            for dev in DEVICE_STATES:
                if dev.send_index < len(dev.frames):
                    if (now - dev.last_send_time) >= SEND_INTERVAL:
                        send_next_frame(dev)

            if all_devices_finished():
                finish_current_image_cycle()
        else:
            if (now - LAST_RESTART_POLL_TIME) >= RESTART_POLL_INTERVAL:
                try_restart_when_all_queues_empty()
                LAST_RESTART_POLL_TIME = time.time()

        time.sleep(READ_CYCLE_SLEEP)


# =========================================================
# ========== 初始化与清理 ==========
# =========================================================

def init_system():
    global DEVICE_STATES, BASE_FRAMES_PER_DEVICE

    print("LoRa 2设备共发图片循环发送程序")
    print("====================================")
    print(f"图片文件: {IMAGE_FILE}")
    print("EL 分片仍按 3 设备逻辑分成三份，本程序只发送其中 2 台设备各自那一份")
    print(f"帧长度: {FRAME_SIZE_BYTES} 字节（头 {HEADER_SIZE_BYTES} + 载荷最多 {MAX_PAYLOAD_BYTES}）")
    print("图片发送完毕后，检查这2个设备的 CMMQ?；只要有一个非0，就不开始下一轮")
    print("检测到任意一条重启签名后，等待7秒，再补发 AT+CLOG=1")
    print()

    ensure_dir(DEVICE_LOG_ROOT_DIR)
    BASE_FRAMES_PER_DEVICE = encode_image_for_devices(IMAGE_FILE)

    DEVICE_STATES = []

    for cfg in DEVICE_CONFIGS:
        dev = DeviceState(
            logical_id=cfg["logical_id"],
            hw_id=cfg["hw_id"],
            port=cfg["port"],
        )

        log_filename = get_log_filename(dev)
        dev.log_file = open(log_filename, "ab", buffering=0)
        print(f"{get_timestamp()} [DEV{dev.logical_id}] 日志文件: {log_filename}")

        dev.ser = serial.Serial(dev.port, BAUD, timeout=TIMEOUT)
        print(f"{get_timestamp()} [DEV{dev.logical_id}] ✓ 串口已连接: {dev.port}")

        initialize_device(dev)

        dev.frames = BASE_FRAMES_PER_DEVICE[dev.logical_id]
        l0_count = sum(1 for x in dev.frames if x.layer_id == LAYER_L0)
        el_count = sum(1 for x in dev.frames if x.layer_id == LAYER_EL)
        print(f"{get_timestamp()} [DEV{dev.logical_id}] 单轮待发送: 总计 {len(dev.frames)} 帧, L0={l0_count}, EL={el_count}")

        DEVICE_STATES.append(dev)


def cleanup():
    global RUN
    RUN = False

    print(f"\n{get_timestamp()} === 执行系统清理 ===")

    for dev in DEVICE_STATES:
        try:
            if dev.ser and dev.ser.is_open:
                dev.ser.close()
                print(f"{get_timestamp()} [DEV{dev.logical_id}] ✓ 串口已关闭")
        except Exception as e:
            print(f"{get_timestamp()} [DEV{dev.logical_id}] 关闭串口异常: {e}")

        try:
            if dev.log_file:
                dev.log_file.close()
                print(f"{get_timestamp()} [DEV{dev.logical_id}] ✓ 日志文件已关闭")
        except Exception as e:
            print(f"{get_timestamp()} [DEV{dev.logical_id}] 关闭日志异常: {e}")

        total = dev.stats["total"]
        succ = dev.stats["success"]
        fail = total - succ
        print(f"{get_timestamp()} [DEV{dev.logical_id}] 发送统计 - 总计:{total} 成功:{succ} 失败:{fail}")

    print(f"{get_timestamp()} 程序退出")


def signal_handler(signum, frame):
    global RUN
    print(f"\n\n{get_timestamp()} 收到退出信号，正在清理...")
    RUN = False


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    atexit.register(cleanup)

    init_system()
    main_loop()