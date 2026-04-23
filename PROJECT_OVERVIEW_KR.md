# IPP-MARL 프로젝트 구조 및 코드 연결성 정리

## 1) 프로젝트 개요

이 프로젝트는 멀티 UAV의 정보획득 기반 경로 계획(Informative Path Planning)을 위해 COMA 기반 다중 에이전트 강화학습(MARL)을 구현한 코드베이스다.  
핵심 루프는 다음과 같다.

1. 각 UAV가 관측 수행
2. 로컬 맵 업데이트 및 통신 융합
3. Actor가 행동 선택
4. Critic이 Q-value 학습
5. 엔트로피 감소 기반 보상으로 정책 개선

즉, `행동 -> 측정 -> 맵 변화 -> 보상 -> 학습`의 폐루프 구조다.

---

## 2) 최상위 폴더 구조

- `README.md`: 논문 배경/문제 정의/접근 방식 개요
- `marl_framework/`: 실행 및 학습 코드 전체

---

## 3) `marl_framework` 내부 구조

### A. 실행/설정 계층

- `main.py`: 실행 엔트리포인트
- `params.py`: YAML 설정 로더
- `params.yaml`: 실험 하이퍼파라미터
- `constants.py`: 경로/상수/미션 타입 정의
- `logger.py`: 콘솔+파일 로깅 설정

### B. 미션 오케스트레이션 계층 (`missions/`)

- `mission_factories.py`: 설정값(`missions.type`)에 따라 미션 생성
- `missions.py`: 미션 인터페이스(추상 클래스)
- `coma_mission.py`: 학습 루프(에피소드 반복, 평가, 모델 저장, 텐서보드 로깅)
- `episode_generator.py`: 단일 에피소드의 step 전개 담당

### C. 에이전트 계층 (`agent/`)

- `agent.py`: 에이전트의 통신/행동/맵업데이트
- `action_space.py`: 유효 액션 마스크, 충돌 회피 마스크, 위치 변환
- `state_space.py`: 상태 인덱스/좌표 변환 및 초기 위치 샘플링
- `communication_log.py`: 통신 범위/실패율을 반영한 메시지 전달

### D. 맵/센서/시뮬레이션 계층

- `mapping/grid_maps.py`: 격자 해상도 및 맵 크기 계산
- `mapping/mappings.py`: footprint 기반 맵 업데이트/맵 융합
- `mapping/simulations.py`: GT 맵 생성 및 노이즈 관측 생성
- `mapping/ground_truths.py`: 랜덤 필드 생성 로직
- `sensors/__init__.py`: 센서 베이스 클래스
- `sensors/cameras.py`: 카메라 FoV 투영
- `sensors/models/sensor_models.py`: 고도별 노이즈 모델

### E. 학습 계층

- `coma_wrapper.py`: Actor/Critic/보상/메모리 연결 허브
- `batch_memory.py`: transition 저장, TD(lambda) 타깃 생성, 배치 구성
- `actor/network.py`: 정책망(Actor)
- `actor/learner.py`: 정책 업데이트 로직
- `actor/transformations.py`: Actor 입력 피처 생성
- `critic/network.py`: 가치망(Critic, Q-value)
- `critic/learner.py`: Critic 업데이트 + 타깃망 동기화
- `critic/transformations.py`: Critic 입력 피처 생성

### F. 유틸/베이스라인/실험

- `utils/reward.py`: 엔트로피 감소 기반 보상
- `utils/state.py`: Shannon entropy 및 가중 엔트로피
- `utils/plotting.py`: trajectory/지표 시각화
- `random_baseline.py`, `lawn_mower.py`, `IG_baseline.py`: 비교 실험
- `classification.py`, `coma_test.py`: 보조 실험/테스트 성격 코드

---

## 4) 실행 시퀀스(엔드투엔드)

