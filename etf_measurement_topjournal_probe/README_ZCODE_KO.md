# KOREA ETF 측정오류: 탑저널 잠재력 판별용 실제 실행 패키지

이 디렉터리는 **기존 결과를 받아쓰지 않고**, 업로드된
`KOREA_ETF_MEASUREMENT_ERROR_EMPIRICAL_RESULTS_FINAL.zip` 안의 분석 패널에서
통계량을 다시 계산한다.

## 현재 데이터로 정확히 찌르는 질문

1. 누락은 단순 무작위 오류인가, 아니면 batch/multi-product/correction/template 같은
   **공시 생산·배포 아키텍처**가 만드는 비고전적 오류인가?
2. issuer 고정효과는 문서 아키텍처를 통제하면 얼마나 줄어드는가?
3. proxy를 쓰면 공시율뿐 아니라 severity·congestion 계수, 운용사 분산·순위,
   시장결과와의 연관성이 실제로 얼마나 왜곡되는가?
4. 공개 메타데이터만으로 만든 교정식을 새 운용사·새 연도에 적용했을 때
   receipt 기준 진실에 가까워지는가?
5. 위 결과가 특정 운용사·연도 하나에 의존하는가?

## ZCode가 할 일: 한 줄

원본 ZIP과 이 디렉터리를 같은 폴더에 둔 뒤 아래 한 줄만 실행한다.

```bash
python -m pip install -r etf_measurement_topjournal_probe/requirements.txt && python etf_measurement_topjournal_probe/run_topjournal_probe.py --input KOREA_ETF_MEASUREMENT_ERROR_EMPIRICAL_RESULTS_FINAL.zip --output ETF_TOPJOURNAL_PROBE_RUN
```

예상 입력 SHA-256:

```text
a56c4cb16d67b18c5723e8f207530e985aaade992067a36f755880db0a368d08
```

## 완료 조건

다음 파일이 실제 생성돼야 완료다.

- `ETF_TOPJOURNAL_PROBE_RUN/FINAL_VERDICT.md`
- `ETF_TOPJOURNAL_PROBE_RUN/TOPJOURNAL_SCORECARD.csv`
- `ETF_TOPJOURNAL_PROBE_RUN/tables/*.csv`
- `ETF_TOPJOURNAL_PROBE_RUN/figures/*.png`
- `ETF_TOPJOURNAL_PROBE_RUN/paper/RESULTS_DRAFT.md`
- `ETF_TOPJOURNAL_PROBE_RUN/ETF_TOPJOURNAL_PROBE_RESULTS.zip`

## 판정 규칙

- `GO_TOPJOURNAL_CANDIDATE_MEASUREMENT_ERROR`: 경제적 결론의 실질적 왜곡,
  문서 아키텍처 메커니즘, out-of-sample 교정, 강건성, 독립된 두 번째 환경 복제를 모두 통과.
- `GO_STRONG_MEASUREMENT_MECHANISM_PAPER_NEEDS_EXTERNAL_REPLICATION`: 앞의 네 조건은
  통과하지만 두 번째 환경이 없음.
- `GO_OPEN_DATA_MEASUREMENT_ERROR_PAPER`: 큰 prevalence bias는 있으나 메커니즘 또는
  경제학적 결론 왜곡이 약함.
- `STOP_REPORTED_RESULTS_NOT_REPRODUCED`: 핵심 confusion matrix가 원자료에서 재현되지 않음.

`run_topjournal_probe.py`가 데이터 파일과 열 이름을 자동 탐색한다. 결과를 보고 열 이름이나
표본을 바꾸지 않는다.