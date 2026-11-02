# KAIST 기본 펌웨어 개발 폴더

## 現在 동작: 지상국 트리거 제어

자동 왕복을 제거했다. TA0/PF0·TA1/PF1·TA2/PF2는 부팅 시 0도,
체크섬 검사를 통과한 명령 **ID 71, 값 180**에서 모두 180도,
**ID 71, 값 0**에서 모두 0도로 이동한다. 다른 값은 모터에 적용하지 않는다.
재부팅하면 0도로 돌아간다. 1000~2000us 범위를 사용한다.
아래 과거 시험 기록의 자동 왕복 설명은 현재 동작에 해당하지 않는다.

지상국 웹 UI 통신 탭의 `TX 활성화` 후 `180° 전개` / `0° 복귀` 버튼으로 조작한다.
기존 ID/값 명령 폼에서도 ID 71로 송신할 수 있다. UI 변경은 서버 재시작 및 브라우저 새로고침 후 반영된다.
SW6 USB에서는 USB 직결, SW6 BT에서는 SD1000U 무선 연결을 사용한다.
시리얼 write 성공과 실제 서보 동작 완료는 다르며, 위성 SERVO 진단 메시지에서 목표 각도를 확인한다.
지상국 UI 변경은 기존 `command` API와 TX 허용 조건을 그대로 사용한다.

빌드·업로드: `build.py --servo-pins ta`, `upload.py --servo-pins ta --port PORT`.
Flash 29,032 bytes 기록/읽기 검증 성공. 웹 테스트 36개 통과.


현재 동작은 공식 **2026 Default / RUN_PROGRAM=1**이다. 자위성 사출 기능은 아직 추가하지 않았다.
1층·3층 PCB 2025-05-20, 2층 PCB 2022인 사용자 키트를 대상으로 준비했다.
설치된 펌웨어와 배포 소스가 동일한지는 아직 확인하지 않았다.

## 빌드와 업로드 (Linux)

저장소 루트에서:

```bash
python3 firmware/kaist-childsat/build.py
python3 firmware/kaist-childsat/upload.py --port /dev/ttyUSB0 --dry-run
python3 firmware/kaist-childsat/upload.py --port /dev/ttyUSB0
```

실제 포트 이름은 2층 USB 연결 후 확인한다. Bluetooth 지상국 어댑터 포트와 구분한다.
2층 USB 연결 → SW6 USB 경로 → 위성 전원 ON → 해당 포트를 쓰는 지상국/모니터 종료 → 업로드.
완료 후 SW6 BT 경로로 복귀하고 재시작해 GPS/IMU/카메라 및 로그 수신을 확인한다.
업로드 스크립트는 공식 보드 설정대로 ATmega128 / arduino 프로토콜 / 115200 baud를 사용하며,
플래시만 기록하고 기본 검증을 수행한다. 부트로더·퓨즈·EEPROM 기록 명령은 포함하지 않는다.
기존 설치 펌웨어의 플래시 내용은 덮어쓴다.

`build.py`는 현재 PC의 `~/.platformio/packages/toolchain-atmelavr/bin`을 기본으로 사용한다.
다른 설치는 `AVR_TOOLCHAIN=/path/to/bin`으로 지정한다.
`upload.py`는 `~/.platformio/packages/tool-avrdude`를 사용하며 `AVRDUDE_DIR`로 변경할 수 있다.

## 소스와 변경 범위

- 공식 출처: https://cansat.kaist.ac.kr/doc/ko/selectDoc.do?docSeq=10586&menuSeq=3459&bbsSeq=142
- `Cansat_2026_Default.zip`: 원본 및 SHA-256은 `log/kaist-firmware-research/downloads/latest_sources.json`.
- `src/main.cpp`: 원본 .ino. 포함 경로의 역슬래시를 슬래시로, `csBt.c`를 실제 파일명 `csBT.c`로 수정.
- `src/Cansat_Common`, `src/Cansat_Loop`: 기본 소스 모듈. 포함된 .c는 원본 구조대로 main.cpp에서 포함한다.
- `vendor/arduino`: 공식 CanSat 보드 패키지 1.8.19의 코어·ATmega128 variant·라이브러리.
- `vendor/Servo`: 공식 arduino-libraries/Servo 1.2.2.
- `vendor/SD`: 공식 arduino-libraries/SD 1.3.0.
- `vendor/SPI`, `vendor/EEPROM`: 이 PC에 설치된 Arduino AVR framework에서 복사한 라이브러리.
- 공식 ZIP의 Visual Studio 테스트 프로젝트는 다운로드 원본에 보존하며 빌드 대상에 포함하지 않는다.

이 빌드는 공식 소스와 위에 명시한 라이브러리를 조합한 재빌드다. 실제 키트에 설치된 바이너리와
같다는 의미는 아니다. 서보 제어 및 추가 사출 조건을 바꾸기 전에 기본 수신 동작을 확인한다.

## 현재 확인 결과

