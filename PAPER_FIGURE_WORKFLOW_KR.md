# 논문용 Figure 생성 워크플로우 (TensorBoard 로그 기반)

TensorBoard는 학습 모니터링에는 좋지만, 논문용 Figure로는 한계가 있다.  
아래 절차로 `TensorBoard event -> CSV -> 논문형 Figure(PNG/PDF)`로 변환하면 된다.

## 1) 사전 준비

프로젝트 루트에서 가상환경 의존성 설치:

```powershell
uv pip install --python .venv -r requirements-windows.txt
```

## 2) TensorBoard 로그에서 스칼라 추출

```powershell
.\.venv\Scripts\python .\tools\extract_tb_scalars.py --logdir .\marl_framework\logs --outdir .\analysis\tb_export
```

출력:

- `analysis/tb_export/scalars/*.csv` (태그별 CSV)
- `analysis/tb_export/index.json` (run/tag 인덱스)

## 3) 논문용 플롯 생성

```powershell
.\.venv\Scripts\python .\tools\plot_paper_curves.py --scalars-dir .\analysis\tb_export\scalars --outdir .\analysis\paper_figures --ema-alpha 0.2 --dpi 300 --style-template ieee
```

출력:

- `analysis/paper_figures/single/*.png`
- `analysis/paper_figures/single/*.pdf`
- (group 규칙 사용 시) `analysis/paper_figures/group_compare/*.png`, `*.pdf`

## 4) Pretty Label 자동 매핑

예시 파일:

- `tools/configs/pretty_labels.example.json`

사용 예:

```powershell
.\.venv\Scripts\python .\tools\plot_paper_curves.py --scalars-dir .\analysis\tb_export\scalars --outdir .\analysis\paper_figures --pretty-labels-json .\tools\configs\pretty_labels.example.json
```

- exact key 매핑: `"Critic/Loss": "Critic Loss"`
- regex 매핑: `"re:^trainReturn/": "Train Return"`

## 5) IEEE / Springer 템플릿

아래 옵션 중 하나를 사용:

- `--style-template default`
- `--style-template ieee`
- `--style-template springer`

예:

```powershell
.\.venv\Scripts\python .\tools\plot_paper_curves.py --scalars-dir .\analysis\tb_export\scalars --outdir .\analysis\paper_figures_ieee --style-template ieee
```

## 6) 여러 알고리즘(run 그룹) 비교 플롯

예시 파일:

- `tools/configs/group_regex.example.json`

사용 예:

```powershell
.\.venv\Scripts\python .\tools\plot_paper_curves.py --scalars-dir .\analysis\tb_export\scalars --outdir .\analysis\paper_figures_compare --group-regex-json .\tools\configs\group_regex.example.json
```

`group_regex`를 주면 태그별로:

- 개별 통합 플롯: `single/`
- 그룹 비교 플롯: `group_compare/`

가 동시에 생성된다.

## 7) 특정 지표만 그리기 (필터)

예: loss 관련 태그만 출력

```powershell
.\.venv\Scripts\python .\tools\plot_paper_curves.py --scalars-dir .\analysis\tb_export\scalars --outdir .\analysis\paper_figures_loss --include-tags "Loss|loss"
```

## 8) 권장 실험 프로토콜 (논문용)

- seed 여러 개(최소 3~5) 실행
- 동일 하이퍼파라미터/평가 조건 유지
- 평균 및 분산(표준편차) 기반 보고
- 최종 제출은 PDF(벡터) 우선 사용

## 9) 주의사항

- CSV 파일명은 태그 문자열 정규화본(특수문자 `_` 치환)으로 생성된다.
- 원본 태그명은 `analysis/tb_export/index.json`을 통해 복원해 제목에 사용된다.
- `--ema-alpha`는 시각적 smoothing용이며, 논문 본문에는 smoothing 설정을 명시하는 것이 좋다.
- step이 run마다 다르면 가능한 step에 대해서만 평균/표준편차가 계산된다.
