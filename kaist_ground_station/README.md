# KAIST CanSat Linux Ground Station

KAIST 기본 키트용 독립 지상국이다. 기존 `guiTool/`을 수정하거나 가져오지 않는다.
Python 서비스와 Tk 화면을 분리했으며 Windows 실행파일이나 Wine을 사용하지 않는다.
현재는 **소프트웨어·Linux 가상 직렬 포트 검증을 마친 초기 구현**이다.
실제 키트·Bluetooth 무선 연결·카메라·명령 적용은 아직 검증하지 않았다.

## 실행

저장소 루트에서:

```bash
python3 -m venv kaist_ground_station/.venv
kaist_ground_station/.venv/bin/pip install -r kaist_ground_station/requirements.txt
kaist_ground_station/.venv/bin/python -m kaist_ground_station --demo
```

Tk가 없는 Linux Python 환경은 배포판의 `python3-tk` 패키지가 필요하다.
Conda 환경은 해당 환경의 Tk 지원도 확인한다. 한글은 Noto Sans CJK KR이 있으면 사용한다.
새 폴더 내부 `.venv/`는 해당 폴더의 `.gitignore`로 제외한다.
아래 예시의 `python3`는 필요한 패키지가 설치된 Python을 가리킨다.

실제 포트와 연결:

```bash
python3 -m kaist_ground_station --port /dev/ttyUSB0
python3 -m kaist_ground_station --port /dev/rfcomm0
```

기본값은 **115200, 8N1, 흐름 제어 없음**이다. 포트는 새로고침하거나 직접 입력한다.
직렬 포트가 열렸다는 사실과 Bluetooth 무선 연결 완료는 다르다.
SD1000U 같은 USB 직렬 Bluetooth 어댑터 또는 이미 연결된 Linux RFCOMM 장치를 사용한다.
어댑터 고유의 연결/설정 명령은 `원시 수신 / BT 터미널`에서 수동으로 보낼 수 있다.
ASCII 모드는 CRLF를 붙이고 HEX 모드는 입력한 바이트만 보낸다.
보드/모뎀 종류별 자동 검색·페어링 절차는 아직 구현하지 않았다.
포트 권한이 없으면 해당 배포판의 직렬 장치 접근 권한을 설정한다.

### 화면 기능

- GPS 위치·fix·위성 수·고도, 로컬 궤적, 최근 고도 변화
- IMU X/Y/Z 회전 미리보기와 전체 필드 원시값
- ATLM 8채널 원시값·환산값, DTLM 최대 32개 상태
- JPEG 수신/저장, QLOOK 회색조 표시, 사용자 메시지 수신/저장
- 프레임 수·오류 수·수신 지연·버린 바이트 수, 원시 수신 터미널
- 직렬 수신, 데모, 시간 간격을 보존한 로그 재생
- 디지털/값 명령 및 UTC 시각 전송

화면의 GPS 궤적은 첫 fix 기준 로컬 동·북 좌표다. 배경 지도 영상은 아직 사용하지 않는다.
GPS 고도는 GGA의 고도를 그대로 표시하며 AGL로 환산하지 않는다.
IMU 그림은 XYZ Euler 회전 미리보기이며, 센서 장착 방향·회전 순서는 실기로 확인해야 한다.
추가 IMU 필드 3–15는 센서 출력 설정에 따라 뜻이 달라서 임의로 가속도/자이로 단위를 붙이지 않는다.
값은 마지막 수신값을 유지하고 GPS·IMU age를 하단에 표시한다.
화면의 링크 age는 마지막 유효 프레임 기준이며 메시지만 들어와도 GPS가 최신이라는 뜻은 아니다.
사용자 메시지 내용과 바이트 원문은 `events.csv`와 `traffic.jsonl`에 남는다.

### 센서 환산

배포 자료의 `csAtlmSet.cfg`를 화면에서 불러오거나 다음처럼 지정한다.

```bash
python3 -m kaist_ground_station --calibration /path/to/csAtlmSet.cfg --demo
```

형식은 `ID,MODE,A,B,UNIT`이고 MODE=1일 때 `A*raw+B`를 적용한다.
설정이 없으면 원시값으로 표시한다. 세션 도중 환산 계수를 바꾸지 않으며,
사용한 설정은 세션 메타데이터에 보존한다. 참고 예시는 `config/calibration.example.cfg`다.

### 명령 전송

실제 직렬 연결 후 `TX 활성화`를 켜고 ID/값을 입력한다.
디지털 ID 0–23은 값 0/1, 값 명령 ID 64–71은 0–255다.
연결/소스를 바꾸면 TX 활성화가 해제된다. 자동 재전송과 자동 명령은 없다.
데모와 재생은 송신할 수 없고 재생 파일의 TX 레코드는 하드웨어로 보내지 않는다.
송신 완료는 **직렬 포트에 기록했다는 뜻**이다. 별도 ACK를 가정하지 않으며,
DTLM 등 실제 수신 상태가 바뀌었는지 확인한다.

## 로그와 재생

기본 저장 위치는 현재 작업 디렉터리의 `log/kaist-ground-station/sessions/`다.
루트 `.gitignore`에 따라 `log/`는 커밋되지 않는다. `--log-dir`로 변경할 수 있다.
LIVE / REPLAY는 각각 별도 세션 폴더로 분리한다.

