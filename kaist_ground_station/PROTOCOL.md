# KAIST 2026 protocol implementation notes

조사 기준: 2026-10-27. 실행파일은 실행하지 않고 정적으로 분석했다.
**문서 근거, EXE에서 확인한 동작, 하드웨어에서 확인한 동작을 구분한다.**
아래는 최초 정적 조사 내용이다. 이후 실제 SD1000U/ESD100V2 장비로 수신한
형식과 검증 결과는 [HARDWARE_TEST.md](HARDWARE_TEST.md)를 우선 참고한다.

## 입력 자료

사용자 제공 `/home/airhood/Downloads/kaist_cansat_docs/`:

- `온라인교육자료_캔위성_2026_11_프로토콜_20260606.pdf`, pp.10–19: 패킷과 체크섬
- `온라인교육자료_캔위성_2026_10_데이터_처리_20260602 .pdf`, p.9: 2025 이후 이미지 64바이트 분할
- `온라인교육자료_캔위성_2026_07_기초_점검_통신_20260527.pdf`, pp.2–6: 스위치·115200·모뎀 연결
- `온라인교육자료_캔위성_2026_12_데이터_활용_20260606.pdf`, pp.2–4: 로그 자료 종류

실행파일 근거는 사용자 제공 `Cansat_Gs_20260529.zip`의 `Cansat_Gs.exe`다.
정적 분석 대상은 x86 PE32 / MFC 빌드이며, 아래 주소는 ImageBase=0x400000인
**해당 실행파일의 가상 주소**다. 다른 배포 버전에도 같은 주소가 있다고 가정하지 않는다.
자료 SHA-256과 추출 텍스트·분석 중간 결과는 Git 제외 `log/kaist-ground-station/`에 보존한다.
PDF나 실행파일 원본은 이 폴더에 재배포하지 않는다.

## 수신 형식

아래 바이트는 16진수다. `n`, `payload`, `sum`, `xor`는 값 자리다.

| 종류 | 지원 형식 | 검사 / 출처 |
| --- | --- | --- |
| ATLM | `76 00 40 10 [8 bytes] sum` | EXE compact, 합 mod 256 |
| ATLM | `76 00 40 00 10 [8 bytes] sum` | PDF p.12, 동일 합 |
| DTLM | `76 00 48 n [n bytes] xor` | EXE compact, n=2/3/4 |
| DTLM | `76 00 48 00 n [n bytes] xor` | PDF p.13의 n=4, 구형 n=2/3도 수신 |
| GPS | `76 00 58 00 $GPGGA,...*HH CR LF` | PDF p.15, NMEA XOR |
| GPS | `76 00 58 00 $GNGGA,...*HH CR LF` | 위와 같음 |
| IMU | `76 00 60 00 *x,y,z,...,HH CR LF` | PDF p.14 / EXE, 아래 참고 |
| Message | `76 00 A0..AF n [n bytes]` | PDF p.10, 체크섬 없음 |
| QLOOK | `76 00 80 n Xlo Xhi Ylo Yhi [pixels]` | PDF p.11, 체크섬 없음 |
| JPEG size | `76 00 34 00 04 00 00 Shi Slo` | PDF p.16, unsigned big-endian |
| JPEG data | `76 00 32 00 00 [JPEG] 76 00 32 00 00` | PDF p.17, JPEG SOI/EOI 검사 |

DTLM 각 바이트를 LSB부터 bit 0–7 순서로 표시한다. 16/24비트 구형 수신은
나머지 비트를 0으로 꾸며 채우지 않고 미수신으로 표시한다.
GGA fix=0이면 현재 위치/고도를 비우고 궤적 점을 추가하지 않는다.
GGA 좌표는 도분→십진도로 바꾸고 N/S/E/W 부호를 반영한다.

### 문서와 EXE의 차이

- **ATLM compact 헤더**: receiver `0x421BA0`, type switch `0x421CF1`에서
  `40`을 읽으면 state 50으로 이동한다. jump table `0x42650C`, byte index
  table `0x426660`을 따라가면 state 50 → `0x422769`다. 여기서 바로 `10`을
  비교하고 state 51 → `0x4227BD`에서 첫 ATLM 값을 저장한다. PDF의 추가
  reserved `00`이 없다. `10`은 십진수 10이 아니라 실제 바이트 **0x10**이다.
- **DTLM compact 헤더**: type `48` → state 60 → `0x422B9F`에서 바로
  길이 `02`, `03`, `04`를 비교한다. `0x422C0F`에서 payload 첫 바이트를 저장한다.
