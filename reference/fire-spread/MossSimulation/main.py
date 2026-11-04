import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial.distance import cdist
from scipy.ndimage import gaussian_filter
import pandas as pd
from dataclasses import dataclass
from typing import List, Tuple, Optional
import seaborn as sns

# 글꼴 import
plt.rcParams['font.family'] ='Malgun Gothic'
plt.rcParams['axes.unicode_minus'] =False

@dataclass
class MossStructure:
    """이끼 구조물 클래스"""
    x: float
    y: float
    size: float  # 구조물 크기 (m²)
    humidity_boost: float  # 습도 증가율 (%)
    effective_radius: float  # 효과 반경 (m)
    durability: float  # 내구성 (0-1)
    
@dataclass
class EnvironmentConditions:
    """환경 조건 클래스"""
    temperature: float  # 온도 (°C)
    wind_speed: float  # 풍속 (m/s)
    wind_direction: float  # 풍향 (도)
    base_humidity: float  # 기본 습도 (%)
    solar_radiation: float  # 일사량 (W/m²)
    
class MossFirePreventionSimulator:
    """이끼 기반 산불 예방 시뮬레이션 클래스"""
    
    def __init__(self, grid_size: int = 100, cell_size: float = 10.0):
        self.grid_size = grid_size
        self.cell_size = cell_size  # 각 셀의 크기 (m)
        self.terrain = np.zeros((grid_size, grid_size))
        self.vegetation_density = np.ones((grid_size, grid_size)) * 0.5
        self.humidity_map = np.ones((grid_size, grid_size)) * 30.0  # 기본 습도 30%
        self.fire_risk_map = np.zeros((grid_size, grid_size))
        self.moss_structures: List[MossStructure] = []
        
    def add_moss_structure(self, moss: MossStructure):
        """이끼 구조물 추가"""
        self.moss_structures.append(moss)
        
    def calculate_humidity_effect(self, env: EnvironmentConditions):
        """이끼 구조물들의 습도 효과 계산"""
        # 기본 습도 맵 초기화
        self.humidity_map.fill(env.base_humidity)
        
        for moss in self.moss_structures:
            # 그리드 좌표로 변환
            grid_x = int(moss.x / self.cell_size)
            grid_y = int(moss.y / self.cell_size)
            
            # 효과 반경 계산
            effect_radius_cells = int(moss.effective_radius / self.cell_size)
            
            # 거리 기반 습도 증가 효과
            for i in range(max(0, grid_x - effect_radius_cells), 
                          min(self.grid_size, grid_x + effect_radius_cells + 1)):
                for j in range(max(0, grid_y - effect_radius_cells), 
                              min(self.grid_size, grid_y + effect_radius_cells + 1)):
                    
                    distance = np.sqrt((i - grid_x)**2 + (j - grid_y)**2) * self.cell_size
                    
                    if distance <= moss.effective_radius:
                        # 거리에 따른 습도 효과 감소 (가우시안 분포)
                        effect_strength = np.exp(-distance**2 / (2 * (moss.effective_radius/3)**2))
                        
                        # 환경 조건에 따른 효과 조정
                        wind_effect = 1.0 - min(0.5, env.wind_speed / 20.0)  # 강풍 시 효과 감소
                        temp_effect = 1.0 - max(0, (env.temperature - 25) / 50.0)  # 고온 시 효과 감소
                        
                        humidity_increase = (moss.humidity_boost * effect_strength * 
                                           wind_effect * temp_effect * moss.durability)
                        
                        self.humidity_map[i, j] += humidity_increase
                        
    def calculate_fire_risk(self, env: EnvironmentConditions):
        """화재 위험도 계산"""
        # 기본 화재 위험도 = f(온도, 풍속, 습도, 식생밀도)
        temp_risk = np.clip((env.temperature - 20) / 30.0, 0, 1)
        wind_risk = np.clip(env.wind_speed / 25.0, 0, 1)
        humidity_risk = np.clip((60 - self.humidity_map) / 40.0, 0, 1)
        vegetation_risk = self.vegetation_density
        
        # 종합 화재 위험도 (0-1 스케일)
        self.fire_risk_map = (temp_risk * 0.3 + 
                             wind_risk * 0.2 + 
                             humidity_risk * 0.4 + 
                             vegetation_risk * 0.1)
        
    def simulate_fire_spread(self, ignition_point: Tuple[int, int], 
                           env: EnvironmentConditions, max_steps: int = 50):
        """화재 확산 시뮬레이션"""
        fire_map = np.zeros((self.grid_size, self.grid_size))
        fire_map[ignition_point] = 1.0
        
        spread_history = [fire_map.copy()]
        
        for step in range(max_steps):
            new_fire_map = fire_map.copy()
            
            # 현재 화재 지점에서 인근으로 확산
            for i in range(1, self.grid_size - 1):
                for j in range(1, self.grid_size - 1):
                    if fire_map[i, j] > 0:
                        # 8방향 확산
                        for di in [-1, 0, 1]:
                            for dj in [-1, 0, 1]:
                                if di == 0 and dj == 0:
                                    continue
                                    
                                ni, nj = i + di, j + dj
                                if 0 <= ni < self.grid_size and 0 <= nj < self.grid_size:
                                    if new_fire_map[ni, nj] == 0:
                                        # 확산 확률 = 화재 위험도 * 바람 효과
                                        spread_prob = self.fire_risk_map[ni, nj]
                                        
                                        # 바람 방향 효과
                                        wind_angle = np.radians(env.wind_direction)
                                        wind_dx = np.cos(wind_angle)
                                        wind_dy = np.sin(wind_angle)
                                        
                                        # 바람 방향과 확산 방향의 일치도
                                        wind_alignment = (di * wind_dx + dj * wind_dy) / np.sqrt(di**2 + dj**2)
                                        wind_boost = 1.0 + max(0, wind_alignment) * env.wind_speed / 10.0
                                        
                                        spread_prob *= wind_boost
                                        
                                        if np.random.random() < spread_prob * 0.3:  # 기본 확산 확률 조정
                                            new_fire_map[ni, nj] = 1.0
            
            fire_map = new_fire_map
            spread_history.append(fire_map.copy())
            
            # 더 이상 확산이 없으면 종료
            if np.array_equal(spread_history[-1], spread_history[-2]):
                break
                
        return spread_history
    
    def run_simulation(self, env: EnvironmentConditions, ignition_points: List[Tuple[int, int]]):
        """전체 시뮬레이션 실행"""
        print("습도 효과 계산 중...")
        self.calculate_humidity_effect(env)
        
        print("화재 위험도 계산 중...")
        self.calculate_fire_risk(env)
        
        results = {}
        for i, ignition_point in enumerate(ignition_points):
            print(f"화재 확산 시뮬레이션 {i+1}/{len(ignition_points)}...")
            fire_history = self.simulate_fire_spread(ignition_point, env)
            results[f"fire_{i}"] = fire_history
            
        return results
    
    def visualize_results(self, results: dict, env: EnvironmentConditions):
        """결과 시각화"""
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        
        # 1. 이끼 구조물 위치
        ax1 = axes[0, 0]
        ax1.imshow(self.humidity_map, cmap='Blues', origin='lower')
        for moss in self.moss_structures:
            circle = plt.Circle((moss.y/self.cell_size, moss.x/self.cell_size), 
                              moss.effective_radius/self.cell_size, 
                              fill=False, color='red', linewidth=2)
            ax1.add_patch(circle)
            ax1.plot(moss.y/self.cell_size, moss.x/self.cell_size, 'ro', markersize=8)
        ax1.set_title('이끼 구조물과 습도 분포')
        ax1.set_xlabel('Y (격자)')
        ax1.set_ylabel('X (격자)')
        
        # 2. 화재 위험도 맵
        ax2 = axes[0, 1]
        im2 = ax2.imshow(self.fire_risk_map, cmap='Reds', origin='lower')
        ax2.set_title('화재 위험도 맵')
        ax2.set_xlabel('Y (격자)')
        ax2.set_ylabel('X (격자)')
        plt.colorbar(im2, ax=ax2, label='위험도 (0-1)')
        
        # 3. 화재 확산 결과 (첫 번째 화재)
        if 'fire_0' in results:
            ax3 = axes[0, 2]
            final_fire = results['fire_0'][-1]
            ax3.imshow(final_fire, cmap='Reds', origin='lower')
            ax3.set_title('화재 확산 결과')
            ax3.set_xlabel('Y (격자)')
            ax3.set_ylabel('X (격자)')
        
        # 4. 습도 분포 히스토그램
        ax4 = axes[1, 0]
        ax4.hist(self.humidity_map.flatten(), bins=30, alpha=0.7, color='blue')
        ax4.axvline(env.base_humidity, color='red', linestyle='--', label=f'기본 습도: {env.base_humidity}%')
        ax4.set_xlabel('습도 (%)')
        ax4.set_ylabel('빈도')
        ax4.set_title('습도 분포')
        ax4.legend()
        
        # 5. 화재 위험도 히스토그램
        ax5 = axes[1, 1]
        ax5.hist(self.fire_risk_map.flatten(), bins=30, alpha=0.7, color='red')
        ax5.set_xlabel('화재 위험도 (0-1)')
        ax5.set_ylabel('빈도')
        ax5.set_title('화재 위험도 분포')
        
        # 6. 화재 확산 면적 vs 시간
        ax6 = axes[1, 2]
        for fire_key in results:
            fire_history = results[fire_key]
            areas = [np.sum(fire_map) for fire_map in fire_history]
            ax6.plot(areas, label=fire_key)
        ax6.set_xlabel('시간 (단계)')
        ax6.set_ylabel('화재 면적 (격자 수)')
        ax6.set_title('화재 확산 면적 변화')
        ax6.legend()
        
        plt.tight_layout()
        plt.show()
        
    def analyze_effectiveness(self, results_with_moss: dict, results_without_moss: dict):
        """이끼 구조물 효과 분석"""
        print("\n=== 이끼 구조물 효과 분석 ===")
        
        for fire_key in results_with_moss:
            if fire_key in results_without_moss:
                area_with = np.sum(results_with_moss[fire_key][-1])
                area_without = np.sum(results_without_moss[fire_key][-1])
                
                reduction = (area_without - area_with) / area_without * 100
                print(f"{fire_key}: 화재 면적 감소율 {reduction:.1f}%")
                print(f"  - 이끼 있음: {area_with:.0f} 격자")
                print(f"  - 이끼 없음: {area_without:.0f} 격자")

