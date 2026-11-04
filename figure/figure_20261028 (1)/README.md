# figure_20261028 (1): GPS 기록 분석

- 입력: `flight_test/20261027T231100.585097Z-live/events.csv`
- 입력 파일 수정 시각: 2026-10-28 08:14:07 KST; 이 시각으로 폴더 날짜와 같은 날의 순서를 정함
- 원본 SHA-256: `19238b2ef45bee6b4d035c36089fb2afb1e45f20078901d6282cef67b1d58a42`
- 위치가 있는 GPS fix: 70개; 원본 GPS GGA 고도 범위: 145.5–243.9 m

[공통 계산식·품질 제한](../METHODS_20261104.md) · [그림 설명](CAPTIONS.md)

## 임시 하강 구간과 수평 이동

| 구간 | 세션 시작 후 시간 | 원본 GPS 고도 처음→끝 | 통과 표본 | 평균 동쪽 | 평균 북쪽 | 평균 벡터 크기 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 47–120 s | 243.9→148.7 m | 29 | +0.31 m/s | -0.63 m/s | 0.70 m/s |

하강 시작·끝은 원본 GPS 고도와 궤적을 보고 임시로 선택했다. 사출·착륙 이벤트 확인 전의 값이다. 평균 벡터는 통과 표본의 동·북 성분을 평균한 뒤 크기를 구한 것으로, 검증된 실제 풍속이 아니다.

## 파일

| 번호 | 내용 |
| --- | --- |
| 1 | [figure_1_raw_gps_altitude_quality.png](figure_1_raw_gps_altitude_quality.png) / [figure_1_raw_gps_altitude_quality.svg](figure_1_raw_gps_altitude_quality.svg): GPS GGA 원본 고도, HDOP, 위성 수와 임시 하강 구간 |
| 2 | [figure_2_raw_gps_plan_track.png](figure_2_raw_gps_plan_track.png) / [figure_2_raw_gps_plan_track.svg](figure_2_raw_gps_plan_track.svg): 전체 GPS 수평 궤적과 선택한 구간 |
| 3 | [figure_3_raw_imu_angles.png](figure_3_raw_imu_angles.png) / [figure_3_raw_imu_angles.svg](figure_3_raw_imu_angles.svg): IMU 원본 3축 각도와 선택한 구간 |
| 4 | [figure_4_3d_descent_horizontal_drift.png](figure_4_3d_descent_horizontal_drift.png) / [figure_4_3d_descent_horizontal_drift.svg](figure_4_3d_descent_horizontal_drift.svg): 선택 구간의 3D GPS 궤적과 수평 이동 벡터 |
| 5 | [figure_5_smoothed_drift_profile.png](figure_5_smoothed_drift_profile.png) / [figure_5_smoothed_drift_profile.svg](figure_5_smoothed_drift_profile.svg): 평활화한 수평 이동 성분의 시간·GPS 고도별 분포 |
| 6 | [figure_6_local_3d_drift_cloud.png](figure_6_local_3d_drift_cloud.png) / [figure_6_local_3d_drift_cloud.svg](figure_6_local_3d_drift_cloud.svg): 관측 궤적 주변의 국소 3D 수평 이동 보간 |

생성 스크립트·분석용 CSV·실행 로그와 첫 그림 시안은 Git 제외 경로 `log/report-2026-11-04/`에 보존했다. 원본 `flight_test/`는 수정하지 않았다.
