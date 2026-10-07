# Child CanSat 바람 추정기

루트에서 실행하는 오프라인 분석기다. 현재 Child 펌웨어 CSV(8열)는 그대로 읽어 형식을 확인하지만, `lat`, `lon`이 없으면 바람 계산을 중단하고 이유를 알려 준다. 실제 GPS 데이터가 아직 없으므로, 재현 가능한 합성 비행으로 처리 경로를 검증할 수 있다.

## 실행

```bash
python3 -m pip install -r windField/requirements.txt
python3 -m windField demo --output-dir log/demo
python3 -m windField analyze child_with_gps.csv --output-dir log/flight-001
python3 -m unittest discover -s windField/tests -v
```

`demo`는 세 Child의 합성 GPS/기압 CSV, 생성에 사용한 참값과 조건, 계산 결과, CSV 프로파일, PNG 그림, 설정·입력 SHA-256·통계가 담긴 `analysis.json`을 지정한 `log/` 폴더에 저장한다. 결과 폴더를 다르게 지정하면 이전 실험을 덮어쓰지 않는다. `docs/`와 `log/`는 Git에서 제외된다.

`wind_field_3d.html`은 인터넷 연결 없이 브라우저에서 회전·확대할 수 있는 3D 공간 보기다. `wind_field_3d.png`는 정적 미리보기다. 동/북 위치와 고도가 3D 좌표이고, 화살표는 그 지점에서 추정한 **수평 바람**이다. 회색 화살표는 같은 고도 Child 관측점의 무게중심에서 역거리 가중 보간한 값이다. 파일 탐색기에서 HTML을 열거나 `xdg-open log/demo/wind_field_3d.html`을 실행하면 된다.

## 입력

현재 Child CSV 열을 유지하면서 아래 열을 추가한다.

| 필드 | 단위 | 의미 |
| --- | --- | --- |
| `child_id` | 문자열 | 여러 Child 구분, 생략 시 `child-1` |
| `t_s` | 초 | Child 기준 경과 시간, 필수 |
| `lat`, `lon` | 십진도 | Child의 GPS 위치, 필수 |
| `rel_alt_m` 또는 `alt_m` | m | 고도, 하나 필수 |
| `state` | 문자열 | `DESCENT`만 분석, 생략 가능 |
| `gps_valid` | 0/1 | GPS fix 유효성, 생략 가능 |
| `pressure_hPa`, `temp_C` | hPa, °C | 공기 밀도 추정용, 보정 계수 입력 시 필수 |

기존 `idx`, `humidity_pct`, `accel_g` 등은 읽을 수 있지만 바람 역산에는 쓰지 않는다. `accel_g`는 크기라 수평 가속도를 제공하지 않는다. 서로 다른 Child의 `t_s`를 결합해 시간별 바람을 비교하려면 추후 공통 시각도 기록해야 한다.

## 계산과 해석

1. 위경도를 첫 표본 기준 지역 동/북 미터 좌표로 바꾼다. GPS 고립 점프, fix 손실, 중복 시각, 하강 외 구간과 사출 직후를 거른다.
2. 위치를 시간 창에서 2차 다항식으로 평활화하고 미분한다. 기본 창은 7초다. 창 크기와 고도 분해능의 상충은 실제 GPS 오차로 조정해야 한다.
3. 기본 바람은 안정 하강 중 수평 이동 속도로 추정한다. 수평 중력은 0이고, 항력이 물체 속도를 바람에 수렴시킨다는 근사다.
4. 항력 지연 보정 후보 `w_h ≈ v_h + τ a_h`도 계산한다. `τ = |v_z|/g`는 종단 하강 가정이고, `--mass-kg`, `--cd`, `--area-m2`를 모두 입력하면 `τ = 2m/(ρ C_D A |v_z|)`을 사용하여 보정값을 주 결과로 선택한다. 미보정 기본값과 후보를 CSV에 모두 남긴다. 보정 계수가 실측되지 않았다면 후보를 정확한 결과로 간주하지 않는다.
5. 고도별 Child 표본을 묶고, 같은 고도에 세 Child 이상이 있을 때 **관측점들이 둘러싼 영역 안에서만** 역거리 가중 보간을 그린다. 컬러 화살표는 관측 기반, 회색 화살표는 보간값이다. 이는 고도별 수평 바람이며 3차원 바람의 수직 성분이 아니다.

`wind_samples.csv`의 `accepted=0`은 품질 기준에서 제외된 표본이다. `wind_to_deg`는 북쪽부터 시계 방향인 **바람이 향하는 방향**이다. 기상학의 풍향(불어오는 방향)이 필요하면 180°를 더해 360°로 나눈다.

합성 데이터의 오차 수치는 코드 동작 검증용이다. 실제 정확도는 위성 GPS와 낙하산/항력막이 준비된 뒤 기준 풍속계와 반복 낙하로 확인해야 한다.
