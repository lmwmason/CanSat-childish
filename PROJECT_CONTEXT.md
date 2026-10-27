# CanSat-childish 프로젝트 인수인계

> 이 문서는 새 agent가 저장소와 최근 작업의 맥락을 빠르게 잡기 위한 요약이다. 기준일: **2026-10-27**. 실제 동작·수치는 링크된 코드와 입력 자료를 확인한다.

## 1. 한 문장 설명

캔위성(CanSat)은 캔 크기의 소형 모의 위성을 떨어뜨려 센서 측정·통신·회수 등의 임무를 수행하는 장치다. 이 프로젝트는 **모(母) 캔위성 1기와 소형 Child 캔위성 여러 기**를 만들고, Child의 하강 궤적에서 주변 **수평 바람의 동쪽·북쪽 성분**을 추정해 시각화하려는 연구다. 우주 궤도 위성이 아니라 지상 대기에서 낙하·활공하는 실험 장치다.

## 2. 시스템과 데이터 흐름

| 구성 | 하는 일 | 이 저장소의 주요 경로 |
| --- | --- | --- |
| 모위성 | 낙하 감지, 반작용휠 자세 제어, 도어·날개 작동, 활공 제어, GPS/IMU 상태 전송 | [`firmware/motherCansat-Firmware/`](firmware/motherCansat-Firmware/), [`pcb/motherBoard/`](pcb/motherBoard/) |
| Child 위성 | 분리 감지, 낙하산 서보 작동, 기압·온습도·가속도 크기 측정, EEPROM 비행 기록 | [`firmware/childCansat-Firmware/`](firmware/childCansat-Firmware/), [`3d-model/`](3d-model/) |
| 지상국 | 모위성 CRSF 텔레메트리 수신·표시·CSV 기록, Child 직렬 로그 조회 | [`guiTool/`](guiTool/) |
| 오프라인 분석 | GPS 궤적 평활화, 수평 이동 속도 및 바람 대리지표 계산, 2D/3D 그림 | [`windField/`](windField/), [`figure_20261026/`](figure_20261026/) |

모위성은 STM32F410RB, Child는 ATmega328/Arduino Pro Mini, 지상국은 PyQt6를 사용한다. 모위성의 전송은 CRSF이고 지상국은 받은 프레임을 `mother_YYYYmmdd_HHMMSS.csv`와 원시 `.crsf`로 저장한다([`telemetry_log.py`](guiTool/cansat_gui/telemetry_log.py)). 전체 임무 시퀀스와 빌드 방법은 루트 [`README.md`](README.md)에 있다. README에 언급된 `simulator/`는 **현재 체크아웃에는 없으므로** 해당 경로를 전제로 작업하지 않는다.

### Child 펌웨어의 원래 저장 형식

Child는 측정값을 EEPROM의 압축 `Record`로 저장하고, 착륙 후 직렬 포트에서 `d` 명령으로 8열 CSV를 덤프한다([`flight_log.h`](firmware/childCansat-Firmware/src/storage/flight_log.h), [`serial_cmd.cpp`](firmware/childCansat-Firmware/src/comm/serial_cmd.cpp)). 열은 `idx,state,t_s,rel_alt_m,pressure_hPa,temp_C,humidity_pct,accel_g`다. 여기에는 **위도·경도와 방향별 가속도가 없다.** `accel_g`는 가속도 크기이므로 이것만으로 수평 바람 방향을 복원할 수 없다. 지상국의 [`protocol.py`](guiTool/cansat_gui/protocol.py)도 이 직렬 형식을 읽는다.

따라서 최근 위치·바람 분석은 Child 펌웨어 EEPROM이 아니라 **Child 각각에 장착한 GoPro의 별도 GPS CSV**를 사용했다. 두 자료의 시계·고도 기준을 자동으로 같은 것으로 가정하지 않는다.

## 3. 연구 목표와 계산의 의미

위경도를 공통 기준점의 동·북 미터 좌표로 바꾼 뒤, 수평 위치를 시간창의 2차 다항식으로 평활화하고 미분해 이동 속도 `(v_E, v_N)`를 얻는다. 낙하산으로 안정적으로 내려오는 Child가 주변 공기의 수평 운동을 충분히 따라간다는 근사에서 이를 **바람의 대리지표**로 쓴다. 중력은 수평 방향에 직접 더하지 않는다. 질량·유효 항력계수·낙하산 면적이 검증되면 수평 응답 지연 보정 `w_h ≈ v_h + τ a_h`를 검토할 수 있으나, 현재 실측 그림의 기본 결과에는 적용하지 않았다.

한 하강 경로에서 얻는 값은 **그 경로 주변의 고도별 수평 이동**이다. 3D 그림의 세 축은 동쪽 위치·북쪽 위치·GPS 고도이고, 화살표의 성분은 수평 2개다. 수직풍을 측정한 3성분 바람장으로 해석하지 않는다. 그림의 반투명 구름과 색칠된 단면은 관측점 주변을 제한적으로 보간한 **시각화**다. 계산식과 한계는 [`figure_20261026/METHODS.md`](figure_20261026/METHODS.md)에 있다.

## 4. 자료별 현재 상태

### `data_20261026/`: 사용자 제공 실측 GoPro GPS

세 파일 `GS010114`, `GS010115`, `GS010116`은 사용자가 **각각 Child에 장착한 실측 기록**이라고 확인했다. 서로 다른 시각에 떨어졌고 정확한 사출·착지 시각은 알려지지 않았다. CSV에는 UTC, 위도·경도·GPS 고도, GPS 2D/3D 속도, `fix`, `precision` 등이 있다. **IMU 가속도·사출 스위치 값은 이 CSV에 없다.** CSV의 UTC 날짜는 2026-10-25, 한국 시각 시험일은 2026-10-26이다.

