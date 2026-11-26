"""Summarise guest logout runs: classify the first logout's captures.

Usage: python3 vmsum.py <result_dir>...
. desktop or greeter picture, # black, % mostly dark or over 2% black, R relay (orange),
C compositor backdrop (cyan), M greeter marker.
"""
import re
import subprocess
import sys
from pathlib import Path

for run in map(Path, sys.argv[1:]):
    log = (run / "serial.log").read_bytes().decode(errors="replace").replace("\r", "")
    frames = sorted(run.glob("frame-*.png"))
    out = subprocess.run(
        ["magick", *map(str, frames), "-colorspace", "sRGB", "-format",
         "%[fx:mean] %[hex:p{640,400}] %[hex:p{20,20}]\\n", "info:"],
        capture_output=True, text=True, check=True).stdout.split("\n")
    # Share of near-black pixels: catches captures that are only partly black.
    lit = subprocess.run(
        ["magick", *map(str, frames), "-colorspace", "sRGB", "-fuzz", "3%",
         "-fill", "white", "+opaque", "black", "-format", "%[fx:mean]\\n", "info:"],
        capture_output=True, text=True, check=True).stdout.split()
    kinds = []
    for line, share in zip(filter(None, out), lit):
        mean, centre, corner = line.split()
        if centre.startswith("FF8000") and corner.startswith("FF8000"):
            kind = "R"
        elif centre.startswith("00FFFF") and corner.startswith("00FFFF"):
            kind = "C"
        elif centre.startswith("FF00FF"):
            kind = "M"
        elif float(mean) < .01:
            kind = "#"
        elif float(mean) < .3:
            kind = "%"
        else:
            kind = "."
        if kind == "." and float(share) < .98:
            kind = "%"
        kinds.append(kind)
    captures = "".join(kinds)
    first = re.search(r"\.([#%RCM][#%RCM.]*?)\.{8,}", captures)
    gap = first.group(1) if first else ""
    print(run.name, "relogin=" + "".join(re.findall(r"LOGOUT_VM_RELOGIN=(passed|failed)\n", log)))
    print("  captures", captures)
    print(f"  first gap: {len(gap)} captures;", " ".join(
        f"{name}={gap.count(mark)}" for name, mark in
        (("black", "#"), ("partial", "%"), ("relay", "R"), ("backdrop", "C"), ("marker", "M"))))
    events = re.findall(r"(?m)^[\d.]+ ((?:TRIGGER|SWITCHED|PAINT\S*|RELEASE|DONE|TIMEOUT|RESTORED).*)$", log)
    print("  relay", " | ".join(events))
    holder = re.findall(r"logout-holder\[\d+\]: [\d.]+ (.*)", log)
    if holder:
        print("  holder", " | ".join(holder))
