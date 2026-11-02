import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial.distance import cdist
from scipy.ndimage import gaussian_filter
import pandas as pd
from dataclasses import dataclass, field # <--- field 추가
from typing import List, Tuple, Optional, Dict # <--- Dict 추가
import seaborn as sns

# 글꼴 import
import matplotlib.pyplot as plt
plt.rcParams['font.family'] ='Malgun Gothic'
plt.rcParams['axes.unicode_minus'] =False

@dataclass
class MossStructure:
    """이끼 구조물 클래스"""
    x: float
    y: float
    size: float  # 구조물 크기 (m²)
    # humidity_boost: float # <--- 기존 단일 값 대신 아래 시간별 데이터 사용
    effective_radius: float  # 효과 반경 (m)
    durability: float  # 내구성 (0-1)
    # <--- 추가: 시간에 따른 습도 증가율 스케줄
    # 사용자의 '시간에 따른 습도 변화 그래프'를 모방한 데이터. key=시간(0-23), value=습도증가율(%)
    humidity_boost_schedule: Dict[int, float] = field(default_factory=dict)

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
        self.humidity_map = np.ones((grid_size, grid_size)) * 30.0
        self.fire_risk_map = np.zeros((grid_size, grid_size))
        self.moss_structures: List[MossStructure] = []
        # <--- 추가: 시간별 데이터를 저장하기 위한 리스트
        self.hourly_humidity_maps = []
        self.hourly_fire_risk_maps = []


    def add_moss_structure(self, moss: MossStructure):
        """이끼 구조물 추가"""
        self.moss_structures.append(moss)

    # <--- 변경: 시간에 따른 습도 효과 계산 로직
    def calculate_humidity_effect(self, env: EnvironmentConditions, hour: int):
        """
        이끼 구조물들의 습도 효과를 특정 시간에 맞춰 계산
        hour (int): 현재 시간 (0-23)
        """
        # 기본 습도 맵 초기화
        self.humidity_map.fill(env.base_humidity)
        DEW_END_HOUR = 9 # 아침 이슬이 마르는 시간 (오전 9시)

        for moss in self.moss_structures:
            # 현재 시간의 기본 습도 증가율 가져오기
            current_humidity_boost = moss.humidity_boost_schedule.get(hour, 10.0) # 스케줄에 없으면 기본값 10%

            # <--- 추가: 아침 이슬 이후, 바람에 의한 습도 감소 효과
            wind_drying_effect = 1.0
            if hour > DEW_END_HOUR:
                # 풍속이 셀수록 건조 효과가 커져 습도 증가율이 감소함 (최대 40% 감소로 제한)
                wind_drying_effect = 1.0 - min(0.4, env.wind_speed / 30.0)

            # 그리드 좌표로 변환
            grid_x = int(moss.x / self.cell_size)
            grid_y = int(moss.y / self.cell_size)
            effect_radius_cells = int(moss.effective_radius / self.cell_size)

            for i in range(max(0, grid_x - effect_radius_cells),
                          min(self.grid_size, grid_x + effect_radius_cells + 1)):
                for j in range(max(0, grid_y - effect_radius_cells),
                              min(self.grid_size, grid_y + effect_radius_cells + 1)):

                    distance = np.sqrt((i - grid_x)**2 + (j - grid_y)**2) * self.cell_size
                    if distance <= moss.effective_radius:
                        effect_strength = np.exp(-distance**2 / (2 * (moss.effective_radius/3)**2))

                        # 환경 조건에 따른 효과 조정
                        temp_effect = 1.0 - max(0, (env.temperature - 25) / 50.0)

                        # 최종 습도 증가량 = 기본 증가량 * 건조효과 * 온도효과 * 내구성
                        humidity_increase = (current_humidity_boost * effect_strength *
                                           wind_drying_effect * temp_effect * moss.durability)

                        self.humidity_map[i, j] += humidity_increase

        # <--- 추가: 시간별 습도 맵 저장
        self.hourly_humidity_maps.append(self.humidity_map.copy())


    def calculate_fire_risk(self, env: EnvironmentConditions):
        """화재 위험도 계산"""
        temp_risk = np.clip((env.temperature - 20) / 30.0, 0, 1)
        wind_risk = np.clip(env.wind_speed / 25.0, 0, 1)
        humidity_risk = np.clip((60 - self.humidity_map) / 40.0, 0, 1)
        vegetation_risk = self.vegetation_density

        self.fire_risk_map = (temp_risk * 0.3 +
                             wind_risk * 0.2 +
                             humidity_risk * 0.4 +
                             vegetation_risk * 0.1)

        # <--- 추가: 시간별 화재 위험도 맵 저장
        self.hourly_fire_risk_maps.append(self.fire_risk_map.copy())

    def simulate_fire_spread(self, ignition_point: Tuple[int, int],
                           env: EnvironmentConditions, ignition_hour: int, max_steps: int = 50): # <--- ignition_hour 추가
        """화재 확산 시뮬레이션"""
        # <--- 변경: 발화 시점의 화재 위험도 맵을 사용
        fire_risk_map_at_ignition = self.hourly_fire_risk_maps[ignition_hour]

        fire_map = np.zeros((self.grid_size, self.grid_size))
        fire_map[ignition_point] = 1.0
        spread_history = [fire_map.copy()]

        for step in range(max_steps):
            new_fire_map = fire_map.copy()
            for i in range(1, self.grid_size - 1):
                for j in range(1, self.grid_size - 1):
                    if fire_map[i, j] > 0:
                        for di in [-1, 0, 1]:
                            for dj in [-1, 0, 1]:
                                if di == 0 and dj == 0: continue
                                ni, nj = i + di, j + dj
                                if 0 <= ni < self.grid_size and 0 <= nj < self.grid_size and new_fire_map[ni, nj] == 0:
                                    # <--- 변경: 발화 시점의 위험도 사용
                                    spread_prob = fire_risk_map_at_ignition[ni, nj]
                                    wind_angle = np.radians(env.wind_direction)
                                    wind_dx, wind_dy = np.cos(wind_angle), np.sin(wind_angle)
                                    wind_alignment = (di * wind_dx + dj * wind_dy) / np.sqrt(di**2 + dj**2)
                                    wind_boost = 1.0 + max(0, wind_alignment) * env.wind_speed / 10.0
                                    spread_prob *= wind_boost

                                    if np.random.random() < spread_prob * 0.3:
                                        new_fire_map[ni, nj] = 1.0
            fire_map = new_fire_map
            spread_history.append(fire_map.copy())
            if np.array_equal(spread_history[-1], spread_history[-2]):
                break
        return spread_history

    # <--- 추가: 시간에 따른 시뮬레이션 실행 함수
    def run_daily_simulation(self, daily_weather_data: pd.DataFrame, ignition_point: Tuple[int, int], ignition_hour: int):
        """
        하루 동안의 환경 변화에 따른 시뮬레이션 실행
        """
        print("하루(24시간) 동안의 환경 변화 시뮬레이션 시작...")
        self.hourly_humidity_maps.clear()
        self.hourly_fire_risk_maps.clear()

        # 매 시간별로 습도 및 화재 위험도 계산
        for hour, weather in daily_weather_data.iterrows():
            env = EnvironmentConditions(
                temperature=weather['temperature'],
                wind_speed=weather['wind_speed'],
                wind_direction=weather['wind_direction'],
                base_humidity=weather['base_humidity'],
                solar_radiation=800 # 예시값
            )
            self.calculate_humidity_effect(env, hour)
            self.calculate_fire_risk(env)
        print("시간별 습도 및 화재 위험도 계산 완료.")

        # 지정된 발화 시간에 화재 확산 시뮬레이션 실행
        print(f"{ignition_hour}시에 화재 발생 시뮬레이션 실행...")
        ignition_env = EnvironmentConditions(
            temperature=daily_weather_data.loc[ignition_hour, 'temperature'],
            wind_speed=daily_weather_data.loc[ignition_hour, 'wind_speed'],
            wind_direction=daily_weather_data.loc[ignition_hour, 'wind_direction'],
            base_humidity=daily_weather_data.loc[ignition_hour, 'base_humidity'],
            solar_radiation=800
        )
        fire_history = self.simulate_fire_spread(ignition_point, ignition_env, ignition_hour)

        return fire_history

    # <--- 추가: 시간에 따른 변화를 보여주는 새로운 시각화 함수
    def visualize_time_series_results(self, daily_weather: pd.DataFrame, fire_history: list, moss_location: Tuple[int, int], no_moss_comparison: dict):
        """
        시간에 따른 시뮬레이션 결과 시각화
        no_moss_comparison: 이끼가 없을 때의 시간별 데이터
        """
        fig = plt.figure(figsize=(20, 15))
        grid = plt.GridSpec(3, 2, hspace=0.4, wspace=0.3)

        moss_grid_x, moss_grid_y = int(moss_location[0]/self.cell_size), int(moss_location[1]/self.cell_size)
        far_point_x, far_point_y = self.grid_size - moss_grid_x, self.grid_size - moss_grid_y

        # 1. 시간에 따른 습도 변화 그래프
        ax1 = fig.add_subplot(grid[0, 0])
        hours = range(24)
        base_humidity = daily_weather['base_humidity']
        moss_area_humidity = [hmap[moss_grid_x, moss_grid_y] for hmap in self.hourly_humidity_maps]
        no_moss_area_humidity = [hmap[far_point_x, far_point_y] for hmap in self.hourly_humidity_maps]

        ax1.plot(hours, base_humidity, 'k--', label='기본 습도 (대기)')
        ax1.plot(hours, moss_area_humidity, 'b-', marker='o', label='이끼 주변 습도')
        ax1.plot(hours, no_moss_area_humidity, 'g:', label=f'이끼 없는 지역 습도 ({far_point_x},{far_point_y})')
        ax1.set_title('시간에 따른 습도 변화 (예방 효과)', fontsize=16)
        ax1.set_xlabel('시간 (Hour)')
        ax1.set_ylabel('습도 (%)')
        ax1.set_xticks(hours)
        ax1.grid(True, alpha=0.5)
        ax1.legend()

        # 2. 시간에 따른 화재 위험도 변화 그래프
        ax2 = fig.add_subplot(grid[0, 1])
        moss_area_risk = [rmap[moss_grid_x, moss_grid_y] for rmap in self.hourly_fire_risk_maps]
        no_moss_area_risk = [rmap[far_point_x, far_point_y] for rmap in self.hourly_fire_risk_maps]

        ax2.plot(hours, moss_area_risk, 'r-', marker='s', label='이끼 주변 화재 위험도')
        ax2.plot(hours, no_moss_area_risk, 'orange', linestyle=':', label=f'이끼 없는 지역 위험도 ({far_point_x},{far_point_y})')
        ax2.set_title('시간에 따른 화재 위험도 변화 (예방 효과)', fontsize=16)
        ax2.set_xlabel('시간 (Hour)')
        ax2.set_ylabel('화재 위험도 (0-1)')
        ax2.set_xticks(hours)
        ax2.grid(True, alpha=0.5)
        ax2.legend()

        # 3. 화재 확산 결과 (이끼 있음)
        ax3 = fig.add_subplot(grid[1, 0])
        final_fire_with_moss = fire_history[-1]
        im3 = ax3.imshow(final_fire_with_moss, cmap='Reds', origin='lower')
        ax3.set_title(f'화재 확산 결과 (이끼 O) - {len(fire_history)} 단계 후', fontsize=16)
        ax3.set_xlabel('Y (격자)')
        ax3.set_ylabel('X (격자)')
        # Add moss location marker
        ax3.plot(moss_location[1]/self.cell_size, moss_location[0]/self.cell_size, 'bo', markersize=10, mfc='none', mew=2, label='이끼 위치')
        ax3.legend()

        # 4. 화재 확산 결과 (이끼 없음)
        ax4 = fig.add_subplot(grid[1, 1])
        final_fire_without_moss = no_moss_comparison['fire_history'][-1]
        im4 = ax4.imshow(final_fire_without_moss, cmap='Reds', origin='lower')
        ax4.set_title(f'화재 확산 결과 (이끼 X) - {len(no_moss_comparison["fire_history"])} 단계 후', fontsize=16)
        ax4.set_xlabel('Y (격자)')
        # ax4.set_ylabel('X (격자)')

        # 5. 화재 면적 비교 (방지 효과)
        ax5 = fig.add_subplot(grid[2, :])
        area_with_moss = [np.sum(f) for f in fire_history]
        area_without_moss = [np.sum(f) for f in no_moss_comparison['fire_history']]
        max_len = max(len(area_with_moss), len(area_without_moss))

        # Pad shorter list to make lengths equal for plotting
        area_with_moss.extend([area_with_moss[-1]] * (max_len - len(area_with_moss)))
        area_without_moss.extend([area_without_moss[-1]] * (max_len - len(area_without_moss)))

        ax5.plot(range(max_len), area_with_moss, 'b-', label=f'이끼 있음 (최종 면적: {area_with_moss[-1]:.0f})')
        ax5.plot(range(max_len), area_without_moss, 'r--', label=f'이끼 없음 (최종 면적: {area_without_moss[-1]:.0f})')
        ax5.set_title('이끼 유무에 따른 화재 확산 면적 비교 (방지/억제 효과)', fontsize=16)
        ax5.set_xlabel('확산 시간 (단계)')
        ax5.set_ylabel('화재 면적 (격자 수)')
        ax5.grid(True, alpha=0.5)
        ax5.legend()
        
        reduction = (area_without_moss[-1] - area_with_moss[-1]) / area_without_moss[-1] * 100 if area_without_moss[-1] > 0 else 0
        fig.suptitle(f'이끼 구조물 산불 방지/예방 효과 시뮬레이션\n(화재 면적 감소율: {reduction:.1f}%)', fontsize=20, y=0.98)
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        plt.show()