GPS 고도에서 큰 하락을 찾은 **임시 하강 후보**는 KST로 114: `08:02:10–08:02:31`, 115: `08:06:42–08:07:30`, 116: `08:13:12–08:14:05`다. 이 구간은 영상 확인 전에는 확정 사건 시각이 아니다. GPS 3D 속도의 변화율은 사출의 보조 단서이며 IMU 가속도가 아니다. GPS 고도에는 하강 중 반등이 있고 115는 `−80.9 m`까지 내려간다. 114의 1.375초 고도 증가 `3.77 m`는 같은 구간 GPS 3D 속도로 적분한 총 이동 거리 `1.46 m`보다 커서 두 GPS 필드가 서로 맞지 않는다. **실측 자료라는 사실과 GPS 고도가 실제 높이를 정확히 나타낸다는 주장은 별개**다. 원본을 임의로 단조 하강으로 고치지 않았다.

세 낙하는 비동시이므로 **세 Child를 합쳐 같은 순간의 3D 바람장이라고 주장할 수 없다.** 현재 그림은 기록별 수평 이동과 그 주변의 국소 보간이다. GPS 고도 기준, 실제 사건 시각, 항력 특성, 기준 풍속계가 검증되기 전까지 절대 풍속 정확도를 제시하지 않는다.

### `cansat_fake_data/`: 이전 그림의 입력

이 폴더에서 만든 이전 보고서 그림은 [`figure/`](figure/)에 있다. 사용자는 폴더명 `fake_data`가 잘못됐다고 했으며 **그림 제목에 `fake`라고 쓰지 말라고 요청했다.** 다만 이 폴더의 README와 생성 스크립트는 생성 자료의 시나리오를 설명한다. 출처가 확정되기 전에는 이를 현장 실측 정확도의 증거로 인용하지 않는다. 새 GoPro 결과와 이전 그림의 입력·가정은 서로 다르다.

## 5. 산출물과 재현 경로

- [`windField/README.md`](windField/README.md): 범용 분석 CLI의 입력 형식·실행법. `python3 -m windField demo --output-dir log/demo`는 합성 자료로 처리 경로를 검증한다. `python3 -m windField analyze INPUT.csv --output-dir log/NAME`은 **정규화된 GPS 위치 포함 CSV**를 분석한다. GoPro 원본 CSV를 CLI에 그대로 넣는 형식은 아니다.
- [`figure_20261026/README.md`](figure_20261026/README.md): 이번 실측 GPS의 보고서용 그림 **1–16** 목록. 각 그림은 PNG/SVG 쌍이다. [`METHODS.md`](figure_20261026/METHODS.md)는 계산식·구간 선택·오차와 해석 범위, [`CAPTIONS.md`](figure_20261026/CAPTIONS.md)는 보고서용 그림 설명이다.
- [`figure/README.md`](figure/README.md): 이전 자료의 그림 1–7. 입력 자료와 사건 정보가 이번 GoPro 자료와 다르므로 결과 수치를 섞지 않는다.
- `log/report-2026-10-26/` (**Git 제외**): 원본 해시와 구간 선택을 담은 `selection_summary.json`, 정규화 스크립트 `prepare.py`, Child별 CLI 결과(`analysis_primary_*/`), 창 길이 3/5/7/11/15초 실험, 그림 생성 스크립트 `make_figures.py`·`make_wind_figures.py`, 고도 일관성 확인 `check_altitude_consistency.py`, stdout/stderr, 그림 개정본을 보존한다. 보고서 주 결과는 **11초 위치 평활화, 사출 후 3초 제외, 5 m GPS 고도 bin**이다.

저장소 루트에서 필요 패키지를 설치한 뒤 테스트는 `python3 -m unittest discover -s windField/tests -v`, 분석기 도움말은 `python3 -m windField --help`로 확인할 수 있다. 새 데이터에 적용할 때는 원본 형식과 실제 사건 시각을 먼저 확인하고 별도 `log/` 결과 폴더를 사용한다.

## 6. 협업 규칙과 남은 검증

- 현재 작업 브랜치는 **`feat/wind-field-analysis`**다(기준일 현재). 최근 커밋 제목은 `feat:`, `fix:`, `docs:`, `chore:` 형식을 사용한다. 작업 전 `git status`와 최근 커밋을 확인한다.
- 사용자 요청으로 `docs/`에는 연구 기록(`research.md`)과 개발 기록(`devlog.md`), `log/`에는 실험 스크립트·입출력·오류 로그·이전 그림 버전을 **로컬에 모두 보존한다.** `.gitignore`에서 두 폴더를 제외한다. `figure/`, `figure_20261026/`의 보고서 산출물은 Git에 올렸다. 사용자 제공 데이터 폴더 `data_20261026/`, `cansat_fake_data/`는 현재 untracked이며 별도 지시 없이 커밋하지 않는다.
- 그림은 보고서에 들어갈 학술적 스타일을 선호한다. 선이 너무 얇지 않게 하고, 불필요한 큰 제목·장식은 피한다. 3D 그림은 좌표의 의미, 관측값과 보간값의 차이를 명시한다. 출력은 이전 `figure/`와 새 `figure_20261026/`를 섞지 않는다.
- 다음 핵심 검증은 **영상의 실제 사출·착지 프레임**, GPS 시각/고도 기준과 독립 고도계, Child 질량·낙하산 면적/항력 특성, 기준 풍속계와의 동시 측정이다. 이 정보가 오면 임시 구간과 풍속을 다시 계산한다.
