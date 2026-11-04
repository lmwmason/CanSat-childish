# figure_20261102 (1): GPS 기록 분석

- 입력: `flight_test/20261101T225646.570711Z-live/events.csv`
- 입력 파일 수정 시각: 2026-11-02 07:59:43 KST; 이 시각으로 폴더 날짜와 같은 날의 순서를 정함
- 원본 SHA-256: `831c2f00e317eea01ae9060f7489158c19cd6aa15c12d689581c8874a769c1bc`
- 위치가 있는 GPS fix: 55개; 원본 GPS GGA 고도 범위: -302.1–134.6 m

[공통 계산식·품질 제한](../METHODS_20261104.md) · [그림 설명](CAPTIONS.md)

## 임시 하강 구간과 수평 이동

GPS 고도가 −302.1 m까지 내려가고 수평 위치가 크게 벗어난다. 신뢰할 수 있는 하강 구간과 수평 이동 속도를 제시하지 않고 원본 진단 그림 1–3만 제공한다.

## 파일

| 번호 | 내용 |
| --- | --- |
| 1 | [figure_1_raw_gps_altitude_quality.png](figure_1_raw_gps_altitude_quality.png) / [figure_1_raw_gps_altitude_quality.svg](figure_1_raw_gps_altitude_quality.svg): GPS GGA 원본 고도, HDOP, 위성 수와 임시 하강 구간 |
| 2 | [figure_2_raw_gps_plan_track.png](figure_2_raw_gps_plan_track.png) / [figure_2_raw_gps_plan_track.svg](figure_2_raw_gps_plan_track.svg): 전체 GPS 수평 궤적과 선택한 구간 |
| 3 | [figure_3_raw_imu_angles.png](figure_3_raw_imu_angles.png) / [figure_3_raw_imu_angles.svg](figure_3_raw_imu_angles.svg): IMU 원본 3축 각도와 선택한 구간 |

생성 스크립트·분석용 CSV·실행 로그와 첫 그림 시안은 Git 제외 경로 `log/report-2026-11-04/`에 보존했다. 원본 `flight_test/`는 수정하지 않았다.
