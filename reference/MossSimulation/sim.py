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
    humidity_boost: float
    effective_radius: float

@dataclass
class EnvironmentConditions:
    """특정 시간의 환경 조건 데이터 클래스"""
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

                        # 환경 요인
                        wind_effect = 1.0 - min(0.5, self.env.wind_speed / 14.0)
                        temp_effect = 1.0 - max(0, (self.env.temperature - 25) / 50.0)

                        humidity_increase = current_humidity_boost * effect_strength * wind_effect * temp_effect
                        
                        self.humidity_map[i, j] += humidity_increase

    def calculate_fire_risk(self):
        temp_risk = np.clip((self.env.temperature - 20) / 30.0, 0, 1)
        wind_risk = np.clip(self.env.wind_speed / 25.0, 0, 1)
        humidity_risk = np.clip((80 - self.humidity_map) / 60.0, 0, 1)
        
        self.fire_risk_map = (temp_risk * 0.3 +
                              wind_risk * 0.2 +
                              humidity_risk * 0.4 +
                              self.vegetation_density * 0.1)

    def run_time_series_simulation(self, hourly_data: pd.DataFrame):        
        results = []
        for hour, data in hourly_data.iterrows():
            self.env = EnvironmentConditions(
                temperature=data['temperature'],
                wind_speed=data['wind_speed'],
                wind_direction=180, # 예시 값
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

    def visualize_results(self, results_with_moss_df: pd.DataFrame, results_without_moss_df: pd.DataFrame):
        fig, ax1 = plt.subplots(figsize=(14, 7))
        
        # 습도 변화 그래프 (왼쪽 y축)
        ax1.set_xlabel('시간 (Hour)', fontsize=14)
        ax1.set_ylabel('습도 (%)', fontsize=14, color='blue')
        ax1.plot(results_with_moss_df['hour'], results_with_moss_df['base_humidity'], 'k--', label='기본 습도 (CSV 데이터)')
        
        # 이끼 적용 시 습도
        ax1.plot(results_with_moss_df['hour'], results_with_moss_df['moss_area_humidity'], 'b-', marker='o', label='이끼 주변 습도 (이끼 적용)')
        ax1.plot(results_with_moss_df['hour'], results_with_moss_df['far_area_humidity'], 'g:', label='이끼 없는 곳 습도 (이끼 적용)')

        # 이끼 미적용 시 습도 (baseline)
        ax1.plot(results_without_moss_df['hour'], results_without_moss_df['moss_area_humidity'], 'c--', linestyle='--', marker='x', label='이끼 없는 곳 습도 (이끼 미적용)') 

        ax1.tick_params(axis='y', labelcolor='blue')
        ax1.grid(True, axis='y', linestyle='--', alpha=0.6)

        # 화재 위험도 변화 그래프 (오른쪽 y축)
        ax2 = ax1.twinx()
        ax2.set_ylabel('화재 위험도', fontsize=14, color='red')
        
        # 이끼 적용 시 화재 위험도
        ax2.plot(results_with_moss_df['hour'], results_with_moss_df['moss_area_risk'], 'r-', marker='s', label='이끼 주변 화재 위험도 (이끼 적용)')

        # 이끼 미적용 시 화재 위험도
        ax2.plot(results_without_moss_df['hour'], results_without_moss_df['moss_area_risk'], 'm--', marker='P', label='이끼 없는 곳 화재 위험도 (이끼 미적용)') 

        ax2.tick_params(axis='y', labelcolor='red')
        
        # 범례 합치기
        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax2.legend(lines + lines2, labels + labels2, loc='upper right', bbox_to_anchor=(1.0, 1.15))

        plt.title('시간에 따른 습도 및 화재 위험도 변화 (이끼 적용 vs 미적용 - 고정 습도 부스트)', fontsize=18)
        plt.xticks(np.arange(0, 24, 2))
        fig.tight_layout()
        plt.show()

if __name__ == "__main__":
    experiment_humidity_data = pd.read_csv('./data/experiment_humidity_data.csv')
    experiment_humidity_data['humidity_boost'] = experiment_humidity_data['case3 (moss+archi) humi'] - experiment_humidity_data['case2 (moss) humi']
    humidity_boost_mean = experiment_humidity_data['humidity_boost'].mean()

    hours = np.arange(24)

    # example data
    base_humidity = 55 - 25 * np.cos(np.pi * (hours - 4) / 12)
    temperature = 15 + 15 * np.cos(np.pi * (hours - 4) / 12)
    wind_speed = 5 + 5 * np.sin(np.pi * (hours - 8) / 12)
    
    hourly_data = pd.DataFrame({
        'base_humidity': base_humidity,
        'temperature': temperature,
        'wind_speed': wind_speed
    }, index=hours)

    # 이끼 구조물 적용
    print("\n=== 이끼 구조물 적용 시뮬레이션 시작 (고정 습도 부스트) ===")
    sim_with_moss = Simulation(grid_size=100, cell_size=10.0)
    sim_with_moss.add_moss_structure(MossStructure(
        x=500, y=500, size=30, 
        humidity_boost=humidity_boost_mean,
        effective_radius=60.0
    ))
    print(f"💧 이끼 구조물 추가 완료: 습도 +{sim_with_moss.moss_structures[0].humidity_boost:.2f}%, 효과 반경 {sim_with_moss.moss_structures[0].effective_radius}m")
    simulation_results_with_moss = sim_with_moss.run_time_series_simulation(hourly_data)
    print("=== 이끼 구조물 적용 시뮬레이션 완료 ===")

    # 이끼 구조물 미적용
    print("\n=== 이끼 구조물 미적용 시뮬레이션 시작 ===")
    sim_without_moss = Simulation(grid_size=100, cell_size=10.0)
    simulation_results_without_moss = sim_without_moss.run_time_series_simulation(hourly_data)
    print("=== 이끼 구조물 미적용 시뮬레이션 완료 ===")


    sim_with_moss.visualize_results(simulation_results_with_moss, simulation_results_without_moss)

    avg_risk_with_moss = simulation_results_with_moss['moss_area_risk'].mean()
    avg_risk_without_moss = simulation_results_without_moss['moss_area_risk'].mean()

    risk_reduction = avg_risk_without_moss - avg_risk_with_moss

    print(f"\n=== 하루 평균 화재 위험도 감소량 분석 ===")
    print(f"이끼 적용 시 하루 평균 화재 위험도: {avg_risk_with_moss:.4f}")
    print(f"이끼 미적용 시 하루 평균 화재 위험도: {avg_risk_without_moss:.4f}")
    print(f"이끼 구조물 적용으로 인한 하루 평균 화재 위험도 감소량: {risk_reduction:.4f}")

    simulation_results_with_moss.to_csv('./data/simulation_results_with_moss_fixed_boost.csv', index=False)
    simulation_results_without_moss.to_csv('./data/simulation_results_without_moss_fixed_boost.csv', index=False)

    print("\n=== 시뮬레이션 결과 요약 (이끼 적용) ===")
    print(simulation_results_with_moss.head())
    print("\n===시뮬레이션 결과 요약 (이끼 미적용) ===")
    print(simulation_results_without_moss.head())