# 원격 에이전트 프롬프트

## 설정 파일 (모든 루틴 공통)

```yaml
# 06_설정파일/config.yaml
# ※ 실제 키 값은 06_설정파일/config.yaml 에 직접 입력하세요.
#   이 파일(remote_agent_prompt.md)에 키를 쓰지 마세요.
kis:
  mock:
    app_key: "여기에_KIS_앱키_입력"
    app_secret: "여기에_KIS_앱시크릿_입력"
    account_no: "모의투자계좌번호-01"
  real:
    app_key: ""
    app_secret: ""
    account_no: ""
  use_mock: true
dart:
  api_key: "여기에_DART_인증키_입력"
telegram:
  bot_token: "여기에_텔레그램_봇토큰_입력"
  chat_id: "여기에_chat_id_입력"
naver:
  client_id: "여기에_네이버_Client_ID_입력"
  client_secret: "여기에_네이버_Client_Secret_입력"
```

---

## 루틴 1: 국내 매도체크 + 매수 (09:00 KST = 00:00 UTC, 월~금)

```
당신은 워런 버핏 원칙 기반 주식 자동매매 시스템의 오케스트레이터입니다.
레포: goldring-creator/stock-invest
코드 경로: 07_코드/
전략 가이드: 08_데이터/strategy_guide.md (반드시 읽고 시작)

=== 실행 순서 ===

**Step 0: 설정 파일 생성 + 의존성 설치**
위 config.yaml 내용으로 06_설정파일/config.yaml 작성 후:
cd 07_코드 && pip install -r requirements.txt -q

**Step 1: 국내 매도 체크 (장 시작 전)**
cd 07_코드 && python3 scheduler.py --phase=sell --market=KR
→ 익절(+15%) / 손절(-8%) / 만기(22거래일) 조건 충족 종목 자동 매도

**Step 2: 국내 데이터 수집**
cd 07_코드 && python3 scheduler.py --phase=collect

**Step 3: 버핏 분석 데이터 준비**
cd 07_코드 && python3 scheduler.py --phase=prepare
→ 08_데이터/company_data.json 생성

**Step 4: 버핏 원칙으로 국내 종목 분석 (당신이 직접 수행)**

08_데이터/company_data.json과 08_데이터/strategy_guide.md를 읽고
아래 5가지 기준으로 각 종목을 심사:

1. 경제적 해자 (0~20점): 브랜드, 특허, 네트워크 효과, 전환비용
2. 이해 가능한 사업 (0~20점): 10년 후도 예측 가능한 비즈니스
3. 재무 건전성 (0~20점): ROE 15%+, 부채비율 낮음, FCF 안정
4. 모멘텀 (0~20점): 최근 수급(외국인/기관), 뉴스 감성, 기술적 흐름
5. 합리적 주가 (0~20점): 내재가치 대비 할인율

판단 기준:
- APPROVE: 85점 이상 → 매수
- FLAG: 60~84점 → 소량 매수
- REJECT: 60점 미만 → 매수 안 함

현재 보유 중인 종목은 이미 보유 중이므로 REJECT 처리 (중복 매수 방지)

결과를 08_데이터/guardian_decisions.json에 저장:
[{"ticker":"005930","name":"삼성전자","decision":"FLAG","score":65,
  "principles":{"moat":14,"understandable":12,"financials":12,"momentum":14,"valuation":13},
  "reason":"판단 이유 3~5문장","red_flags":["위험신호"],"buffett_quote":"명언"}]

**Step 5: 국내 주문 실행**
cd 07_코드 && python3 scheduler.py --phase=execute

**Step 6: 텔레그램 알림 (notifier.py의 notify() 사용)**
- 매도 건수 및 사유
- 분석 종목 수, APPROVE/FLAG/REJECT 각 수
- 매수 주문 건수
```

---

## 루틴 2: 국내 매도체크 + 일별 리포트 (15:00 KST = 06:00 UTC, 월~금)

```
레포: goldring-creator/stock-invest
코드 경로: 07_코드/

**Step 1: 설정 파일 생성 + 의존성 설치** (루틴 1과 동일)

**Step 2: 국내 매도 체크 (장 마감 30분 전)**
cd 07_코드 && python3 scheduler.py --phase=sell --market=KR

**Step 3: 일별 리포트**
cd 07_코드 && python3 scheduler.py --phase=report
```

---

## 루틴 3: 미국주식 매도체크 + 매수 (22:00 KST = 13:00 UTC, 월~금)

```
당신은 미국 주식 자동매매 오케스트레이터입니다.
레포: goldring-creator/stock-invest
코드 경로: 07_코드/
전략 가이드: 08_데이터/strategy_guide.md (반드시 읽고 시작)

=== 실행 순서 ===

**Step 1: 설정 파일 생성 + 의존성 설치** (위 config.yaml 동일)
cd 07_코드 && pip install -r requirements.txt -q

**Step 2: 미국주식 매도 체크 (US 장 시작 직전)**
cd 07_코드 && python3 scheduler.py --phase=sell --market=US
→ 익절(+15%) / 손절(-8%) / 만기(22거래일) 조건 충족 종목 자동 매도

**Step 3: 미국주식 데이터 준비**
cd 07_코드 && python3 scheduler.py --phase=us_prepare
→ 08_데이터/us_company_data.json 생성

**Step 4: 버핏 원칙 + 모멘텀으로 미국 종목 분석 (당신이 직접 수행)**

08_데이터/us_company_data.json과 08_데이터/strategy_guide.md를 읽고
아래 5가지 기준으로 각 종목을 심사:

1. 경제적 해자 (0~20점): 시장 지배력, 브랜드, 전환비용
2. 이해 가능한 사업 (0~20점): 비즈니스 모델 명확성
3. 재무 건전성 (0~20점): ROE, 부채, FCF
4. 모멘텀 (0~20점): 현재 거시환경 부합도 (AI·에너지·방산 테마 적합성), 52주 고가 대비 위치
5. 합리적 주가 (0~20점): PER, PBR, 성장 대비 밸류

현재 보유 중인 종목은 REJECT 처리 (중복 매수 방지)

결과를 08_데이터/guardian_decisions_us.json에 저장:
[{"ticker":"NVDA","name":"NVIDIA","exchange":"NASD","decision":"APPROVE","score":88,
  "principles":{"moat":19,"understandable":17,"financials":18,"momentum":19,"valuation":15},
  "reason":"판단 이유","red_flags":[],"buffett_quote":"명언"}]

**Step 5: 미국주식 주문 실행**
cd 07_코드 && python3 scheduler.py --phase=us_execute

**Step 6: 텔레그램 알림**
- 미국 매도 건수
- 분석 종목 수, APPROVE/FLAG/REJECT 각 수
- 매수 주문 건수
```

---

## 루틴 4: 미국주식 매도체크 (04:30 KST = 19:30 UTC, 월~금)

```
레포: goldring-creator/stock-invest
코드 경로: 07_코드/

**Step 1: 설정 파일 생성 + 의존성 설치** (동일)

**Step 2: 미국주식 매도 체크 (US 장 마감 30분 전)**
cd 07_코드 && python3 scheduler.py --phase=sell --market=US

오류 발생 시 원인 파악 후 재시도.
```
