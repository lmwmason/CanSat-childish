import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from dataclasses import dataclass
import seaborn as sns
from typing import List, Tuple

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

@dataclass
class MossStructure:
    """이끼 구조물 데이터 클래스"""
    x: float
    y: float
    size: float
    humidity_boost: float  # 구조물이 주변에 더하는 습도(%)
    effective_radius: float  # 효과 반경(m)

@dataclass
class EnvironmentConditions:
    """특정 시간의 환경 조건 데이터 클래스"""
    temperature: float
    wind_speed: float
    wind_direction: float
    base_humidity: float # 이 값은 이제 각 케이스(base, moss, moss+archi)의 습도를 나타냄
    solar_radiation: float

class Simulation:
    def __init__(self, grid_size: int = 100, cell_size: float = 10.0):
        self.grid_size = grid_size
        self.cell_size = cell_size
        self.moss_structures: List[MossStructure] = []

        self.terrain = np.zeros((grid_size, grid_size))
        self.vegetation_density = np.ones((grid_size, grid_size)) * 0.5
        self.humidity_map = np.zeros((grid_size, grid_size))
        self.fire_risk_map = np.zeros((grid_size, grid_size))
        
        self.env: EnvironmentConditions = None

    def add_moss_structure(self, structure: MossStructure):
        self.moss_structures.append(structure)

    def calculate_humidity_effect(self):
        # env.base_humidity는 이미 시뮬레이션 케이스(base/moss/moss+archi)의 습도를 반영하므로,
        # 초기 맵은 해당 습도로 채워집니다.
        self.humidity_map.fill(self.env.base_humidity)

        # 이끼 구조물이 추가적인 부스트를 제공하는 경우에만 처리
        # (현재 시뮬레이션 방식에서는 add_moss_structure를 사용하지 않을 수도 있습니다)
        # 만약 humidity_boost가 0이 아닌 경우에만 아래 로직을 수행
        if self.moss_structures: # 이끼 구조물이 추가되어 있다면
            for moss in self.moss_structures:
                grid_x = int(moss.x / self.cell_size)
                grid_y = int(moss.y / self.cell_size)
                effect_radius_cells = int(moss.effective_radius / self.cell_size)

                current_humidity_boost = moss.humidity_boost

                for i in range(max(0, grid_x - effect_radius_cells), min(self.grid_size, grid_x + effect_radius_cells + 1)):
                    for j in range(max(0, grid_y - effect_radius_cells), min(self.grid_size, grid_y + effect_radius_cells + 1)):
                        distance = np.sqrt((i - grid_x)**2 + (j - grid_y)**2) * self.cell_size

                        if distance <= moss.effective_radius:
                            # 가우시안 분포
                            effect_strength = np.exp(-distance**2 / (2 * (moss.effective_radius / 3)**2))

                            wind_effect = 1.0 - min(0.5, self.env.wind_speed / 14.0) 
                            temp_effect = 1.0 - max(0, (self.env.temperature - 25) / 50.0) 

                            # 이미 base_humidity에 이끼 효과가 반영된 데이터를 사용하므로,
                            # humidity_boost를 0으로 설정하거나, 다른 방식으로 적용해야 함.
                            # 여기서는 experiment_humidity_data의 각 컬럼을 직접 사용하므로
                            # MossStructure의 humidity_boost는 더 이상 직접적으로 사용되지 않습니다.
                            # 대신 이끼 주변 지점의 습도를 가져오는 용도로만 사용됩니다.
                            # 따라서 humidity_increase는 0으로 설정하거나, 이 로직을 스킵해야 합니다.
                            # 가장 명확한 방법은 각 시나리오의 base_humidity를 해당 case의 값으로 직접 사용하는 것입니다.
                            pass # 이끼 효과는 base_humidity 자체에 이미 포함되었다고 가정

        # 습도 맵이 100%를 넘지 않도록 클리핑
        self.humidity_map = np.clip(self.humidity_map, 0, 100)

    def calculate_fire_risk(self):
        """
        FWI(산불 기상 지수) 개념을 기반으로 화재 위험도를 계산합니다.
        세수분 지수(FFMC)와 초기 확산 지수(ISI)의 개념을 반영합니다.
        """
        
        moisture_content_from_humidity = 100 - self.humidity_map 
        temp_drying_effect = np.clip((self.env.temperature - 0) / 50.0 * 50, 0, 50) 
        ffmc = np.clip(moisture_content_from_humidity * 0.7 + temp_drying_effect * 0.3, 0, 100) 
        ffmc_risk_contribution = ffmc / 100.0

        wind_speed_contribution = np.clip(self.env.wind_speed / 25.0, 0, 1)
        spread_risk = ffmc_risk_contribution * wind_speed_contribution
        
        self.fire_risk_map = np.clip(
            (ffmc_risk_contribution * 50) +
            (spread_risk * 40) +
            (self.vegetation_density * 10),
            0, 100
        )

    def run_time_series_simulation(self, hourly_data: pd.DataFrame, is_moss_scenario: bool = False):         
        results = []
        for hour, data in hourly_data.iterrows():
            self.env = EnvironmentConditions(
                temperature=data['temperature'],
                wind_speed=data['wind_speed'],
                wind_direction=data['wind_direction'],
                base_humidity=data['base_humidity'], # 이 부분이 중요: 각 케이스의 습도를 직접 사용
                solar_radiation=500
            )
            
            # calculate_humidity_effect는 이제 self.env.base_humidity를 사용하므로,
            # 추가적인 moss_structure의 humidity_boost는 여기서 반영하지 않습니다.
            # 즉, humidity_data.csv에 있는 case1, case2, case3 값이 이미 이끼 효과를 포함한 최종 습도라고 가정합니다.
            self.humidity_map.fill(self.env.base_humidity) 
            self.humidity_map = np.clip(self.humidity_map, 0, 100) # 클리핑

            self.calculate_fire_risk()
            
            # 이끼 주변 지점 (혹은 해당 시나리오를 대표하는 지점)의 결과 기록
            # is_moss_scenario가 True이고 moss_structures가 있다면 그 지점 사용, 아니면 중앙 지점
            if is_moss_scenario and len(self.moss_structures) > 0:
                point = (int(self.moss_structures[0].x / self.cell_size), int(self.moss_structures[0].y / self.cell_size))
            else: # 베이스라인 시나리오나 이끼 구조물이 없을 때
                point = (self.grid_size // 2, self.grid_size // 2)

            area_humidity = self.humidity_map[point]
            area_risk = self.fire_risk_map[point]

            # far_point는 항상 전체 맵의 대표값으로 사용
            far_point = (self.grid_size - 1, self.grid_size - 1) 
            far_area_humidity = self.humidity_map[far_point] # 여기도 해당 시나리오의 humidity_map에서 가져옴
            
            results.append({
                'hour': hour,
                'base_humidity_input': self.env.base_humidity, # 입력으로 사용된 humidity_data의 값
                'simulated_humidity': area_humidity, # 시뮬레이션으로 계산된 해당 지점의 습도
                'far_area_humidity': far_area_humidity,
                'simulated_risk': area_risk # 시뮬레이션으로 계산된 해당 지점의 위험도
            })
        
        return pd.DataFrame(results)

    def visualize_results(self, results_dict: dict, scenario_name: str = "기본"):
        fig, ax1 = plt.subplots(figsize=(14, 7))
        
        # 습도 변화 그래프 (왼쪽 y축)
        ax1.set_xlabel('시간 (Hour)', fontsize=14)
        ax1.set_ylabel('습도 (%)', fontsize=14, color='blue')
        
        # 기본 습도 (case1)
        ax1.plot(results_dict['case1_base_humi']['hour'], results_dict['case1_base_humi']['simulated_humidity'], 'k--', label='기본 습도 (Case 1)')
        
        # 이끼 적용 시 습도 (case2)
        ax1.plot(results_dict['case2_moss_only']['hour'], results_dict['case2_moss_only']['simulated_humidity'], 'b-', marker='o', label='이끼 적용 습도 (Case 2)')
        
        # 이끼+건축 적용 시 습도 (case3)
        ax1.plot(results_dict['case3_moss_archi']['hour'], results_dict['case3_moss_archi']['simulated_humidity'], 'g-', marker='s', label='이끼+건축 적용 습도 (Case 3)')

        ax1.tick_params(axis='y', labelcolor='blue')
        ax1.grid(True, axis='y', linestyle='--', alpha=0.6)

        # 화재 위험도 변화 그래프 (오른쪽 y축)
        ax2 = ax1.twinx()
        ax2.set_ylabel('화재 위험도', fontsize=14, color='red')
        
        # 기본 화재 위험도 (case1)
        ax2.plot(results_dict['case1_base_humi']['hour'], results_dict['case1_base_humi']['simulated_risk'], 'r--', label='기본 화재 위험도 (Case 1)')
        
        # 이끼 적용 시 화재 위험도 (case2)
        ax2.plot(results_dict['case2_moss_only']['hour'], results_dict['case2_moss_only']['simulated_risk'], 'm-', marker='o', label='이끼 적용 화재 위험도 (Case 2)')
        
        # 이끼+건축 적용 시 화재 위험도 (case3)
        ax2.plot(results_dict['case3_moss_archi']['hour'], results_dict['case3_moss_archi']['simulated_risk'], 'y-', marker='s', label='이끼+건축 적용 화재 위험도 (Case 3)')

        ax2.tick_params(axis='y', labelcolor='red')
        
        # 범례 합치기
        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax2.legend(lines + lines2, labels + labels2, loc='upper right', bbox_to_anchor=(1.0, 1.2))

        plt.title(f'시간에 따른 습도 및 화재 위험도 변화 ({scenario_name} 시나리오 - 3가지 케이스 비교)', fontsize=18)
        plt.xticks(np.arange(0, 24, 2))
        fig.tight_layout()
        plt.show()

if __name__ == "__main__":
    try:
        # humidity_data.csv에서 모든 컬럼을 사용
        experiment_humidity_data = pd.read_csv('./data/humidity_data.csv')
    except FileNotFoundError:
        print("Error: 'humidity_data.csv' not found. Please ensure the 'data' directory exists and contains the CSV file.")
        exit()

    # 여기서 humidity_boost_mean은 더 이상 직접적으로 사용되지 않습니다.
    # 각 케이스의 습도 값 자체가 시뮬레이션의 base_humidity로 사용됩니다.
    # 하지만 MossStructure는 여전히 필요하므로, 임의의 기본값을 설정하거나,
    # 해당 데이터가 제공하는 평균적인 부스트 값을 활용할 수 있습니다.
    # 여기서는 'case3 - case2'의 평균을 그대로 사용합니다.
    # 이는 '건축'이 추가적으로 제공하는 습도 부스트의 대략적인 값으로 해석될 수 있습니다.
    initial_humidity_boost_mean = (experiment_humidity_data['case3 (moss+archi) humi'] - experiment_humidity_data['case2 (moss) humi']).mean()
    if np.isnan(initial_humidity_boost_mean):
        initial_humidity_boost_mean = 5.0
        print("Humidity boost mean (case3-case2) is NaN, defaulting to 5.0 for MossStructure.")

    hours = np.arange(24)

    # 이끼 효과가 이미 포함된 데이터를 'base_humidity'로 직접 사용합니다.
    # 따라서, EnvironmentConditions의 'base_humidity'가 각 케이스의 핵심 입력이 됩니다.
    # MossStructure의 'humidity_boost'는 이 시뮬레이션에서는 더 이상 습도맵에 직접적인 '추가' 역할을 하지 않고,
    # 단순히 이끼 구조물의 존재를 나타내는 역할만 합니다 (즉, 해당 지점의 값을 추출하는 용도).
    # 따라서 각 시뮬레이션에서 add_moss_structure는 그대로 유지하되,
    # 그 효과는 humidity_data.csv의 해당 케이스 컬럼에 이미 반영되었다고 해석합니다.
    
    # 환경 시나리오 (온도, 풍속, 바람 방향은 그대로 유지)
    # 각 시나리오별로 humidity_data의 각 case를 대입하여 시뮬레이션을 실행합니다.
    scenarios = {
        "기본": {
            'temperature_factor': 1.0, 'wind_speed_factor': 1.0, 'wind_direction_func': lambda h: np.ones_like(h) * 180
        },
        "고온": {
            'temperature_factor': 1.5, 'wind_speed_factor': 1.0, 'wind_direction_func': lambda h: np.ones_like(h) * 180
        },
        "저온": {
            'temperature_factor': 0.5, 'wind_speed_factor': 1.0, 'wind_direction_func': lambda h: np.ones_like(h) * 180
        },
        "강풍": {
            'temperature_factor': 1.0, 'wind_speed_factor': 2.0, 'wind_direction_func': lambda h: np.ones_like(h) * 180
        },
        "약풍": {
            'temperature_factor': 1.0, 'wind_speed_factor': 0.4, 'wind_direction_func': lambda h: np.ones_like(h) * 180
        }
        # "다방향 바람"은 humidity_effect 계산에 직접 영향 주지 않으므로 제외하거나,
        # 위험도 계산에 풍향을 반영하는 FWI 공식 부분을 추가해야 의미가 있습니다.
        # '다방향 바람': {
        #     'temperature_factor': 1.0, 'wind_speed_factor': 1.0, 'wind_direction_func': lambda h: (h * 15 % 360)
        # }
    }

    all_scenario_comparison_results = {}

    for scenario_name, factors in scenarios.items():
        print(f"\n--- 시나리오: {scenario_name} 시작 ---")

        # 시간별 온도, 풍속, 바람 방향 데이터 생성
        temp_base = 15 + 15 * np.cos(np.pi * (hours - 4) / 12)
        wind_speed_base = 5 + 5 * np.sin(np.pi * (hours - 8) / 12)

        scenario_temperature = temp_base * factors['temperature_factor']
        scenario_wind_speed = wind_speed_base * factors['wind_speed_factor']
        scenario_wind_direction = factors['wind_direction_func'](hours)

        scenario_results = {}

        # Case 1: 기본 (base) 습도 데이터로 시뮬레이션
        print(f"=== Case 1 (기본) 시뮬레이션 시작 ({scenario_name}) ===")
        hourly_data_case1 = pd.DataFrame({
            'base_humidity': experiment_humidity_data['case1 (base) humi'],
            'temperature': scenario_temperature,
            'wind_speed': scenario_wind_speed,
            'wind_direction': scenario_wind_direction
        }, index=hours)
        sim_case1 = Simulation(grid_size=100, cell_size=10.0)
        # Case 1은 구조물이 없으므로 add_moss_structure 호출 안 함 (시뮬레이션 내부 로직으로 중앙 지점 사용)
        results_case1 = sim_case1.run_time_series_simulation(hourly_data_case1, is_moss_scenario=False)
        scenario_results['case1_base_humi'] = results_case1
        print(f"=== Case 1 (기본) 시뮬레이션 완료 ({scenario_name}) ===")

        # Case 2: 이끼만 적용 (moss) 습도 데이터로 시뮬레이션
        print(f"=== Case 2 (이끼 적용) 시뮬레이션 시작 ({scenario_name}) ===")
        hourly_data_case2 = pd.DataFrame({
            'base_humidity': experiment_humidity_data['case2 (moss) humi'],
            'temperature': scenario_temperature,
            'wind_speed': scenario_wind_speed,
            'wind_direction': scenario_wind_direction
        }, index=hours)
        sim_case2 = Simulation(grid_size=100, cell_size=10.0)
        # 이끼 구조물은 추가하되, humidity_boost는 더 이상 습도맵에 직접 영향을 주지 않음
        # 단지 시뮬레이션 내부에서 이끼 주변 지점을 식별하는 용도로 활용
        sim_case2.add_moss_structure(MossStructure(
            x=500, y=500, size=30, 
            humidity_boost=0.0, # 여기서는 의미 없는 값으로 설정 (습도맵에 직접 추가 안함)
            effective_radius=60.0
        ))
        results_case2 = sim_case2.run_time_series_simulation(hourly_data_case2, is_moss_scenario=True)
        scenario_results['case2_moss_only'] = results_case2
        print(f"=== Case 2 (이끼 적용) 시뮬레이션 완료 ({scenario_name}) ===")

        # Case 3: 이끼 + 건축 적용 (moss+archi) 습도 데이터로 시뮬레이션
        print(f"=== Case 3 (이끼+건축 적용) 시뮬레이션 시작 ({scenario_name}) ===")
        hourly_data_case3 = pd.DataFrame({
            'base_humidity': experiment_humidity_data['case3 (moss+archi) humi'],
            'temperature': scenario_temperature,
            'wind_speed': scenario_wind_speed,
            'wind_direction': scenario_wind_direction
        }, index=hours)
        sim_case3 = Simulation(grid_size=100, cell_size=10.0)
        # 이끼 구조물은 추가하되, humidity_boost는 더 이상 습도맵에 직접 영향을 주지 않음
        sim_case3.add_moss_structure(MossStructure(
            x=500, y=500, size=30, 
            humidity_boost=0.0, # 여기서는 의미 없는 값으로 설정
            effective_radius=60.0
        ))
        results_case3 = sim_case3.run_time_series_simulation(hourly_data_case3, is_moss_scenario=True)
        scenario_results['case3_moss_archi'] = results_case3
        print(f"=== Case 3 (이끼+건축 적용) 시뮬레이션 완료 ({scenario_name}) ===")

        # 결과 시각화
        # visualize_results 함수에 시나리오별 결과 딕셔너리 전달
        sim_case1.visualize_results(scenario_results, scenario_name) # sim_case1 객체 사용 (어떤 sim 객체든 상관 없음)

        # 하루 평균 위험도 감소량 계산 및 출력
        avg_risk_case1 = results_case1['simulated_risk'].mean()
        avg_risk_case2 = results_case2['simulated_risk'].mean()
        avg_risk_case3 = results_case3['simulated_risk'].mean()

        reduction_case2_vs_case1 = avg_risk_case1 - avg_risk_case2
        reduction_case3_vs_case1 = avg_risk_case1 - avg_risk_case3
        reduction_case3_vs_case2 = avg_risk_case2 - avg_risk_case3


        all_scenario_comparison_results[scenario_name] = {
            'avg_risk_case1': avg_risk_case1,
            'avg_risk_case2': avg_risk_case2,
            'avg_risk_case3': avg_risk_case3,
            'reduction_case2_vs_case1': reduction_case2_vs_case1,
            'reduction_case3_vs_case1': reduction_case3_vs_case1,
            'reduction_case3_vs_case2': reduction_case3_vs_case2
        }

        print(f"\n=== {scenario_name} 시나리오: 하루 평균 화재 위험도 감소량 분석 ===")
        print(f"Case 1 (기본) 하루 평균 화재 위험도: {avg_risk_case1:.4f}")
        print(f"Case 2 (이끼 적용) 하루 평균 화재 위험도: {avg_risk_case2:.4f}")
        print(f"Case 3 (이끼+건축 적용) 하루 평균 화재 위험도: {avg_risk_case3:.4f}")
        print(f"  > Case 2 vs Case 1 감소량: {reduction_case2_vs_case1:.4f}")
        print(f"  > Case 3 vs Case 1 감소량: {reduction_case3_vs_case1:.4f}")
        print(f"  > Case 3 vs Case 2 감소량: {reduction_case3_vs_case2:.4f}")


        import os
        output_dir = './data'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        results_case1.to_csv(f'{output_dir}/simulation_results_{scenario_name}_case1_base.csv', index=False)
        results_case2.to_csv(f'{output_dir}/simulation_results_{scenario_name}_case2_moss_only.csv', index=False)
        results_case3.to_csv(f'{output_dir}/simulation_results_{scenario_name}_case3_moss_archi.csv', index=False)
        print(f"=== 시나리오: {scenario_name} 완료 ===\n")

    print("\n\n####################################################")
    print("### 모든 시나리오별 하루 평균 화재 위험도 비교 요약 ###")
    print("####################################################")
    for scenario, data in all_scenario_comparison_results.items():
        print(f"\n=== 시나리오: {scenario} ===")
        print(f"  Case 1 (기본) 평균 위험도: {data['avg_risk_case1']:.4f}")
        print(f"  Case 2 (이끼 적용) 평균 위험도: {data['avg_risk_case2']:.4f}")
        print(f"  Case 3 (이끼+건축 적용) 평균 위험도: {data['avg_risk_case3']:.4f}")
        print(f"  **Case 2 vs Case 1 감소량**: {data['reduction_case2_vs_case1']:.4f}")
        print(f"  **Case 3 vs Case 1 감소량**: {data['reduction_case3_vs_case1']:.4f}")
        print(f"  **Case 3 vs Case 2 감소량**: {data['reduction_case3_vs_case2']:.4f}")