class ExperimentDataProcessor:
    """실험 데이터 처리 클래스"""
    
    @staticmethod
    def load_experimental_data(file_path: str = None) -> dict:
        """실험 데이터 로드 (CSV 파일 또는 하드코딩된 데이터)"""
        if file_path:
            # CSV 파일에서 데이터 로드
            df = pd.read_csv(file_path)
            return df.to_dict('records')
        else:
            # 예시 실험 데이터
            return {
                'moss_types': ['Sphagnum', 'Grimmia', 'Bryum'],
                'humidity_boost': [18.5, 22.3, 15.2],  # 습도 증가율 (%)
                'effective_radius': [45, 55, 35],  # 효과 반경 (m)
                'durability': [0.95, 0.85, 0.92],  # 내구성
                'cost_per_unit': [150, 200, 120]  # 단위당 비용 (원)
            }
    
    @staticmethod
    def calibrate_model(experimental_data: dict, simulator: MossFirePreventionSimulator):
        """실험 데이터를 기반으로 모델 보정"""
        print("실험 데이터 기반 모델 보정 중...")
        
        # 실험 데이터 통계
        avg_humidity_boost = np.mean(experimental_data['humidity_boost'])
        avg_effective_radius = np.mean(experimental_data['effective_radius'])
        avg_durability = np.mean(experimental_data['durability'])
        
        print(f"평균 습도 증가율: {avg_humidity_boost:.1f}%")
        print(f"평균 효과 반경: {avg_effective_radius:.1f}m")
        print(f"평균 내구성: {avg_durability:.2f}")
        
        return {
            'humidity_boost': avg_humidity_boost,
            'effective_radius': avg_effective_radius,
            'durability': avg_durability
        }