| 파일 | 내용 |
| --- | --- |
| `session.json` | 소스·모드·시작 UTC·환산 설정·형식 버전 |
| `rx.bin`, `tx.bin` | 수신/성공적으로 write한 송신 바이트 연결본 |
| `traffic.jsonl` | 세션 경과 초·방향·HEX, 재생 가능한 원시 트래픽 |
| `events.csv` | 수신 UTC·경과 초·종류·체크섬·해석 JSON·프레임 HEX |
| `image-00001.jpg` 등 | 완성된 JPEG |

`TX_REQUEST`는 송신 의도, `TX_WRITTEN`은 직렬 write 완료다.
부분 write나 USB 분리 시 실제 전달량이 불확실할 수 있으며 자동으로 재전송하지 않는다.
원시 RX는 패킷 해석 전에 저장한다. 기본 1초 간격으로 flush하고 정지 시 닫는다.
전원 차단/프로세스 강제 종료 시 마지막 버퍼까지 영구 보존된다는 보장은 없다.

```bash
python3 -m kaist_ground_station --replay log/kaist-ground-station/sessions/SESSION/traffic.jsonl
python3 -m kaist_ground_station --headless --port /dev/ttyUSB0 --duration 60
python3 -m kaist_ground_station --headless --demo --duration 10
```

재생은 이 프로그램의 `traffic.jsonl` 형식이며, 기존 KAIST CSV의 직접 재생은 지원하지 않는다.
서로 다른 위성의 스트림은 각자 다른 포트/프로세스로 운용한다. 기존 Crossfire 위성 지원은
기존 지상국에 그대로 있으며 이 새 프로그램에 아직 합치지 않았다.

## 구조

```text
ui.py                  화면·캔버스·사용자 입력
  ↓ 사용자 의도            ↑ 독립 Snapshot (원본 상태를 수정할 수 없는 복사본)
service.py             연결 수명·모드·송신 조건·세션 기록 조율
  ├─ transport.py      직렬 read/write / 포트 목록
  ├─ protocol.py       바이트 스트림 → Frame / 명령 → 바이트
  ├─ models.py         텔레메트리 상태 / 보정 설정
  └─ recording.py      원시 트래픽·CSV·이미지·재생
demo/traffic.jsonl     예시 녹화 (합성 바이트, 데이터 파일). --demo는 이걸 재생하는 단축 옵션
__main__.py            실행 옵션 / GUI 또는 headless 조립
```

통신 계층은 Tk를 import하지 않는다. UI에서 직렬 포트·패킷·로그 파일을 직접 다루지 않는다.
서비스는 한 이벤트 루프에서 `tick()`으로 구동하며 transport와 monotonic clock을 주입할 수 있다.
Tk 화면을 교체할 때는 `StationService`와 `Snapshot` 계약을 유지하면 된다.
`Snapshot.telemetry`는 방어적 깊은 복사다. 서비스의 실제 상태를 노출하지 않는다.
고도 이력 600개, 궤적 5,000개, 화면 이벤트/수신 미리보기는 유한 길이로 유지한다.

새 패킷 지원은 `protocol.py` → `models.py` → 표시용 snapshot → `ui.py` 순서로 확장한다.
프로토콜 규격·문서와 EXE 차이·근거 주소는 [PROTOCOL.md](PROTOCOL.md)에 정리했다.

## 검증

```bash
python3 -m unittest discover -s kaist_ground_station/tests -v
# X display가 있는 환경에서 실제 위젯/작은 창 검사도 포함:
RUN_KAIST_UI_TESTS=1 python3 -m unittest discover -s kaist_ground_station/tests -v
```

테스트는 리터럴 패킷, 가능한 모든 분할 지점, 1바이트 수신, 손상 체크섬,
손실 후 재동기화, no-fix, 지연된 부분 프레임, 이미지 내 헤더 바이트,
전체/64바이트 분할 이미지, 문서/EXE 변형, 세션 기록/재생, 송신 차단,
센서 환산, USB 오류, Linux PTY의 실제 pyserial read/write를 확인한다.
카메라 테스트는 인위적으로 만든 전송 데이터이므로 실제 카메라 호환성의 증거는 아니다.

비행 전 지상 검증은 다음 순서로 진행한다.

1. USB 직결로 실제 RX를 기록하고 패킷 종류·체크섬·갱신 주기를 확인한다.
2. 같은 키트를 KAIST EXE로 수신한 값/로그와 비교해 좌표·IMU·ATLM·DTLM 해석을 대조한다.
3. 실제 무선 어댑터로 연결해 모뎀 연결 절차와 수신 복구를 확인한다.
4. 알려진 명령의 결과를 DTLM 및 해당 기능에서 확인한다. 송신 성공만으로 적용됐다고 판단하지 않는다.
5. JPEG 전체/분할 패킷·영상 크기와 사용자 추가 메시지를 실측 캡처로 검증한다.
6. 지상에서 통신 거리·안테나 방향 변화·일시 단절·재연결·로그 재생을 점검한다.

수신 후 확보한 `traffic.jsonl`을 회귀 테스트 fixture로 추가하면 이후 수정 시 같은 자료로 검증할 수 있다.