1. `main.py` 실행
2. `params.py`가 `params.yaml` 로딩
3. `MissionFactory`가 미션 객체 생성
4. `COMAMission.execute()`에서 에피소드 반복
5. 각 에피소드는 `EpisodeGenerator.execute()`가 step 단위 진행
6. step마다:
   - `COMAWrapper.build_observations()`로 관측 구성
   - 에이전트 통신/수신 후 로컬맵 융합
   - Actor 입력 피처 생성 후 행동 선택
   - 맵 업데이트 및 전역맵 융합
   - 보상 계산 및 메모리 저장
7. 메모리 누적량이 기준을 넘으면:
   - TD 타깃 생성
   - Critic 학습
   - Actor 학습
8. 주기적으로 평가/시각화/모델 저장 수행

---

## 5) 코드 간 연결성과 유기적 관계

### 5.1 `missions` <-> `agent` <-> `mapping`

- 미션 루프가 전체 시간축을 제어
- 에이전트가 개별 행동을 선택
- 행동 결과가 센서 측정으로 이어지고 맵이 갱신
- 갱신된 맵이 다음 스텝 관측으로 재입력

즉, 정책과 환경지식(맵)이 서로를 계속 갱신하는 순환 구조다.

### 5.2 `communication_log`를 통한 협업 결합

- 에이전트는 자신의 로컬맵/위치/footprint를 로그에 기록
- 다른 에이전트는 거리/실패율 조건에서만 수신
- 수신된 정보는 `Mapping.fuse_map()`으로 통합

즉, 통신 제약이 협력 성능에 직접 연결된다.

### 5.3 Actor/Critic 분리 입력의 의미

- Actor: 로컬 관측 중심(부분 관측)
- Critic: 전역 맵/타 에이전트 정보 포함(중앙집중 관측)

이는 COMA의 핵심인 `decentralized execution + centralized training`에 부합한다.

### 5.4 `batch_memory`의 연결 허브 역할

- 관측/행동/보상/종료여부/state를 time-step별로 저장
- TD(lambda) 타깃을 만들어 Critic 학습 안정화
- Critic의 Q-value를 Actor advantage 계산에 사용

즉, Critic 학습 결과가 Actor 업데이트 신호로 바로 연결된다.

### 5.5 엔트로피 기반 목표 일관성

- `utils/state.py`의 엔트로피가 관측 feature와 reward 양쪽에서 사용
- `utils/reward.py`는 엔트로피 감소를 보상으로 환산

즉, 표현(feature)과 목적(objective)이 동일한 정보 이론 축으로 정렬되어 있다.

---

## 6) `params.yaml`에서 성능에 큰 영향을 주는 항목

- 팀/제약:
  - `experiment.missions.n_agents`
  - `experiment.constraints.budget`
  - `experiment.uav.communication_range`
  - `experiment.uav.failure_rate`
- 탐험:
  - `eps_max`, `eps_min`, `eps_anneal_phase`, `use_eps`
- 학습 안정성:
  - `networks.batch_size`, `data_passes`, `gamma`, `lambda`
  - `critic.target_update_mode`, `copy_rate`, `tau`
- 센서 난이도:
  - `sensor.model.*`, `sensor.simulation.cluster_radius`
- 행동공간:
  - `experiment.constraints.num_actions`
  - `experiment.missions.action_space`

---

## 7) 수정 시작점 가이드

- 보상 함수 변경: `utils/reward.py`
- 관측 피처 변경: `actor/transformations.py`, `critic/transformations.py`
- 액션/충돌 규칙 변경: `agent/action_space.py`
- 통신 정책 변경: `agent/communication_log.py`
- 센서 노이즈 변경: `sensors/models/sensor_models.py`
- 학습 루프/평가 주기 변경: `missions/coma_mission.py`

---

## 8) 현재 코드베이스에서 유의할 점

- 일부 경로가 Linux 절대경로 기반으로 작성되어 있어 환경별 경로 정리가 필요할 수 있다.
- 미션 타입 상수는 다양하지만 팩토리/실행 흐름은 COMA 중심으로 구성되어 있다.
- 연구 코드 특성상 베이스라인 스크립트가 분산되어 있어 통합 실행 스크립트가 있으면 운영성이 좋아진다.