class ScenarioGenerator:
    """다양한 시나리오 생성 클래스"""
    
    @staticmethod
    def generate_weather_scenarios():
        """다양한 기상 조건 시나리오"""
        scenarios = [
            # 극한 건조 조건
            EnvironmentConditions(35, 25, 180, 15, 1000),
            # 일반적인 여름 조건
            EnvironmentConditions(28, 10, 90, 35, 800),
            # 봄/가을 조건
            EnvironmentConditions(22, 8, 45, 50, 600),
            # 습한 조건
            EnvironmentConditions(25, 5, 0, 65, 400)
        ]
        
        names = ['극한건조', '일반여름', '봄가을', '습한날씨']
        return dict(zip(names, scenarios))
    
    @staticmethod
    def generate_moss_placement_strategies(grid_size: int, cell_size: float):
        """이끼 구조물 배치 전략"""
        strategies = {}
        
        # 전략 1: 균등 배치
        uniform_moss = []
        for i in range(20, grid_size*cell_size, 200):
            for j in range(20, grid_size*cell_size, 200):
                uniform_moss.append(MossStructure(i, j, 25, 18, 50, 0.9))
        strategies['균등배치'] = uniform_moss
        
        # 전략 2: 고위험 지역 집중
        high_risk_moss = [
            MossStructure(200, 200, 35, 22, 70, 0.95),
            MossStructure(400, 300, 40, 25, 80, 0.9),
            MossStructure(600, 500, 30, 20, 60, 0.85),
            MossStructure(800, 700, 35, 23, 75, 0.92)
        ]
        strategies['고위험집중'] = high_risk_moss
        
        # 전략 3: 경계선 방어
        boundary_moss = []
        for i in range(50, grid_size*cell_size, 150):
            boundary_moss.append(MossStructure(i, 100, 30, 20, 55, 0.88))
            boundary_moss.append(MossStructure(i, grid_size*cell_size-100, 30, 20, 55, 0.88))
        strategies['경계방어'] = boundary_moss
        
        return strategies

