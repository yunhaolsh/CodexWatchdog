#!/usr/bin/env python3
"""Prepare a private firmware copy without editing the original StackChan demo."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def replace_once(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise RuntimeError(f'Unsupported source layout: {path}: expected one patch anchor')
    path.write_text(text.replace(old, new, 1))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path('/home/yunhao/github/stackchan/StackChan/firmware'))
    parser.add_argument('--output', type=Path, default=ROOT.parent / '.run/watchdog-firmware')
    args = parser.parse_args()
    source, target = args.source.resolve(), args.output.resolve()
    if target.exists():
        raise SystemExit(f'Output already exists; choose a fresh --output: {target}')
    if source == target or source in target.parents:
        raise SystemExit('Output must be outside the source demo')
    config = (source / 'sdkconfig').read_text()
    for required in ('CONFIG_SPIRAM_MODE_QUAD=y', 'CONFIG_ESPTOOLPY_FLASHSIZE_16MB=y',
                     'CONFIG_BOARD_TYPE_M5STACK_STACK_CHAN=y'):
        if required not in config.splitlines():
            raise SystemExit(f'Unexpected board configuration: missing {required}')
    commits = {}
    for name, path in [('stackchan', source.parent), ('xiaozhi', source/'xiaozhi-esp32')]:
        commits[name] = subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'], text=True).strip()
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('.git','build','__pycache__','.venv','.cache','sdkconfig.old'))
    shutil.copytree(ROOT/'overlay', target, dirs_exist_ok=True)
    replace_once(target/'main/hal/hal.h', '    std::string content;\n};',
                 '    std::string content;\n    std::string watchdog_json;\n};')
    replace_once(target/'main/hal/hal.h', '    uitk::Signal<const WsTextMessage_t&> onWsTextMessage;',
                 '    uitk::Signal<const WsTextMessage_t&> onWsTextMessage;\n    uitk::Signal<> onWsHeartbeat;')
    replace_once(target/'main/hal/hal_ws_avatar.cpp', '                    sendPacket(DataType::HeartbeatPong, nullptr, 0);',
                 '                    GetHAL().onWsHeartbeat.emit();\n                    sendPacket(DataType::HeartbeatPong, nullptr, 0);')
    replace_once(target/'main/hal/hal_ws_avatar.cpp', '                        WsTextMessage_t text_msg;',
                 '''                        WsTextMessage_t text_msg;
                        if (doc["watchdog"].is<ArduinoJson::JsonObject>()) {
                            ArduinoJson::serializeJson(doc["watchdog"], text_msg.watchdog_json);
                        }''')
    (target/'watchdog-source.json').write_text(json.dumps(commits, indent=2)+'\n')
    print(f'Prepared Watchdog firmware in {target}')
    print('Source revisions:',json.dumps(commits))

if __name__ == '__main__':
    main()
