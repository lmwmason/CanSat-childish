"""Read-only static evidence from the user-supplied reference ZIP; never runs EXE."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile


def inspect(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        exe = archive.read("Cansat_Gs.exe")
    pe = struct.unpack_from("<I", exe, 0x3C)[0]
    if exe[:2] != b"MZ" or exe[pe:pe+4] != b"PE\0\0":
        raise ValueError("Not a PE image")
    count = struct.unpack_from("<H", exe, pe+6)[0]
    optional_size = struct.unpack_from("<H", exe, pe+20)[0]
    if struct.unpack_from("<H", exe, pe+24)[0] != 0x10B:
        raise ValueError("Expected PE32 optional header")
    base = struct.unpack_from("<I", exe, pe+24+28)[0]
    sections = [struct.unpack_from("<8sIIII", exe, pe+24+optional_size+i*40) for i in range(count)]

    def offset(va):
        for _,_,rva,size,ptr in sections:
            if rva <= va-base < rva+size:
                return ptr+va-base-rva
        raise ValueError(f"Unmapped address {va:#x}")

    report = {"exe_sha256": hashlib.sha256(exe).hexdigest(), "image_base": hex(base),
              "size": len(exe), "sections": [s[0].rstrip(b"\0").decode() for s in sections]}
    # Addresses are specific to the May 29 2026 binary, not a general PE recognizer.
    if b"May 29 2026" not in exe:
        report["note"] = "Different build: known reference addresses not inspected"
        return report
    report["command_buffer"] = exe[offset(0x43D62C):offset(0x43D62C)+12].hex(" ")
    report["time_buffer"] = exe[offset(0x43D61C):offset(0x43D61C)+12].hex(" ")
    report["rx_state_targets"] = {}
    for state in [0,1,2,50,51,60,61,90,91]:
        index = exe[offset(0x426660)+state]
        target = struct.unpack_from("<I",exe,offset(0x42650C)+index*4)[0]
        report["rx_state_targets"][state] = hex(target)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path",type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.zip_path),indent=2))