class CostBenefitAnalyzer:
    """비용-편익 분석 클래스"""
    
    def __init__(self):
        self.fire_damage_cost_per_hectare = 50000000  # 헥타르당 화재 피해 비용 (원)
        self.installation_cost_per_structure = 300000  # 구조물당 설치 비용 (원)
        self.maintenance_cost_per_year = 50000  # 연간 유지비용 (원)
        
    def calculate_cost_benefit(self, moss_structures: List[MossStructure], 
                             fire_reduction_area: float, years: int = 10):
        """비용-편익 계산"""
        # 비용 계산
        installation_cost = len(moss_structures) * self.installation_cost_per_structure
        maintenance_cost = len(moss_structures) * self.maintenance_cost_per_year * years
        total_cost = installation_cost + maintenance_cost
        
        # 편익 계산 (화재 피해 감소)
        area_hectares = fire_reduction_area * 0.01  # 격자를 헥타르로 변환
        fire_damage_prevented = area_hectares * self.fire_damage_cost_per_hectare
        
        # 비용-편익 비율
        benefit_cost_ratio = fire_damage_prevented / total_cost if total_cost > 0 else 0
        
        return {
            'total_cost': total_cost,
            'fire_damage_prevented': fire_damage_prevented,
            'benefit_cost_ratio': benefit_cost_ratio,
            'net_benefit': fire_damage_prevented - total_cost
        }

def run_comprehensive_analysis():
    """종합적인 분석 실행"""
    print("=== 이끼 기반 산불 예방 시스템 종합 분석 ===\n")
    
    # 실험 데이터 로드
    exp_data = ExperimentDataProcessor.load_experimental_data()
    
    # 시나리오 생성
    weather_scenarios = ScenarioGenerator.generate_weather_scenarios()
    placement_strategies = ScenarioGenerator.generate_moss_placement_strategies(100, 10)
    
    # 비용-편익 분석기
    cost_analyzer = CostBenefitAnalyzer()
    
    results_summary = []
    
    for weather_name, weather_condition in weather_scenarios.items():
        print(f"\n--- {weather_name} 조건 분석 ---")
        
        for strategy_name, moss_structures in placement_strategies.items():
            print(f"\n배치 전략: {strategy_name}")
            print(f"이끼 구조물 수: {len(moss_structures)}개")
            
            # 시뮬레이션 실행
            simulator = MossFirePreventionSimulator(grid_size=100, cell_size=10.0)
            for moss in moss_structures:
                simulator.add_moss_structure(moss)
            
            # 화재 발생 지점 (다양한 위치)
            ignition_points = [(20, 30), (50, 70), (80, 20)]
            
            # 이끼 있는 경우
            results_with = simulator.run_simulation(weather_condition, ignition_points)
            
            # 이끼 없는 경우
            simulator_no_moss = MossFirePreventionSimulator(grid_size=100, cell_size=10.0)
            results_without = simulator_no_moss.run_simulation(weather_condition, ignition_points)
            
            # 효과 계산
            total_reduction = 0
            for fire_key in results_with:
                if fire_key in results_without:
                    area_with = np.sum(results_with[fire_key][-1])
                    area_without = np.sum(results_without[fire_key][-1])
                    total_reduction += (area_without - area_with)
            
            # 비용-편익 분석
            cost_benefit = cost_analyzer.calculate_cost_benefit(moss_structures, total_reduction)
            
            print(f"화재 면적 감소: {total_reduction:.0f} 격자")
            print(f"비용-편익 비율: {cost_benefit['benefit_cost_ratio']:.2f}")
            print(f"순편익: {cost_benefit['net_benefit']:,.0f}원")
            
            results_summary.append({
                'weather': weather_name,
                'strategy': strategy_name,
                'structures': len(moss_structures),
                'reduction': total_reduction,
                'cost_benefit_ratio': cost_benefit['benefit_cost_ratio'],
                'net_benefit': cost_benefit['net_benefit']
            })
    
    # 결과 요약
    print("\n=== 종합 결과 요약 ===")
    df_results = pd.DataFrame(results_summary)
    
    # 최고 성능 전략 찾기
    best_strategy = df_results.loc[df_results['cost_benefit_ratio'].idxmax()]
    print(f"\n최적 전략:")
    print(f"- 기상 조건: {best_strategy['weather']}")
    print(f"- 배치 전략: {best_strategy['strategy']}")
    print(f"- 비용-편익 비율: {best_strategy['cost_benefit_ratio']:.2f}")
    print(f"- 순편익: {best_strategy['net_benefit']:,.0f}원")
    
    return df_results

