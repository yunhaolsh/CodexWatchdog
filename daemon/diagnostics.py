"""Separate Codex execution evidence from device connection evidence."""
from pathlib import Path


def diagnose(health: dict, status: dict) -> dict:
    connected = health.get("device_connected") is True
    return {
        "daemon": health,
        "task": {key: status.get(key) for key in ("task_id", "state", "phase")},
        "device_transport": "connected" if connected else "disconnected",
        "screen": "unverified",
        "explanation": (
            "设备传输已连接；屏幕显示仍需实机确认。"
            if connected else
            "设备未连接，任务 success 不代表消息已送达屏幕。请先确认固件协议和服务器地址。"
        ),
        "serial_candidates": [
            {"usb_id": path.name, "port": str(path.resolve())}
            for path in sorted(Path("/dev/serial/by-id").glob("usb-Espressif*"))
        ],
        "serial_note": "USB 枚举不等于固件识别；此命令不打开串口或复位设备。",
    }