2026-10-29 Linux AVR 컴파일·링크·HEX 생성 성공.
Flash 27,054 bytes / 정적 RAM 2,509 bytes (스택·힙의 실시간 사용량 제외).
빌드 로그: `log/kaist-firmware-research/build.log`.
실물 기본 펌웨어 업로드 성공: ATmega128 signature 0x1e9702, flash 27,054 bytes written/verified, avrdude exit 0.
SW6을 USB 경로로 옮긴 후 성공했다. 로그: `log/kaist-firmware-research/upload-usb-selected.log`.
업로드 후 기본 수신 재확인과 TA 0·1·2 세 채널 서보 제어 구현은 남아 있다.

## 자동 서보 왕복 시험 모드

사용자 배선: 3층 보드 **TA0/TA1/TA2**. 앞선 PF7/PF6/PF5 대응은 잘못된 해석이었다.
보드 그림과 전용 variant의 csA0/csA1/csA2(ADC 채널 0/1/2)에 따라 PF0/PF1/PF2로 수정했다.
Arduino A 라벨은 뒤집혀 있어 A7/A6/A5에 해당한다. 자료 그림: 2026 보드별 핀 구성 p.4.

```bash
python3 firmware/kaist-childsat/build.py --servo-pins ta
python3 firmware/kaist-childsat/upload.py --servo-pins ta --port /dev/ttyUSB0
```

이 시험 모드는 전원 ON 직후 세 채널을 함께 30~150도 범위에서 20ms마다 1도씩
왕복시킨다. 1000~2000us를 0~180도로 대응한다. 지상국 명령은 필요 없다.
시험 모드에서도 기본 GPS/IMU/카메라/텔레메트리 처리를 유지한다. 통신 대기 루프에서
서보 위치를 갱신해 긴 카메라 처리 중에도 왕복을 진행한다. 기존 D0/D1 서보 출력은
시험 모드에서 사용하지 않는다. TA0~2를 출력으로 쓰므로 그 핀의 아날로그 값은
유효한 센서 측정으로 해석하지 않는다. PF4~PF7을 출력으로 쓰기 위해 JTAG를 실행 중 해제한다.
이는 영구 퓨즈 변경이 아니다. TA0~2는 원래 analog 입력/센서에 연결될 수 있으므로
향후 임무 펌웨어에서는 연결 회로와 센서 기능 공존 여부를 별도 대조해야 한다.
기본 펌웨어 HEX는 build/firmware.hex, TA 시험 HEX는 build/servo-ta/firmware.hex로 분리한다.
AT/DT 빌드 옵션은 서로 다른 핀 매핑을 위한 것으로 현재 사용자 배선에는 쓰지 않는다.
TA 시험 빌드 성공. 시험 펌웨어의 실물 업로드 및 실제 모터 동작은 아직 확인하지 않았다.


서보+통신 동시 시험은 기존 monitor를 사용한다.

```bash
# 위성 2층 USB 직접 연결, 어떤 모뎀 명령도 보내지 않음
python3 -m kaist_ground_station.tools.monitor --port /dev/ttyUSB0 --no-dial --duration 30
# SW6 BT 경로로 복귀 후 SD1000U 어댑터로 무선 연결
python3 -m kaist_ground_station.tools.monitor --duration 60
```

monitor는 UI를 실행하지 않으며 원시 로그와 패킷별 수신 결과를 보존한다.
유선 성공과 Bluetooth 무선 성공은 별도로 확인한다. 현재 동시 시험 펌웨어 빌드 성공:
Flash 27,256 bytes / 정적 RAM 2,529 bytes. USB 장치 미연결로 업로드 및 실측은 아직 미완료.

### 実機 결과: 서보+통신 시험

2026-10-29 사용자 지시에 따라 TA 시험 펌웨어를 업로드했다. Flash 27,256 bytes 기록/읽기 검증 성공.
`upload-servo-telemetry.log`에 보존. USB 직결 monitor --no-dial 20초: 629 bytes, 유효 36프레임
(MESSAGE/ATLM/DTLM 각 12), 오류 7개. 오류 원인은 `76 00 4c 0a` LIFESIGN 길이를 기존
파서가 지원하지 않는 것으로 확인. GPS/IMU 데이터 프레임과 사진 수신은 이번 기록에서 0.
마지막 유효 프레임 age 약 0.71초. Bluetooth 무선 연결과 모터 실제 움직임은 아직 확인 필요.
세션: `log/kaist-ground-station/monitor/20261029T110656.275145Z-live/`.

### 단일 모터 분리 시험

사용자 요청으로 testActiveChannels=1로 변경. TA0(PF0) 하나만 30~150도 왕복하고
TA1/TA2는 입력·pull-up OFF로 두어 PWM을 출력하지 않는다. 텔레메트리는 유지한다.
현재 빌드 29,130 bytes flash / 2,611 bytes 정적 RAM.

### MG90S / 시간 기준 수정

