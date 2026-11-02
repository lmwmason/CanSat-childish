# 바람장 기반 화재 확산 연구용 프로토타입

저장된 Child 하강 분석 샘플을 공간적 수평 바람장으로 보간하고, 지형·토지피복과 함께 Rothermel/Behave 지표화 시나리오에 넣어 지도에 도달 시간을 그린다. **연구용이며 실제 화재·대피·진화에 사용할 수 없다.**

## 실행

```bash
python3 -m venv fire_spread/.venv
fire_spread/.venv/bin/pip install -r fire_spread/requirements.txt
fire_spread/.venv/bin/python -m fire_spread
```

http://127.0.0.1:8766 을 열고 지상국이 저장한 `events.csv` 또는 `traffic.jsonl`을 선택한다. 프로그램이 GPS 관측을 추출하고 기존 windField 분석기로 수평 바람을 추정한다. 별도 wind_samples.csv 생성 단계나 실행 중인 지상국은 필요하지 않다. 서로 다른 세션 파일을 합치지 않는다. 지도에 관측점과 경계, 보간 바람 방향이 표시되면 경계 안의 발화점을 선택하고 계산한다. 지상국 관측 가져오기는 선택 기능이다. pyrothermel 빌드에 C++ 컴파일러가 필요할 수 있다. 인터넷과 외부 지도·CDN이 필요하며 조회한 지리 영역에 대한 요청은 자료 제공자에게 전달된다.

## 바람장과 제한

- 지상국 기록의 유효 GPS에 11초 위치 평활화와 하강 표본 선별을 적용한다. 계산된 `accepted=1` 표본 중 최신 표본 기준 60초 이내를 사용한다. `t_s`는 파일 내 상대시간이며 UTC로 간주하지 않는다. 서로 다른 Child를 포함한 파일은 거부한다. 선택적인 LIVE/REPLAY 입력은 현재 기준 최근 120초 이내이면서 최신 표본 기준 60초 이내를 사용한다.
- 샘플의 지역 동·북 좌표를 이용하여 각 화재 격자에 동·북 성분을 역거리 제곱 가중 평균한다. 3개 이상의 서로 다른 비일직선 위치가 필요하다. 관측점 볼록 껍질 바깥이나 가장 가까운 관측점에서 설정 거리 밖의 격자는 미계산이다. 발화점이 미계산 영역이면 계산을 중단한다. 비어 있거나 회색인 영역은 안전하다는 의미가 아니다.
- **서로 다른 GPS 고도의 관측을 수평면에 투영해 보간한다.** 이는 화염 높이의 지표풍이나 동시 3D 바람장이 아니다. 화면에는 사용한 관측의 고도 범위와 시간차를 표시한다. 고도 기준 및 지표풍 변환이 검증되지 않아 보정 계수는 가정이다. 좁거나 거의 직선인 한 Child 경로에서는 유효 영역이 매우 작거나 없을 수 있다.
- 수평 바람장은 선택한 시간의 정적인 근사로 계산 전체에 적용된다. 미래 바람의 변화·실시간 갱신·항력 지연 보정은 구현하지 않았다.

## 화재 모델과 제한

- Terrain Tiles 고도 차이에서 격자 경사·방향을 계산한다. WorldCover 2021의 수목/관목/초지·경작지를 TL8/SH1/GR1/GR1로 임시 매핑한다. 실제 수종·지표 연료를 확인한 결과가 아니다. 나머지는 미계산이다.
- 사연료 수분과 생연료 수분은 가정이며 기상 이력에서 자동 추정하지 않는다. 각 격자의 보간 바람과 경사, 연료를 Behave/Rothermel에 넣어 8방향 지표화 속도를 구하고 격자 최단 도달 시간을 계산한다. 색은 확률이 아닌 도달 시간 구간이다.
- 격자 방향 의존성이 있고 수관화·비화·진화 활동은 미구현이다. 실제 화재 및 기준 모델 비교 검증이 필요하다.