- **IMU 합산**: `0x423E79`에서 `*`를 버퍼 첫 바이트에 저장한다.
  `0x424231`부터 시작하는 해석 루프는 index 1부터 돌고 `0x424327` 이후
  마지막 checksum 구분 comma 이전까지 합산한다. 따라서 EXE는 `*`를 제외한다.
  PDF의 IMU_DATA 합이라는 표현에 대응하여 `*` 포함 방식도 수신하고,
  `checksum_basis`에 `excluding_star_exe` / `including_star_pdf`를 구분해 기록한다.
  파서는 checksum을 생략하거나 불일치 프레임을 정상으로 처리하지 않는다.
- IMU 6개 필드의 추가 3개가 gyro인지 accel인지는 출력 설정에 따라 달라진다.
  현재 수신값을 순서대로 기록하며 추가 필드 의미를 임의 지정하지 않는다.

이 구현은 문서/EXE에서 확인한 후보를 함께 수신한다. 어느 변형을 실제 키트가
보내는지는 RX 캡처로 확인하고 회귀 fixture로 고정해야 한다.

## 송신 형식

| 종류 | EXE와 동일하게 송신하는 바이트 |
| --- | --- |
| Digital/value command | `56 00 48 00 ID VALUE (ID xor VALUE) 00` |
| UTC Unix timestamp | `56 00 49 00 T3 T2 T1 T0 (T3 xor T2 xor T1 xor T0) 00` |

PDF pp.18–19에는 마지막 `00`이 없다. EXE의 정적 송신 버퍼와 write 길이는 다음과 같다.

- `0x43D62C`: `08 56 00 48 00 00 00 00 ...`; `0x42CD10`이 ID/value/xor를
  buffer index 5/6/7에 쓴다. 송신 함수 `0x42CC70`은 첫 바이트를 길이로,
  주소+1을 데이터 포인터로 사용하므로 **8바이트**를 쓰고 마지막은 zero다.
- `0x43D61C`: `0A 56 00 49 00 ...`; `0x42CE20`이 time과 xor를 index 5–9에
  쓴다. 동일 송신 함수가 **10바이트**를 쓰므로 끝에 zero 하나가 추가된다.

디지털 ID 0–23은 값 0/1, ID 64–71은 값 0–255만 만든다.
시각은 UTC Unix 초를 big-endian unsigned 32-bit로 보낸다.
ACK 패킷은 제공 문서에서 확인되지 않아 추정 구현하지 않는다.

## 아직 확인할 부분

- **카메라 분할**: 데이터 처리 p.9의 64바이트 분할 설명은 상세 framing을
  제시하지 않는다. 현재 전체 payload+trailer와, 64바이트마다 동일 header/trailer를
  갖는 후보를 지원한다. 후자는 **가설 기반 구현**이고 실측 호환성은 미확인이다.
  JPEG 내 sync와 같은 값은 payload 길이에 따라 처리한다. ESP32 카메라의
  확장 크기/별도 패킷이나 여러 카메라 동시 스트림은 미지원이다.
- **Bluetooth 연결 명령**: 직렬 어댑터별 초기화·검색·원격 ID 연결 시퀀스는 미확정이다.
  EXE의 `0x41425D–0x4142B3`에서 기본 `ATD\r\n` 송신 분기를 확인했지만,
  ID 지정 분기는 별도 상태를 사용한다. 자동화하지 않고 raw 터미널로 확인한다.
- EXE type switch에서 추가 type `4C`, `50`을 확인했다. 각각 생존/시각 계열 및
  추가 GPS 계열로 보이나 상세 wire format은 아직 구현하지 않았다.
  raw RX를 보존하고 unknown type 오류로 표시한다. checksum-valid 프레임으로 간주하지 않는다.
- QLOOK 픽셀의 가로 순차 배치는 문서 예제로 구현했다. 512 경계 넘는 행은 오류 처리한다.
- 모뎀 응답의 텍스트는 raw 터미널에 표시하며 위성 패킷과 구분한다.

## 재현과 다음 검증

`python3 -m kaist_ground_station.tools.inspect_reference /path/to/Cansat_Gs_20260529.zip`
으로 실행파일 SHA, PE 구조, 송신 정적 버퍼와 수신 jump-table 매핑을 확인할 수 있다.
이 스크립트는 PE를 실행하지 않는다. 해석 루프는 `objdump -d -Mintel`로 확인했다.

소프트웨어 fixture/PTY 검증과 실제 하드웨어 검증을 구분한다.
첫 실측에서 raw RX와 기존 EXE CSV를 짝지어 compact/PDF header, IMU 합산,
카메라 분할, unknown type, 모뎀 연결 절차를 확정한다.
