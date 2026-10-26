# 2026-10-26 Child GPS 분석 그림

`data_20261026/`의 GoPro GPS CSV 세 파일을 각각 별도의 Child 낙하 시험으로 처리한 결과다. 이전 `figure/`와 분리했다. 모든 그림은 **300 dpi PNG와 SVG** 한 쌍으로 저장했다. 원본 CSV는 수정하지 않았다.

| 번호 | 파일 이름 (`.png` / `.svg`) | 보고서에서 보여주는 내용 |
| --- | --- | --- |
| 1 | `figure_1_gps_plan_tracks` | 전체 수평 궤적과 임시 하강 선택 구간 |
| 2 | `figure_2_gps_altitude_and_descent_selection` | GPS 원본 고도와 하강 시작·끝 후보 |
| 3 | `figure_3_gps_reported_speed` | GPS에 기록된 2D·3D 속도 |
| 4 | `figure_4_candidate_descent_tracks_3d` | 선택된 세 하강 궤적의 3D 위치 |
| 5 | `figure_5_smoothed_horizontal_drift_components` | 11초 평활화 위치에서 계산한 동·북 이동 속도 |
| 6 | `figure_6_independent_descent_mean_drift` | 서로 다른 세 시험의 평균 수평 이동 벡터 |
| 7 | `figure_7_speed_method_comparison` | 위치 미분 속도와 GPS 기록 속도 비교 |
| 8 | `figure_8_gps_speed_change_event_hint` | GPS 속도 변화율을 이용한 사출 시각 단서 |
| 9 | `figure_9_gps_precision_field` | 원본 `precision` 필드의 시간 변화 |
| 10 | `figure_10_3d_drift_speed_at_observations` | 3D 관측 위치에서의 수평 이동 속도 색상 표시 |

보고서용 [분석 방법](METHODS.md)과 [그림 설명](CAPTIONS.md)을 함께 둔다.

## 현재 해석

세 기록은 **서로 다른 시각**에 시작한다. GPS 고도의 최대 연속 하락을 이용해 하강 구간을 임시 선택했다. 아래 속도는 그 구간의 **Child 수평 이동 대리지표**이며 기준 풍속계로 검증된 바람값이 아니다.

| 기록 | 하강 후보 (KST, 10월 26일) | 평균 동쪽 (m/s) | 평균 북쪽 (m/s) | 평균 벡터 크기 (m/s) |
| --- | --- | ---: | ---: | ---: |
| 114 | 08:02:10–08:02:31 | +0.02 | −0.39 | 0.39 |
| 115 | 08:06:42–08:07:30 | −2.23 | +1.05 | 2.47 |
| 116 | 08:13:12–08:14:05 | −1.62 | +1.11 | 1.96 |

기록 115는 GPS 원본 고도가 **−80.9 m**까지 내려간다. 같은 장소의 다른 기록과 차이가 커서 이 값을 실제 지상 기준 높이로 해석하거나 세 시험의 고도별 바람장을 합치지 않았다. 또한 위치 미분 속도와 GPS 기록 속도의 차이가 있으므로 절대 풍속 정확도는 제시하지 않는다.

분석 설정·원본 SHA-256·선택 시각·민감도·실행 로그는 Git 제외 경로 `log/report-2026-10-26/`에 보존했다. 원본 폴더 `data_20261026/`는 현재 사용자 제공 자료로 그대로 둔다.
