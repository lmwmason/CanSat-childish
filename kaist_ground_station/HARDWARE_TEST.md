# 실제 장비 통신 시험 기록

2026-10-27, Linux에서 UI 없이 수행했다. 기존 UI와 Claude가 작업 중인 프런트엔드는 수정하지 않았다.

## 확인된 장비와 연결

- PC 쪽: Parani SD1000U, firmware 2.0.3, MODE0 / NoFC.
- USB 식별: FTDI FT232R, VID:PID `0403:6001`, 포트 `/dev/ttyUSB0`.
- 위성 쪽 검색 이름: ESD100V2, firmware 2.0.6.
- 직렬 설정: 115200, 8N1, 흐름 제어 없음.
- `AT`, `AT+BTINFO?`, `AT+BTVER?` 조회에 정상 응답했다.
- `AT+BTINQ?` 검색 후, 실제 검색된 위성 주소로 `ATD<address>`를 보내 `CONNECT`를 받았다.

실제 장치 주소와 원문 응답은 Git 제외 `log/kaist-ground-station/hardware/`에만 기록한다.
포트 open과 무선 CONNECT는 서로 다른 단계다. 포트를 열었다고 위성에 연결된 것으로 판단하면 안 된다.

## 최초 수신 기록에서 확인한 것

원시 RX 317,624 bytes를 보존했다. 수신을 중지할 당시 마지막 영상은 전송 도중이었다.

- JPEG 24장: Pillow `verify()`로 모두 정상 확인.
- ATLM 24개, DTLM 24개, IMU 24개.
- GPS 24개: 실내에서 fix=0, 위성 수=0. 좌표를 만들어 채우지 않는다.
- 사용자 메시지 120개, 카메라 ACK 48개, LIFESIGN 16개.
- IMAGE_SIZE 25개: 마지막 한 건은 중지 시점에 전송 중이었다.

실측에서 확인한 다음 형식을 parser에 반영한 뒤, 원시 RX 전체를 113-byte 단위로
재입력했을 때 완성된 프레임은 parser 오류 없이 해석됐다. 파일 끝의 8,411 bytes는
중지 시점의 부분 영상이므로 완성 프레임이라고 주장하지 않는다.

### GPS 중복 checksum

실제 wire:

```text
76 00 58 00 $GPGGA,,,,,,0,00,99.99,,,,,,*48 CR *48 CR LF
```

위성 firmware가 원래 NMEA checksum/CR을 보존하고 checksum을 다시 붙인다.
실내 no-fix 자체와 parser의 형식 호환 문제는 별개다.
두 checksum이 서로 같고 원래 NMEA 본문의 XOR에도 맞을 때만 수신한다.
`checksum_envelope=repeated_after_cr`를 이벤트에 남기고 Frame.raw에 원문을 보존한다.

### 기타 수신 형식

- ATLM/DTLM은 EXE와 같은 compact header였다.
- 이 위성의 IMU는 `*`를 포함하는 합산 checksum을 사용했다. decoder는 사용한 변형을 기록한다.
- `76 00 36 00 00`은 카메라 제어 응답이다. CAMERA_ACK로 기록하며 위성의 일반 명령 ACK로 해석하지 않는다.
- `76 00 4C 09 [time:4][uptime:4][xor:1]`은 LIFESIGN이다.
  payload XOR, big-endian 시각/uptime 처리는 배포 EXE의 `0x425A88–0x425C90`과 대조했다.
  위성의 time 값이 신뢰할 만한 UTC인지 별도로 확인하기 전에는 `satellite_time_raw`로 기록한다.
- 카메라는 전체 이미지 길이 기준 형식으로 실제 JPEG가 완성됐다.
  내부 UART를 64 bytes씩 처리한다는 설명과 무선 패킷마다 header/trailer가 반복된다는 주장은 구분해야 한다.

## 재연결과 송신 검증 상태

최초 수신 세션을 닫은 뒤 다시 열었을 때 수신기가 STANDBY였고, 한 차례
`ATD<address>` 재연결은 `OK` 후 `ERROR`로 종료됐다. 현재 장비 검색/재연결을
추가 확인해야 한다. 최초 데이터 수신 성공과 재연결 안정성 검증을 구분한다.

UTC 시각 명령을 LIFESIGN으로 검증하는 도구를 준비했지만, 재연결 실패로
시각 명령은 실제로 송신하지 않았다. 위성 명령의 왕복 적용은 아직 미검증이다.
센서 ON/OFF, EEPROM 설정, 서보 등 구동기 명령은 보내지 않았다.

## 재현 자료

- 원시 RX/TX, 시간 기록, CSV, JPEG: `log/kaist-ground-station/hardware/sessions/`
- 모뎀 조회/검색 기록 및 벤치 실행 도구: `log/kaist-ground-station/hardware/`
- 실측 형식을 반영한 회귀 테스트: `tests/test_link_faults.py`
- 백엔드 검증: `python3 -m unittest kaist_ground_station.tests.test_protocol kaist_ground_station.tests.test_service kaist_ground_station.tests.test_link_faults -v`

현재 백엔드 21개 테스트가 통과했다. UI 테스트는 이 작업에서 실행하거나 수정하지 않았다.
