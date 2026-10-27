# 실시간 통신 확인

저장소 루트에서 실행한다. UI를 열지 않으며 기존 UI 파일을 변경하지 않는다.

```bash
python3 -m kaist_ground_station.tools.monitor
```

- SD1000U의 FTDI USB 포트를 자동 선택하고 115200 8N1로 연다.
- 먼저 수신 중인 유효 패킷이 있으면 그대로 수신한다.
- 수신이 없으면 `AT+BTINFO?`로 상태를 조회한다. STANDBY일 때만 `ATD`를 보내
  수신기에 저장된 마지막 위성으로 연결한다.
- 1초마다 수신량·초당 수신량·유효 패킷 수·오류 수·마지막 유효 수신 경과 시간·GPS·IMU·사진 수를 표시한다.
- `OK`/`CONNECT`만으로 실시간 수신이라고 표시하지 않는다. 실제 해석된 CanSat 프레임이 필요하다.
- 마지막 유효 패킷이 5초 넘게 없으면 `수신 지연/끊김`으로 표시한다. GPS fix=0은 `미측위`로 표시한다.
- 연결 시도에 명시적인 `ERROR`가 오면 5초 뒤 재시도한다. 응답이 없는 pending 명령은 중복 송신하지 않는다.
- 위성 제어/구동기/시각 동기화 명령은 보내지 않는다. 송신하는 것은 모뎀 조회·연결 명령뿐이다.

Ctrl+C로 종료한다. 종료 시 포트를 닫고 `monitor_summary.json`을 저장한다.
원시 RX/TX, 시각 포함 `traffic.jsonl`, 해석 CSV, JPEG는
`log/kaist-ground-station/monitor/` 아래 세션별로 보존한다.

한 포트는 한 프로그램에서 사용한다. 같은 USB 포트를 사용 중인 지상국 UI/다른 스크립트가 있다면 먼저 연결을 해제한다.
Python에 pyserial이 없다면 `python3 -m pip install pyserial`로 준비한다.

```bash
# 포트 직접 지정
python3 -m kaist_ground_station.tools.monitor --port /dev/ttyUSB0

# 다른 위성 주소로 연결 (12자리 또는 콜론 구분 MAC)
python3 -m kaist_ground_station.tools.monitor --remote 00:01:95:12:34:56

# 60초만 시험
python3 -m kaist_ground_station.tools.monitor --duration 60

# USB 직결 또는 모뎀 연결이 이미 관리되는 경우: 어떤 송신도 하지 않음
python3 -m kaist_ground_station.tools.monitor --port /dev/ttyUSB0 --no-dial
```

종료 코드는 0=정상 종료/시간 내 유효 프레임 수신, 1=포트·기록 등 실행 오류,
2=지정 시간이 끝날 때까지 유효 프레임이 하나도 없었음이다. Ctrl+C는 정상 종료(0)다.
한 번이라도 수신됐다는 것과 종료 직전까지 계속 수신 중이었다는 것은 구분하며,
마지막 수신 경과 시간과 종료 요약을 함께 확인한다.
