import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from dataclasses import dataclass
import seaborn as sns
from typing import List, Tuple

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

@dataclass
class Boost:
    x: float
    y: float
    size: float
    humidity_boost: float
    effective_radius: float

@dataclass
class EnvironmentConditions:
    temperature: float
    wind_speed: float
    wind_direction: float
    base_humidity: float
    solar_radiation: float

class Simulation:
    def __init__(self, grid_size: int = 100, cell_size: float = 10.0):
        self.grid_size = grid_size
        self.cell_size = cell_size
        self.structures: List[Boost] = []
        self.moss: List[Boost] = []

        self.terrain = np.zeros((grid_size, grid_size))
        self.vegetation_density = np.ones((grid_size, grid_size)) * 0.5
        self.humidity_map = np.zeros((grid_size, grid_size))
        self.fire_risk_map = np.zeros((grid_size, grid_size))
        
        self.env: EnvironmentConditions = None

    def add_structure(self, structure: Boost):
        self.structures.append(structure)

    def add_moss(self, moss: Boost):
        self.moss.append(moss)

    def calculate_humidity_effect(self):
        self.humidity_map.fill(self.env.base_humidity)

        for structure in self.structures:
            grid_x = int(structure.x / self.cell_size)
            grid_y = int(structure.y / self.cell_size)
            effect_radius_cells = int(structure.effective_radius / self.cell_size)

            current_humidity_boost = structure.humidity_boost

            for i in range(max(0, grid_x - effect_radius_cells), min(self.grid_size, grid_x + effect_radius_cells + 1)):
                for j in range(max(0, grid_y - effect_radius_cells), min(self.grid_size, grid_y + effect_radius_cells + 1)):
                    distance = np.sqrt((i - grid_x)**2 + (j - grid_y)**2) * self.cell_size

                    if distance <= structure.effective_radius:
                        # 가우시안 분포
                        effect_strength = np.exp(-distance**2 / (2 * (structure.effective_radius / 3)**2))

                        wind_effect = 1.0 - min(0.5, self.env.wind_speed / 14.0) 
                        temp_effect = 1.0 - max(0, (self.env.temperature - 25) / 50.0) 

                        humidity_increase = current_humidity_boost * effect_strength * wind_effect * temp_effect
                        
                        self.humidity_map[i, j] += humidity_increase
        
        # 습도 맵이 100%를 넘지 않도록 클리핑
        self.humidity_map = np.clip(self.humidity_map, 0, 100)

    def calculate_fire_risk(self):
        """
        FWI(산불 기상 지수) 개념을 기반으로 화재 위험도를 계산합니다.
        세수분 지수(FFMC)와 초기 확산 지수(ISI)의 개념을 반영합니다.
        """
        
        # 1. 세수분 지수 (FFMC) 개념
        # FFMC는 연료의 건조도와 가연성을 나타냅니다.
        # 온도가 높을수록, 습도가 낮을수록 FFMC는 높아져 위험합니다.
        # FFMC는 0-100 사이의 값으로 스케일링하여 사용합니다. (가상의 값 범위)
        # 구조물로 인한 지역 습도(self.humidity_map)를 사용하여 FFMC를 계산합니다.
        
        # 습도에 따른 수분 함량 (높은 습도 = 높은 수분 함량 = 낮은 위험)
        # 0% 습도일 때 최대 건조, 100% 습도일 때 최소 건조 (최대값 100, 최소값 0)
        moisture_content_from_humidity = 100 - self.humidity_map 
        
        # 온도에 따른 건조 가속 (높은 온도 = 더 건조해짐)
        # 0도일 때 0, 50도일 때 50 정도의 영향을 준다고 가정
        temp_drying_effect = np.clip((self.env.temperature - 0) / 50.0 * 50, 0, 50) 
        
        # FFMC는 대략적으로 (습도에 따른 건조도 + 온도에 따른 건조 가속)으로 생각할 수 있습니다.
        # 여기서 최종 FFMC 값은 0-100 사이로 정규화합니다.
        # (온도 효과는 습도 효과에 비해 상대적으로 작게 반영)
        ffmc = np.clip(moisture_content_from_humidity * 0.7 + temp_drying_effect * 0.3, 0, 100) 
        
        # FFMC가 높을수록 연료가 더 건조하여 화재 위험이 높습니다.
        # FFMC를 0-1 사이의 위험 기여도로 변환 (예: 0 -> 0, 100 -> 1)
        ffmc_risk_contribution = ffmc / 100.0

        # 2. 초기 확산 지수 (ISI) 개념
        # ISI는 FFMC와 풍속을 결합하여 초기 화재 확산 속도를 나타냅니다.
        # FFMC가 높을수록, 풍속이 강할수록 ISI는 높아져 위험합니다.
        # 여기서는 ISI가 아닌, ISI가 화재 위험에 기여하는 정도를 바로 계산합니다.
        
        # 풍속에 따른 확산 기여도 (0-1 사이로 정규화, 최대 풍속 25m/s 기준)
        wind_speed_contribution = np.clip(self.env.wind_speed / 25.0, 0, 1)

        # ISI 개념을 반영한 확산 위험: FFMC 위험 기여도와 풍속 기여도를 곱하거나 합산
        # 여기서는 곱하는 방식을 사용하여 둘 다 높을 때 위험이 급격히 증가하도록 합니다.
        spread_risk = ffmc_risk_contribution * wind_speed_contribution

        # 3. 최종 화재 위험도 계산 (0-100 스케일)
        # FFMC 기반의 연료 가연성(ffmc_risk_contribution)과
        # ISI 개념을 반영한 확산 위험(spread_risk)을 종합하여 최종 위험도를 산정합니다.
        # 식생 밀도(self.vegetation_density)도 추가적인 위험 요소로 반영합니다.
        
        # 가연성과 확산 위험에 더 큰 가중치를 부여
        # 식생 밀도는 고정값이므로 전체적인 베이스 라인 위험도에 기여
        
        self.fire_risk_map = np.clip(
            (ffmc_risk_contribution * 50) +
            (spread_risk * 40) +
            (self.vegetation_density * 10),
            0, 100
        )


    def run_time_series_simulation(self, hourly_data: pd.DataFrame):         
        results = []
        for hour, data in hourly_data.iterrows():
            self.env = EnvironmentConditions(
                temperature=data['temperature'],
                wind_speed=data['wind_speed'],
                wind_direction=data['wind_direction'],
                base_humidity=data['base_humidity'],
                solar_radiation=500 # 예시 값
            )
            
            self.calculate_humidity_effect() 
            self.calculate_fire_risk()
            
            if len(self.structures) > 0:
                structure_point = (int(self.structures[0].x / self.cell_size), int(self.structures[0].y / self.cell_size))
                structure_area_humidity = self.humidity_map[structure_point]
                structure_area_risk = self.fire_risk_map[structure_point]
            else:
                center_point = (self.grid_size // 2, self.grid_size // 2)
                structure_area_humidity = self.humidity_map[center_point] 
                structure_area_risk = self.fire_risk_map[center_point] 

            far_point = (self.grid_size - 1, self.grid_size - 1) 
            far_area_humidity = self.humidity_map[far_point]
            
            results.append({
                'hour': hour,
                'base_humidity': self.env.base_humidity,
                'structure_area_humidity': structure_area_humidity,
                'far_area_humidity': far_area_humidity,
                'structure_area_risk': structure_area_risk
            })
        
        return pd.DataFrame(results)

    def visualize_results(self, results_with_structure_df: pd.DataFrame, results_without_structure_df: pd.DataFrame, scenario_name: str = "기본"):
        fig, ax1 = plt.subplots(figsize=(14, 7))
        
        # 습도 변화 그래프 (왼쪽 y축)
        ax1.set_xlabel('시간 (Hour)', fontsize=14)
        ax1.set_ylabel('습도 (%)', fontsize=14, color='blue')
        ax1.plot(results_with_structure_df['hour'], results_with_structure_df['base_humidity'], 'k--', label='기본 습도')
        
        # 구조물 적용 시 습도
        ax1.plot(results_with_structure_df['hour'], results_with_structure_df['structure_area_humidity'], 'b-', marker='o', label='구조물 주변 습도 (구조물 적용)')
        ax1.plot(results_with_structure_df['hour'], results_with_structure_df['far_area_humidity'], 'g:', label='구조물 없는 곳 습도 (구조물 적용)')

        # 이끼 적용 시 습도
        ax1.plot(results_without_structure_df['hour'], results_without_structure_df['structure_area_humidity'], 'c--', linestyle='--', marker='x', label='구조물 없는 곳 습도 (이끼 적용)') 

        ax1.tick_params(axis='y', labelcolor='blue')
        ax1.grid(True, axis='y', linestyle='--', alpha=0.6)

        # 화재 위험도 변화 그래프 (오른쪽 y축)
        ax2 = ax1.twinx()
        ax2.set_ylabel('화재 위험도', fontsize=14, color='red')
        
        # 구조물 적용 시 화재 위험도
        ax2.plot(results_with_structure_df['hour'], results_with_structure_df['structure_area_risk'], 'r-', marker='s', label='구조물 주변 화재 위험도 (구조물 적용)')

        # 이끼 적용 시 화재 위험도
        ax2.plot(results_without_structure_df['hour'], results_without_structure_df['structure_area_risk'], 'm--', marker='P', label='구조물 없는 곳 화재 위험도 (이끼 적용)') 

        ax2.tick_params(axis='y', labelcolor='red')
        
        # 범례 합치기
        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax2.legend(lines + lines2, labels + labels2, loc='upper right', bbox_to_anchor=(1.0, 1.15))

        plt.title(f'시간에 따른 습도 및 화재 위험도 변화 ({scenario_name} 시나리오 - 고정 습도 부스트)', fontsize=18)
        plt.xticks(np.arange(0, 24, 2))
        fig.tight_layout()
        plt.show()

if __name__ == "__main__":
    try:
        experiment_humidity_data = pd.read_csv('./data/humidity_data.csv')
    except FileNotFoundError:
        print("Error: 'experiment_humidity_data.csv' not found. Please ensure the 'data' directory exists and contains the CSV file.")
        exit()

    experiment_humidity_data['humidity_boost_structure'] = experiment_humidity_data['case3 (moss+archi) humi'] - experiment_humidity_data['case1 (base) humi']
    experiment_humidity_data['humidity_boost_moss'] = experiment_humidity_data['case3 (moss+archi) humi'] - experiment_humidity_data['case1 (base) humi']
    humidity_boost_structure_mean = experiment_humidity_data['humidity_boost_structure'].mean()
    humidity_boost_moss_mean = experiment_humidity_data['humidity_boost_moss'].mean()
    if np.isnan(humidity_boost_structure_mean):
        print("humidity_boost_structure_mean is nan!")
        exit()
    if np.isnan(humidity_boost_moss_mean):
        print("humidity_boost_moss_mean is nan")
        exit()
    
    hours = np.arange(24)

    scenarios = {
        "기본": {
            'base_humidity': 55 - 25 * np.cos(np.pi * (hours - 4) / 12),
            'temperature': 15 + 15 * np.cos(np.pi * (hours - 4) / 12),
            'wind_speed': 5 + 5 * np.sin(np.pi * (hours - 8) / 12),
            'wind_direction': np.ones_like(hours) * 180 # 고정된 바람 방향
        },
        "고온": {
            'base_humidity': 50 - 20 * np.cos(np.pi * (hours - 4) / 12), # 고온 시 습도 낮춤
            'temperature': 25 + 15 * np.cos(np.pi * (hours - 4) / 12), # 온도를 높임
            'wind_speed': 5 + 5 * np.sin(np.pi * (hours - 8) / 12),
            'wind_direction': np.ones_like(hours) * 180
        },
        "저온": {
            'base_humidity': 60 - 20 * np.cos(np.pi * (hours - 4) / 12), # 저온 시 습도 높임
            'temperature': 5 + 15 * np.cos(np.pi * (hours - 4) / 12), # 온도를 낮춤
            'wind_speed': 5 + 5 * np.sin(np.pi * (hours - 8) / 12),
            'wind_direction': np.ones_like(hours) * 180
        },
        "강풍": {
            'base_humidity': 55 - 25 * np.cos(np.pi * (hours - 4) / 12),
            'temperature': 15 + 15 * np.cos(np.pi * (hours - 4) / 12),
            'wind_speed': 10 + 8 * np.sin(np.pi * (hours - 8) / 12), # 풍속을 높임
            'wind_direction': np.ones_like(hours) * 180
        },
        "약풍": {
            'base_humidity': 55 - 25 * np.cos(np.pi * (hours - 4) / 12),
            'temperature': 15 + 15 * np.cos(np.pi * (hours - 4) / 12),
            'wind_speed': 2 + 2 * np.sin(np.pi * (hours - 8) / 12), # 풍속을 낮춤
            'wind_direction': np.ones_like(hours) * 180
        }
    }

    all_scenario_results = {}

    for scenario_name, params in scenarios.items():
        print(f"\n=== 시나리오: {scenario_name} 시작 ===")
        hourly_data = pd.DataFrame(params, index=hours)

        # 구조물 적용
        print(f"=== 구조물 적용 시뮬레이션 시작 ({scenario_name}) ===")
        sim_with_structure = Simulation(grid_size=100, cell_size=10.0)
        sim_with_structure.add_structure(Boost(
            x=500, y=500, size=30, 
            humidity_boost=humidity_boost_structure_mean,
            effective_radius=60.0
        ))
        print(f"💧 구조물 추가 완료: 습도 +{sim_with_structure.structures[0].humidity_boost:.2f}%, 효과 반경 {sim_with_structure.structures[0].effective_radius}m")
        simulation_results_with_structure = sim_with_structure.run_time_series_simulation(hourly_data)
        print(f"=== 구조물 적용 시뮬레이션 완료 ({scenario_name}) ===")

        # 이끼 적용
        print(f"=== 이끼 적용 시뮬레이션 시작 ({scenario_name}) ===")
        sim_without_structure = Simulation(grid_size=100, cell_size=10.0)
        simulation_results_without_structure = sim_without_structure.run_time_series_simulation(hourly_data)
        print(f"=== 이끼 적용 시뮬레이션 완료 ({scenario_name}) ===")

        # 결과 시각화
        sim_with_structure.visualize_results(simulation_results_with_structure, simulation_results_without_structure, scenario_name)

        # 하루 평균 위험도 감소량 계산 및 출력
        avg_risk_with_structure = simulation_results_with_structure['structure_area_risk'].mean()
        avg_risk_without_structure = simulation_results_without_structure['structure_area_risk'].mean()
        risk_reduction = avg_risk_without_structure - avg_risk_with_structure

        all_scenario_results[scenario_name] = {
            'avg_risk_with_structure': avg_risk_with_structure,
            'avg_risk_without_structure': avg_risk_without_structure,
            'risk_reduction': risk_reduction
        }

        print(f"\n=== {scenario_name} 시나리오: 하루 평균 화재 위험도 감소량 분석 ===")
        print(f"구조물 적용 시 하루 평균 화재 위험도: {avg_risk_with_structure:.4f}")
        print(f"이끼 적용 시 하루 평균 화재 위험도: {avg_risk_without_structure:.4f}")
        print(f"구조물 적용으로 인한 하루 평균 화재 위험도 감소량: {risk_reduction:.4f}")

        import os
        output_dir = './data'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        simulation_results_with_structure.to_csv(f'{output_dir}/simulation_results_{scenario_name}_with_structure_fixed_boost.csv', index=False)
        simulation_results_without_structure.to_csv(f'{output_dir}/simulation_results_{scenario_name}_without_structure_fixed_boost.csv', index=False)
        print(f"=== 시나리오: {scenario_name} 완료 ===\n")

    print("\n\n############################################")
    print("### 모든 시나리오별 하루 평균 화재 위험도 감소량 요약 ###")
    print("############################################")
    for scenario, data in all_scenario_results.items():
        print(f"\n=== 시나리오: {scenario} ===")
        print(f"구조물 적용 시 평균 위험도: {data['avg_risk_with_structure']:.4f}")
        print(f"이끼 적용 시 평균 위험도: {data['avg_risk_without_structure']:.4f}")
        print(f"**감소량**: {data['risk_reduction']:.4f}")