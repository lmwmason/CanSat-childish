import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from dataclasses import dataclass
import seaborn as sns
from typing import List, Tuple

# 글꼴 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

@dataclass
class MossStructure:
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
        self.moss_structures: List[MossStructure] = []

        self.terrain = np.zeros((grid_size, grid_size))
        self.vegetation_density = np.ones((grid_size, grid_size)) * 0.5
        self.humidity_map = np.zeros((grid_size, grid_size))
        self.fire_risk_map = np.zeros((grid_size, grid_size))
        
        self.env: EnvironmentConditions = None

    def add_moss_structure(self, structure: MossStructure):
        self.moss_structures.append(structure)

    def calculate_humidity_effect(self):
        self.humidity_map.fill(self.env.base_humidity)

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

                        humidity_increase = current_humidity_boost * effect_strength * wind_effect * temp_effect
                        
                        self.humidity_map[i, j] += humidity_increase
        
        # 습도 맵이 100%를 넘지 않도록 클리핑
        self.humidity_map = np.clip(self.humidity_map, 0, 100)

    def calculate_fire_risk(self):        
        # 습도에 따른 수분 함량 계산
        moisture_content_from_humidity = 100 - self.humidity_map
        
        temp_drying_effect = np.clip((self.env.temperature - 0) / 50.0 * 50, 0, 50) 
        
        # FFMC 계산
        ffmc = np.clip(moisture_content_from_humidity * 0.7 + temp_drying_effect * 0.3, 0, 100) 
        
        ffmc_risk_contribution = ffmc / 100.0

        # 풍속에 따른 확산 기여도
        wind_speed_contribution = np.clip(self.env.wind_speed / 25.0, 0, 1)

        # ISI를 반영한 확산 위험 계산
        spread_risk = ffmc_risk_contribution * wind_speed_contribution
        
        # 화재 위험도가 100을 넘지 않도록 클리핑
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
            
            if len(self.moss_structures) > 0:
                moss_point = (int(self.moss_structures[0].x / self.cell_size), int(self.moss_structures[0].y / self.cell_size))
                moss_area_humidity = self.humidity_map[moss_point]
                moss_area_risk = self.fire_risk_map[moss_point]
            else:
                center_point = (self.grid_size // 2, self.grid_size // 2)
                moss_area_humidity = self.humidity_map[center_point] 
                moss_area_risk = self.fire_risk_map[center_point] 

            far_point = (self.grid_size - 1, self.grid_size - 1) 
            far_area_humidity = self.humidity_map[far_point]
            
            results.append({
                'hour': hour,
                'base_humidity': self.env.base_humidity,
                'moss_area_humidity': moss_area_humidity,
                'far_area_humidity': far_area_humidity,
                'moss_area_risk': moss_area_risk
            })
        
        return pd.DataFrame(results)

    def visualize_results(self, results_with_structure_df: pd.DataFrame, results_with_moss_df: pd.DataFrame, scenario_name: str = "기본"):
        fig, ax1 = plt.subplots(figsize=(14, 7))
        
        # 습도 변화 그래프
        ax1.set_xlabel('시간 (Hour)', fontsize=14)
        ax1.set_ylabel('습도 (%)', fontsize=14, color='blue')
        ax1.plot(results_with_structure_df['hour'], results_with_structure_df['base_humidity'], 'k--', label='기본 습도 (CSV 데이터)')
        
        # 이끼 적용 시 습도
        ax1.plot(results_with_structure_df['hour'], results_with_structure_df['moss_area_humidity'], 'b-', marker='o', label='구조물 주변 습도 (구조물 적용)')
        ax1.plot(results_with_structure_df['hour'], results_with_structure_df['far_area_humidity'], 'g:', label='구조물 없는 곳 습도 (구조물 적용)')

        # 이끼 미적용 시 습도
        ax1.plot(results_with_moss_df['hour'], results_with_moss_df['moss_area_humidity'], 'c--', linestyle='--', marker='x', label='구조물 없는 곳 습도 (구조물 미적용)') 

        ax1.tick_params(axis='y', labelcolor='blue')
        ax1.grid(True, axis='y', linestyle='--', alpha=0.6)

        # 화재 위험도 변화 그래프
        ax2 = ax1.twinx()
        ax2.set_ylabel('화재 위험도', fontsize=14, color='red')
        
        # 구조물 적용 시 화재 위험도
        ax2.plot(results_with_structure_df['hour'], results_with_structure_df['moss_area_risk'], 'r-', marker='s', label='구조물 주변 화재 위험도 (구조물 적용)')

        # 구조물 미적용 (이끼 적용) 시 화재 위험도
        ax2.plot(results_with_moss_df['hour'], results_with_moss_df['moss_area_risk'], 'm--', marker='P', label='구조물 없는 곳 화재 위험도 (구조물 미적용)') 

        ax2.tick_params(axis='y', labelcolor='red')
        
        # 범례 합치기
        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax2.legend(lines + lines2, labels + labels2, loc='upper right', bbox_to_anchor=(1.0, 1.15))

        plt.title(f'시간에 따른 습도 및 화재 위험도 변화 ({scenario_name} 시나리오)', fontsize=18)
        plt.xticks(np.arange(0, 24, 2))
        fig.tight_layout()
        plt.show()

if __name__ == "__main__":
    try:
        experiment_humidity_data = pd.read_csv('./data/humidity_data.csv')
    except FileNotFoundError:
        print("Error: 'humidity_data.csv' not found. Please ensure the 'data' directory exists and contains the CSV file.")
        exit()

    experiment_humidity_data['humidity_boost'] = experiment_humidity_data['case3 (moss+archi) humi'] - experiment_humidity_data['case2 (moss) humi']
    humidity_boost_mean = experiment_humidity_data['humidity_boost'].mean()
    if np.isnan(humidity_boost_mean):
        print("Humidity boost mean is NaN!")
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
        print(f"\n===== {scenario_name} 시나리오 =====")
        hourly_data = pd.DataFrame(params, index=hours)

        # 구조물 적용
        sim_with_moss = Simulation(grid_size=100, cell_size=10.0)
        sim_with_moss.add_moss_structure(MossStructure(
            x=500, y=500, size=30, 
            humidity_boost=humidity_boost_mean,
            effective_radius=60.0
        ))
        print(f"구조물 추가 완료: 습도 +{sim_with_moss.moss_structures[0].humidity_boost:.2f}%, 효과 반경 {sim_with_moss.moss_structures[0].effective_radius}m")
        simulation_results_with_moss = sim_with_moss.run_time_series_simulation(hourly_data)

        # 구조물 미적용 (이끼 적용)
        sim_without_moss = Simulation(grid_size=100, cell_size=10.0)
        simulation_results_without_moss = sim_without_moss.run_time_series_simulation(hourly_data)

        # 결과 시각화
        sim_with_moss.visualize_results(simulation_results_with_moss, simulation_results_without_moss, scenario_name)

        # 하루 평균 위험도 감소량 계산 및 출력
        avg_risk_with_structure = simulation_results_with_moss['moss_area_risk'].mean()
        avg_risk_with_moss = simulation_results_without_moss['moss_area_risk'].mean()
        risk_reduction = avg_risk_with_moss - avg_risk_with_structure

        all_scenario_results[scenario_name] = {
            'avg_risk_with_moss': avg_risk_with_structure,
            'avg_risk_without_moss': avg_risk_with_moss,
            'risk_reduction': risk_reduction
        }

        print(f"--- {scenario_name} 시나리오: 하루 평균 화재 위험도 감소량 분석 ---")
        print(f"구조물 적용 시 하루 평균 화재 위험도: {avg_risk_with_structure:.4f}")
        print(f"이끼 적용 시 하루 평균 화재 위험도: {avg_risk_with_moss:.4f}")
        print(f"구조물 적용으로 인한 하루 평균 화재 위험도 감소량: {risk_reduction:.4f}")

        import os
        output_dir = './data'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        simulation_results_with_moss.to_csv(f'{output_dir}/simulation_results_{scenario_name}_with_moss_fixed_boost.csv', index=False)
        simulation_results_without_moss.to_csv(f'{output_dir}/simulation_results_{scenario_name}_without_moss_fixed_boost.csv', index=False)
        print('\n')
    
    print("##############################################")
    print("### 모든 시나리오별 하루 평균 화재 위험도 감소량 ###")
    print("##############################################")
    for scenario, data in all_scenario_results.items():
        print(f"\n======= {scenario} 시나리오 =======")
        print(f"구조물 적용 시 평균 위험도: {data['avg_risk_with_moss']:.4f}")
        print(f"이끼 적용 시 평균 위험도: {data['avg_risk_without_moss']:.4f}")
        print(f"**감소량**: {data['risk_reduction']:.4f}")