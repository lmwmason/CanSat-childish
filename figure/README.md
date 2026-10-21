# 보고서용 그림

2026-10-21 제공 CSV에서 만든 그림 6종이다. 각 그림은 인쇄용 PNG(300 dpi)와 편집 가능한 SVG로 제공한다. 파일 이름의 숫자 순서대로 보고서에 배치할 수 있다.

| 번호 | PNG / SVG 공통 파일명 | 내용 |
| --- | --- | --- |
| 1 | `figure_1_tracks_and_wind_profile` | 세 Child의 수평 궤적과 고도별 풍속 추정 |
| 2 | `figure_2_wind_vectors_3d` | 3D 궤적 위 선택 고도의 수평 바람 벡터 |
| 3 | `figure_3_wind_slice_22m` | 지상 22.5 m 수평 절편과 관측점 내부 보간 |
| 4 | `figure_4_raw_child_gps` | Child 원시 GPS 고도·수평 속도 |
| 5 | `figure_5_raw_gps_quality` | Child 원시 GPS 수신 위성 수·HDOP |
| 6 | `figure_6_raw_parent_imu_servo` | 모위성 원시 IMU 가속도 크기·서보 각도 |

그림 1–3은 사출 직후 3초를 제외하고 5초 위치 평활화를 적용한 **추정 결과**다. 그림 4–6은 원본 CSV의 기록값을 **평활화 없이** 표시한다. 그림 4–5의 Child CSV는 10 Hz 기록에 5 Hz GPS 값이 반복된다. 그림 6의 시간축은 모위성 로컬 `ms`를 `events.json`의 시계 정보로 환산했다.

자료 출처는 `cansat_fake_data/clean/`이다. 제공된 `README.md`와 생성 스크립트는 이 자료를 생성 데이터로 설명한다. 그림 내부에는 자료 성격을 단정하는 문구를 넣지 않았으며, 실제 기체의 실측 정확도로 인용하려면 출처와 기준 계측을 별도로 확인해야 한다.

상세 그림 설명, 처리 설정, 원본 해시, 실행 기록과 이전 레이아웃 시도는 Git 제외 폴더인 `log/report-2026-10-21/`에 있다.