테스트: `fire_spread/.venv/bin/python -m unittest discover -s fire_spread/tests -v`.

자료: [Terrain Tiles](https://registry.opendata.aws/terrain-tiles/), [ESA WorldCover](https://esa-worldcover.org/en/data-access), [Pyrothermel](https://github.com/j-tenny/pyrothermel). © ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium.

기존 115번 자료의 관측 범위는 좁다. 5m 격자 시험에서 169칸 중 바람 지원 31칸, 화재 도달 계산 15칸이었다. 114번 자료는 시험한 관측 중심이 WorldCover 시가지로 분류되어 화재 연료가 없다고 처리된다. 작은 격자 간격을 선택해도 원본 지형·GPS의 실제 해상도가 개선되지는 않는다.

## 지형 바람장 계산 (WindNinja)

초기 설치는 Conda와 C++ 컴파일러가 있는 환경에서 `bash fire_spread/setup.sh`, 이후 실행은 `bash fire_spread/run.sh`를 사용한다. 전용 WindNinja 환경은 `.windninja/`, Python 환경은 `.venv/`에 설치되며 Git에서 제외된다. `WINDNINJA_CLI`로 다른 설치 경로도 지정할 수 있다.

화면의 기본 '고도별 관측 + 지형 바람 모델'은 관측 바람을 GPS 고도 10m 구간별로 동·북 성분 평균한다. 평균 관측 위치에서 DEM 지면을 빼고 사용자가 설정한 고도 기준 보정과 수관 높이를 적용해 WindNinja 관측 높이를 만든다. 유효 높이 2–500m 밖의 구간은 제외하고, 화면에 사용 구간/전체 구간 개수를 표시한다. 유효한 고도 구간이 2개 미만이면 계산을 중단하며 단일 벡터로 대체하지 않는다. GPS와 DEM의 수직 기준이 같고 관측 시간 동안 대기가 준정상이라는 가정은 검증되지 않았다. 보정값은 독립 고도 기준을 확인한 경우에만 설정해야 한다.

WindNinja 질량보존 모델은 이 고도별 입력점과 계산 영역 주변 최소 약 2km DEM을 사용한다. 거칠기 유형은 영역 전체에 동일하게 적용한다. 관측값 강제 일치 옵션은 끄며, 순차적으로 낙하하며 얻은 프로파일을 동시 지상 관측망으로 검증한 것은 아니다. 출력은 수관 위 2m의 30m 격자 바람이다. 코드에서 이 값을 화재 격자 위치에 읽어 Rothermel에 넣으며, 화염 높이 보정 계수는 별도 가정이다. 화재 격자가 5m여도 바람·지형의 원본 해상도가 5m가 되는 것은 아니다.

관측 경로 밖에도 모델 바람을 얻을 수 있지만 이는 직접 관측이나 검증된 풍속장이 아니다. 바람의 지형 영향과 고도 정보를 연결하는 연구용 전방 모델이다. '관측 범위 내 보간'도 선택 가능하며 이 모드에서는 기존의 관측 영역 제한이 유지된다. WindNinja 입력·DEM·설정·표준출력은 `log/fire-spread/windninja/`에 보존한다. 정적 입력에 엔진이 표기하는 실행 시각은 관측 시각을 뜻하지 않는다.

공식 근거: [WindNinja solver](https://ninjastorm.firelab.org/windninja/howdoes/solvers.html), [point initialization tutorial](https://ninjastorm.firelab.org/windninja/tutorials/WindNinja_tutorial3.pdf).

격자 상한은 100,000개이며 초과 시 예상 개수를 오류에 표시한다. 10만 개 근처에서는 외부 자료 조회·WindNinja·격자별 Rothermel 계산·브라우저 도형 표시 시간이 길어질 수 있다. 해당 규모의 성능은 아직 실측하지 않았다.