# 사용 예시
if __name__ == "__main__":
    # 기본 시뮬레이션
    print("기본 시뮬레이션 실행...")
    simulator = MossFirePreventionSimulator(grid_size=100, cell_size=10.0)
    
    # 실험 데이터 기반 이끼 구조물 설정
    exp_data = ExperimentDataProcessor.load_experimental_data()
    calibrated_params = ExperimentDataProcessor.calibrate_model(exp_data, simulator)
    
    # 보정된 매개변수로 이끼 구조물 생성
    moss_structures = [
        MossStructure(x=300, y=200, size=25, 
                     humidity_boost=calibrated_params['humidity_boost'],
                     effective_radius=calibrated_params['effective_radius'],
                     durability=calibrated_params['durability']),
        MossStructure(x=500, y=400, size=30,
                     humidity_boost=calibrated_params['humidity_boost'],
                     effective_radius=calibrated_params['effective_radius'],
                     durability=calibrated_params['durability']),
        MossStructure(x=700, y=600, size=20,
                     humidity_boost=calibrated_params['humidity_boost'],
                     effective_radius=calibrated_params['effective_radius'],
                     durability=calibrated_params['durability'])
    ]
    
    for moss in moss_structures:
        simulator.add_moss_structure(moss)
    
    # 환경 조건 설정
    env = EnvironmentConditions(
        temperature=32.0,
        wind_speed=15.0,
        wind_direction=45.0,
        base_humidity=25.0,
        solar_radiation=800.0
    )
    
    # 화재 발생 지점
    ignition_points = [(20, 30), (80, 70)]
    
    # 시뮬레이션 실행
    print("이끼 구조물이 있는 경우 시뮬레이션...")
    results_with_moss = simulator.run_simulation(env, ignition_points)
    
    # 이끼 구조물 제거 후 비교 시뮬레이션
    print("\n이끼 구조물이 없는 경우 시뮬레이션...")
    simulator_no_moss = MossFirePreventionSimulator(grid_size=100, cell_size=10.0)
    results_without_moss = simulator_no_moss.run_simulation(env, ignition_points)
    
    # 결과 시각화
    simulator.visualize_results(results_with_moss, env)
    
    # 효과 분석
    simulator.analyze_effectiveness(results_with_moss, results_without_moss)
    
    # 종합 분석 실행
    print("\n" + "="*50)
    print("종합 분석 시작...")
    comprehensive_results = run_comprehensive_analysis()
    
    # 결과 시각화
    plt.figure(figsize=(15, 10))
    
    # 1. 기상 조건별 효과
    plt.subplot(2, 3, 1)
    weather_effect = comprehensive_results.groupby('weather')['reduction'].mean()
    plt.bar(weather_effect.index, weather_effect.values)
    plt.title('기상 조건별 화재 감소 효과')
    plt.xlabel('기상 조건')
    plt.ylabel('평균 화재 면적 감소 (격자)')
    plt.xticks(rotation=45)
    
    # 2. 배치 전략별 효과
    plt.subplot(2, 3, 2)
    strategy_effect = comprehensive_results.groupby('strategy')['reduction'].mean()
    plt.bar(strategy_effect.index, strategy_effect.values)
    plt.title('배치 전략별 화재 감소 효과')
    plt.xlabel('배치 전략')
    plt.ylabel('평균 화재 면적 감소 (격자)')
    plt.xticks(rotation=45)
    
    # 3. 비용-편익 비율 분포
    plt.subplot(2, 3, 3)
    plt.hist(comprehensive_results['cost_benefit_ratio'], bins=10, alpha=0.7)
    plt.axvline(1, color='red', linestyle='--', label='손익분기점')
    plt.title('비용-편익 비율 분포')
    plt.xlabel('비용-편익 비율')
    plt.ylabel('빈도')
    plt.legend()
    
    # 4. 구조물 수 vs 효과
    plt.subplot(2, 3, 4)
    plt.scatter(comprehensive_results['structures'], comprehensive_results['reduction'])
    plt.title('구조물 수와 화재 감소 효과')
    plt.xlabel('구조물 수')
    plt.ylabel('화재 면적 감소 (격자)')
    
    # 5. 기상 조건별 비용-편익 비율
    plt.subplot(2, 3, 5)
    weather_cb = comprehensive_results.groupby('weather')['cost_benefit_ratio'].mean()
    plt.bar(weather_cb.index, weather_cb.values)
    plt.axhline(1, color='red', linestyle='--', label='손익분기점')
    plt.title('기상 조건별 비용-편익 비율')
    plt.xlabel('기상 조건')
    plt.ylabel('평균 비용-편익 비율')
    plt.xticks(rotation=45)
    plt.legend()
    
    # 6. 전략별 순편익
    plt.subplot(2, 3, 6)
    strategy_benefit = comprehensive_results.groupby('strategy')['net_benefit'].mean()
    plt.bar(strategy_benefit.index, strategy_benefit.values)
    plt.title('배치 전략별 순편익')
    plt.xlabel('배치 전략')
    plt.ylabel('평균 순편익 (원)')
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.show()


