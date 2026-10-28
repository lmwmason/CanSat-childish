# Example recording

`traffic.jsonl` is a recorded-format file (the same format a real session writes) that the ground station
replays like any other recording. `--demo` is just a shortcut for replaying it:

```bash
python3 -m kaist_ground_station --replay kaist_ground_station/demo/traffic.jsonl
```

**It is synthetic, not telemetry from a kit.** 90 s of made-up GPS (a slow circle that only climbs), IMU, ATLM,
DTLM and message packets in the real wire format, so every panel has something to show and the real parser
handles it. Do not use it as flight data. No program code generates it: replace the file to change the demo.