사용자가 MG90S 및 떨림·느림을 보고했다. TA0 단일 시험 유지. 공식 초기화가
TCCR0=5로 변경하지만 Arduino millis는 /64를 전제하므로 시험 setup에서
TCCR0=_BV(CS02)로 복원했다. 29,134 bytes 기록·검증 성공
(upload-servo-timefix.log). 시험 목표 속도는 20ms당 1도, 30→150도 약 2.4초다.
전압강하/공급 전류 및 실제 PWM 파형은 아직 측정되지 않았다.

### 현재 시험: TA0 빠른 이동

사용자 요청으로 점진적 1도 이동을 제거했다. TA0만 30도와 150도 목표를
700ms마다 번갈아 즉시 지정한다. 실제 이동 속도는 MG90S 및 전원/부하에 달려 있다.
TA1/TA2 PWM OFF, 텔레메트리 유지. 빌드 Flash 29,104 bytes / 정적 RAM 2,609 bytes.

### 현재 시험: 세 모터 빠른 이동

TA0/PF0, TA1/PF1, TA2/PF2를 모두 활성화했다. 30도와 150도를 700ms마다
동시에 지정한다. 점진적 1도 이동 없음. 텔레메트리 및 진단 메시지 유지.
Flash 29,144 bytes / 정적 RAM 2,613 bytes.

### GUI 한 번 클릭 전개

기존 사건 버튼 `Parachute open`을 실시간 연결에서 클릭하면 ID71=180을 한 번
송신하고 사건 시각을 기록한다. 이 버튼 동작 동안만 TX를 허용하고 원래 설정으로
복구하므로 별도 TX 체크가 필요 없다. 재생/IDLE에서는 송신하지 않으며 전송 오류 시
전개 사건을 기록하지 않는다. 전개 시각은 명령 전송 시각이며 기계적 전개 완료를 보장하지 않는다.
이 변경은 GUI/backend 변경이므로 위성 펌웨어 재업로드는 필요 없다.

### Bluetooth 주소 조회용 임시 진단

`build.py --bt-info` / `upload.py --bt-info --port PORT`는 서보를 구동하지 않고
UART0에서 115200 및 9600의 정보 조회와 새 모듈 top menu(t)를 시도한다.
USB 수신으로 `BT_DIAG baud=... hex=...`를 저장한다.
업로드 시 SW6 USB, 모듈 응답을 CPU가 읽을 때 SW6 BT, USB 케이블은 유지한다.
영구 설정 쓰기는 포함하지 않는다. 다만 모듈 종류/설정 스위치에 따라 응답이 없을 수 있다.
진단 후 서보 제어 이미지는 `--servo-pins ta` 업로드로 복구한다.
2026-11-01 실제 flash 읽기 백업 및 기존 서보 이미지 비교(29,032 bytes) 불일치 0.
자료 경로 `log/kaist-firmware-research/inventory-20261101/`.

### MCU에서 모듈 응답을 EEPROM에 보존

`bt_inventory.h`: EEPROM 0x100부터 magic/version/length/CRC16과 최대 1,024바이트의
모듈 메뉴를 저장한다. 기존 0x10 운용 플래그는 건드리지 않는다. 동일 자료는 재기록하지 않으며
기록 중 magic을 무효화하고 payload/CRC를 쓴 뒤 magic을 마지막에 확정한다. 전원 중단 시
불완전한 자료는 유효하지 않은 것으로 처리한다. 업데이트 후 MCU가 실제 EEPROM을 재조회해
길이/CRC와 바이트를 비교한다. bootloader EEPROM read의 유효성에 의존하지 않는다.

`--bt-info`는 공식 설정 모드 속도 9600에서 `t` top menu를 요청한다.
명령 에코/짧은 잡음/비문자 데이터/버퍼 초과는 저장하지 않는다. 출력 `saved_verified=1`과
`BT_EEPROM valid=1`이 모두 나와야 보존 성공이다. 미수신은 기존 유효 자료를 덮어쓰지 않는다.
실제 모듈 메뉴가 읽힌다는 것은 아직 별도 실기 확인이 필요하다.

서보 제어 펌웨어에서는 ID70=1로 EEPROM 메뉴를 메시지 채널14에 길이와 16바이트 HEX 조각으로
반환한다. GUI 통신 탭 `BT 저장 정보 조회` 버튼 사용(TX 활성화 필요).
ID71=0/180 서보 제어는 유지한다. 호스트 EEPROM 모의시험에서 정상 저장/무변경 재저장/
CRC 손상 거부/미완료 레코드 거부/기존 플래그 보존을 확인했다.

### 진단 수집/출력 단계 분리

중계 UART0의 TX가 USB와 모듈에 공통이므로 조회 중 디버그 출력을 섞지 않도록 수정했다.
부팅 후 9600 고정으로 startup 수신과 top menu 2회를 각기 수집/검증/저장하고,
모든 수집이 끝난 뒤에만 115200으로 변경해 결과와 EEPROM 내용을 출력한다.
수집 없이 반복 속도 변경은 더 이상 하지 않는다. 실물 검증은 새 진단 업로드 후 필요.