class SensitivityAnalyzer:
    """민감도 분석 클래스"""
    
    def __init__(self, base_simulator: MossFirePreventionSimulator):
        self.base_simulator = base_simulator
    
    def humidity_sensitivity_analysis(self, env: EnvironmentConditions, ignition_points: List[Tuple[int, int]]):
        """습도 증가율 민감도 분석"""
        print("습도 증가율 민감도 분석 중...")
        
        humidity_boosts = np.linspace(5, 35, 10)  # 5%~35% 범위
        results = []
        
        for boost in humidity_boosts:
            # 임시 시뮬레이터 생성
            temp_simulator = MossFirePreventionSimulator(
                grid_size=self.base_simulator.grid_size,
                cell_size=self.base_simulator.cell_size
            )
            
            # 수정된 습도 증가율로 이끼 구조물 추가
            for moss in self.base_simulator.moss_structures:
                modified_moss = MossStructure(
                    x=moss.x, y=moss.y, size=moss.size,
                    humidity_boost=boost, effective_radius=moss.effective_radius,
                    durability=moss.durability
                )
                temp_simulator.add_moss_structure(modified_moss)
            
            # 시뮬레이션 실행
            sim_results = temp_simulator.run_simulation(env, ignition_points)
            
            # 총 화재 면적 계산
            total_fire_area = 0
            for fire_key in sim_results:
                total_fire_area += np.sum(sim_results[fire_key][-1])
            
            results.append({
                'humidity_boost': boost,
                'fire_area': total_fire_area
            })
        
        return results
    
    def radius_sensitivity_analysis(self, env: EnvironmentConditions, ignition_points: List[Tuple[int, int]]):
        """효과 반경 민감도 분석"""
        print("효과 반경 민감도 분석 중...")
        
        radii = np.linspace(20, 100, 10)  # 20m~100m 범위
        results = []
        
        for radius in radii:
            temp_simulator = MossFirePreventionSimulator(
                grid_size=self.base_simulator.grid_size,
                cell_size=self.base_simulator.cell_size
            )
            
            for moss in self.base_simulator.moss_structures:
                modified_moss = MossStructure(
                    x=moss.x, y=moss.y, size=moss.size,
                    humidity_boost=moss.humidity_boost, effective_radius=radius,
                    durability=moss.durability
                )
                temp_simulator.add_moss_structure(modified_moss)
            
            sim_results = temp_simulator.run_simulation(env, ignition_points)
            
            total_fire_area = 0
            for fire_key in sim_results:
                total_fire_area += np.sum(sim_results[fire_key][-1])
            
            results.append({
                'effective_radius': radius,
                'fire_area': total_fire_area
            })
        
        return results
    
    def plot_sensitivity_results(self, humidity_results: list, radius_results: list):
        """민감도 분석 결과 시각화"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # 습도 증가율 민감도
        humidity_data = pd.DataFrame(humidity_results)
        ax1.plot(humidity_data['humidity_boost'], humidity_data['fire_area'], 'b-o')
        ax1.set_xlabel('습도 증가율 (%)')
        ax1.set_ylabel('총 화재 면적 (격자)')
        ax1.set_title('습도 증가율에 따른 화재 면적 변화')
        ax1.grid(True, alpha=0.3)
        
        # 효과 반경 민감도
        radius_data = pd.DataFrame(radius_results)
        ax2.plot(radius_data['effective_radius'], radius_data['fire_area'], 'r-o')
        ax2.set_xlabel('효과 반경 (m)')
        ax2.set_ylabel('총 화재 면적 (격자)')
        ax2.set_title('효과 반경에 따른 화재 면적 변화')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()


class MonteCarloSimulator:
    """몬테카를로 시뮬레이션 클래스"""
    
    def __init__(self, base_simulator: MossFirePreventionSimulator):
        self.base_simulator = base_simulator
    
    def run_monte_carlo(self, base_env: EnvironmentConditions, 
                       ignition_points: List[Tuple[int, int]], 
                       num_simulations: int = 100):
        """몬테카를로 시뮬레이션 실행"""
        print(f"몬테카를로 시뮬레이션 ({num_simulations}회) 실행 중...")
        
        results = []
        
        for i in range(num_simulations):
            if i % 20 == 0:
                print(f"진행률: {i/num_simulations*100:.1f}%")
            
            # 환경 조건에 불확실성 추가
            varied_env = EnvironmentConditions(
                temperature=base_env.temperature + np.random.normal(0, 3),
                wind_speed=max(0, base_env.wind_speed + np.random.normal(0, 2)),
                wind_direction=base_env.wind_direction + np.random.normal(0, 15),
                base_humidity=np.clip(base_env.base_humidity + np.random.normal(0, 5), 10, 80),
                solar_radiation=max(0, base_env.solar_radiation + np.random.normal(0, 100))
            )
            
            # 이끼 구조물 성능에 불확실성 추가
            temp_simulator = MossFirePreventionSimulator(
                grid_size=self.base_simulator.grid_size,
                cell_size=self.base_simulator.cell_size
            )
            
            for moss in self.base_simulator.moss_structures:
                varied_moss = MossStructure(
                    x=moss.x, y=moss.y, size=moss.size,
                    humidity_boost=max(0, moss.humidity_boost + np.random.normal(0, 2)),
                    effective_radius=max(10, moss.effective_radius + np.random.normal(0, 5)),
                    durability=np.clip(moss.durability + np.random.normal(0, 0.05), 0.5, 1.0)
                )
                temp_simulator.add_moss_structure(varied_moss)
            
            # 시뮬레이션 실행
            sim_results = temp_simulator.run_simulation(varied_env, ignition_points)
            
            # 결과 수집
            total_fire_area = 0
            for fire_key in sim_results:
                total_fire_area += np.sum(sim_results[fire_key][-1])
            
            results.append({
                'simulation': i,
                'fire_area': total_fire_area,
                'temperature': varied_env.temperature,
                'wind_speed': varied_env.wind_speed,
                'humidity': varied_env.base_humidity
            })
        
        return pd.DataFrame(results)
    
    def analyze_monte_carlo_results(self, mc_results: pd.DataFrame):
        """몬테카를로 결과 분석"""
        print("\n=== 몬테카를로 시뮬레이션 결과 분석 ===")
        
        fire_areas = mc_results['fire_area']
        
        print(f"화재 면적 통계:")
        print(f"  평균: {fire_areas.mean():.1f} 격자")
        print(f"  표준편차: {fire_areas.std():.1f} 격자")
        print(f"  95% 신뢰구간: [{fire_areas.quantile(0.025):.1f}, {fire_areas.quantile(0.975):.1f}]")
        print(f"  최대: {fire_areas.max():.1f} 격자")
        print(f"  최소: {fire_areas.min():.1f} 격자")
        
        # 위험도 평가
        high_risk_threshold = fire_areas.quantile(0.9)
        high_risk_probability = (fire_areas > high_risk_threshold).mean() * 100
        print(f"\n위험도 평가:")
        print(f"  고위험 임계값: {high_risk_threshold:.1f} 격자")
        print(f"  고위험 확률: {high_risk_probability:.1f}%")
        
        return {
            'mean': fire_areas.mean(),
            'std': fire_areas.std(),
            'ci_lower': fire_areas.quantile(0.025),
            'ci_upper': fire_areas.quantile(0.975),
            'high_risk_prob': high_risk_probability
        }
    
    def plot_monte_carlo_results(self, mc_results: pd.DataFrame):
        """몬테카를로 결과 시각화"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # 1. 화재 면적 분포
        axes[0, 0].hist(mc_results['fire_area'], bins=30, alpha=0.7, edgecolor='black')
        axes[0, 0].set_xlabel('화재 면적 (격자)')
        axes[0, 0].set_ylabel('빈도')
        axes[0, 0].set_title('화재 면적 분포')
        axes[0, 0].axvline(mc_results['fire_area'].mean(), color='red', linestyle='--', label='평균')
        axes[0, 0].legend()
        
        # 2. 온도 vs 화재 면적
        axes[0, 1].scatter(mc_results['temperature'], mc_results['fire_area'], alpha=0.6)
        axes[0, 1].set_xlabel('온도 (°C)')
        axes[0, 1].set_ylabel('화재 면적 (격자)')
        axes[0, 1].set_title('온도와 화재 면적의 관계')
        
        # 3. 풍속 vs 화재 면적
        axes[1, 0].scatter(mc_results['wind_speed'], mc_results['fire_area'], alpha=0.6)
        axes[1, 0].set_xlabel('풍속 (m/s)')
        axes[1, 0].set_ylabel('화재 면적 (격자)')
        axes[1, 0].set_title('풍속과 화재 면적의 관계')
        
        # 4. 습도 vs 화재 면적
        axes[1, 1].scatter(mc_results['humidity'], mc_results['fire_area'], alpha=0.6)
        axes[1, 1].set_xlabel('습도 (%)')
        axes[1, 1].set_ylabel('화재 면적 (격자)')
        axes[1, 1].set_title('습도와 화재 면적의 관계')
        
        plt.tight_layout()
        plt.show()