# <--- 추가: 시뮬레이션을 위한 시간별 날씨 데이터 생성 함수
def generate_daily_weather_data(peak_temp, min_temp, peak_wind, base_hum):
    """하루 동안의 날씨 데이터를 DataFrame으로 생성"""
    hours = np.arange(24)
    # 온도는 14시(오후 2시)에 최고, 새벽 4시에 최저인 사인 곡선으로 모방
    temp_cycle = -np.cos(np.pi * (hours - 4) / 12)
    temperature = min_temp + (peak_temp - min_temp) * (temp_cycle + 1) / 2
    # 풍속은 오후에 더 강해지는 경향을 모방
    wind_speed = peak_wind * (1 + 0.5 * np.sin(np.pi * (hours - 8) / 12)) / 1.5
    # 습도는 온도와 반비례
    humidity = base_hum + (peak_temp - temperature) * 1.5

    df = pd.DataFrame({
        'hour': hours,
        'temperature': temperature,
        'wind_speed': wind_speed,
        'wind_direction': np.random.randint(0, 360, 24), # 풍향은 무작위로
        'base_humidity': np.clip(humidity, 15, 95) # 15% ~ 95% 범위로 제한
    })
    df.set_index('hour', inplace=True)
    return df

# === 메인 실행 부분 수정 ===
if __name__ == "__main__":
    print("시간에 따른 이끼 기반 산불 예방 효과 시뮬레이션 시작...")

    # --- 시뮬레이션 조건 설정 ---
    IGNITION_HOUR = 15 # 화재 발생 시간 (가장 건조하고 더운 오후 3시)
    IGNITION_POINT = (40, 50) # 화재 시작점

    # --- 시간별 데이터 정의 ---
    # 1. 사용자의 이끼 구조물 습도 데이터 (시간대별 습도 증가율 %)
    # 이른 아침/밤: 높음, 낮: 낮아짐
    moss_humidity_schedule = {
        0: 28, 1: 30, 2: 32, 3: 35, 4: 35, 5: 33, 6: 30, 7: 28, 8: 25, 9: 22,
        10: 20, 11: 18, 12: 16, 13: 15, 14: 14, 15: 14, 16: 15, 17: 16,
        18: 18, 19: 20, 20: 22, 21: 24, 22: 26, 23: 27
    }

    # 2. 하루 동안의 날씨 변화 데이터 생성 (건조한 봄/가을 날씨 가정)
    daily_weather = generate_daily_weather_data(peak_temp=25, min_temp=10, peak_wind=15, base_hum=30)


    # --- 시뮬레이션 (1): 이끼 구조물이 있는 경우 ---
    print("\n--- 시나리오 1: 이끼 구조물이 있는 경우 ---")
    simulator_with_moss = MossFirePreventionSimulator(grid_size=100, cell_size=10.0)

    # 이끼 구조물 추가 (시간별 습도 데이터 포함)
    moss_location_1 = (300, 400)
    simulator_with_moss.add_moss_structure(
        MossStructure(x=moss_location_1[0], y=moss_location_1[1], size=30,
                      effective_radius=60, durability=0.9,
                      humidity_boost_schedule=moss_humidity_schedule)
    )

    # 시간에 따른 시뮬레이션 실행
    fire_history_with_moss = simulator_with_moss.run_daily_simulation(
        daily_weather_data=daily_weather,
        ignition_point=IGNITION_POINT,
        ignition_hour=IGNITION_HOUR
    )

    # --- 시뮬레이션 (2): 이끼 구조물이 없는 경우 (비교군) ---
    print("\n--- 시나리오 2: 이끼 구조물이 없는 경우 (비교 분석용) ---")
    simulator_without_moss = MossFirePreventionSimulator(grid_size=100, cell_size=10.0)
    fire_history_without_moss = simulator_without_moss.run_daily_simulation(
        daily_weather_data=daily_weather,
        ignition_point=IGNITION_POINT,
        ignition_hour=IGNITION_HOUR
    )

    # --- 결과 분석 및 시각화 ---
    print("\n--- 최종 결과 분석 및 시각화 ---")
    no_moss_data_for_viz = {
        "fire_history": fire_history_without_moss,
        "hourly_humidity": simulator_without_moss.hourly_humidity_maps,
        "hourly_risk": simulator_without_moss.hourly_fire_risk_maps
    }
    simulator_with_moss.visualize_time_series_results(
        daily_weather,
        fire_history_with_moss,
        moss_location_1,
        no_moss_data_for_viz
    )

    final_area_with_moss = np.sum(fire_history_with_moss[-1])
    final_area_without_moss = np.sum(fire_history_without_moss[-1])
    reduction_percent = (final_area_without_moss - final_area_with_moss) / final_area_without_moss * 100 if final_area_without_moss > 0 else 0

    print("\n=== 시뮬레이션 요약 ===")
    print(f"발화 시각: {IGNITION_HOUR}시, 발화 지점: {IGNITION_POINT}")
    print(f"이끼가 없을 때 최종 화재 면적: {final_area_without_moss:.0f} 격자")
    print(f"이끼가 있을 때 최종 화재 면적: {final_area_with_moss:.0f} 격자")
    print(f"화재 면적 감소율: {reduction_percent:.1f}%")