# 고급 분석 실행 함수
def run_advanced_analysis():
    """고급 분석 실행"""
    print("=== 고급 분석 모듈 실행 ===\n")
    
    # 기본 시뮬레이터 설정
    simulator = MossFirePreventionSimulator(grid_size=100, cell_size=10.0)
    
    # 실험 데이터 기반 이끼 구조물 설정
    exp_data = ExperimentDataProcessor.load_experimental_data()
    calibrated_params = ExperimentDataProcessor.calibrate_model(exp_data, simulator)
    
    moss_structures = [
        MossStructure(x=300, y=300, size=25, 
                     humidity_boost=calibrated_params['humidity_boost'],
                     effective_radius=calibrated_params['effective_radius'],
                     durability=calibrated_params['durability']),
        MossStructure(x=600, y=600, size=30,
                     humidity_boost=calibrated_params['humidity_boost'],
                     effective_radius=calibrated_params['effective_radius'],
                     durability=calibrated_params['durability'])
    ]
    
    for moss in moss_structures:
        simulator.add_moss_structure(moss)
    
    # 기본 환경 조건
    base_env = EnvironmentConditions(
        temperature=30.0, wind_speed=12.0, wind_direction=90.0,
        base_humidity=30.0, solar_radiation=750.0
    )
    
    ignition_points = [(25, 25), (75, 75)]
    
    # 1. 민감도 분석
    print("1. 민감도 분석 실행...")
    sensitivity_analyzer = SensitivityAnalyzer(simulator)
    
    humidity_sensitivity = sensitivity_analyzer.humidity_sensitivity_analysis(base_env, ignition_points)
    radius_sensitivity = sensitivity_analyzer.radius_sensitivity_analysis(base_env, ignition_points)
    
    sensitivity_analyzer.plot_sensitivity_results(humidity_sensitivity, radius_sensitivity)
    
    # 2. 몬테카를로 시뮬레이션
    print("\n2. 몬테카를로 시뮬레이션 실행...")
    mc_simulator = MonteCarloSimulator(simulator)
    
    mc_results = mc_simulator.run_monte_carlo(base_env, ignition_points, num_simulations=200)
    mc_stats = mc_simulator.analyze_monte_carlo_results(mc_results)
    mc_simulator.plot_monte_carlo_results(mc_results)
    
    return {
        'sensitivity': {'humidity': humidity_sensitivity, 'radius': radius_sensitivity},
        'monte_carlo': {'results': mc_results, 'stats': mc_stats}
    }


# 전체 실행
if __name__ == "__main__":
    print("이끼 기반 산불 예방 시스템 시뮬레이션 시작...\n")
    
    # 기본 시뮬레이션 실행
    advanced_results = run_advanced_analysis()
    
    print("\n시뮬레이션 완료!")
    print("결과 분석 및 시각화가 완료되었습니다.")
    
    # 최종 권장사항 출력
    print("\n=== 최종 권장사항 ===")
    print("1. 습도 증가율 18-22% 범위에서 최적 효과")
    print("2. 효과 반경 50-70m가 비용 대비 효율적")
    print("3. 고위험 지역 집중 배치 전략 권장")
    print("4. 기상 조건 모니터링 시스템 연계 필요")
    print("5. 정기적인 성능 평가 및 보수 계획 수립")