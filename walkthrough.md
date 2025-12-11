# 네이버 부동산 매물 수집 및 분석기 - 사용 가이드

## 프로젝트 개요
이 도구는 네이버 부동산(Naver Land)의 매물 정보를 수집하여 허위매물 의심 사례인 '미끼매물' 증거를 확보하기 위한 도구입니다. Streamlit 대시보드를 통해 수집된 데이터를 시각화하고 분석할 수 있습니다.

## 📂 프로젝트 구조
`naver_land_collector/` 폴더 내 주요 파일 설명:
- `requirements.txt`: Python 라이브러리 의존성 파일.
- `utils.py`: 데이터 정제 및 JSON 파일 입출력을 담당하는 유틸리티.
- `crawler.py`: 네이버 부동산 모바일 API 연동 핵심 로직.
- `app.py`: Streamlit 기반 웹 대시보드 UI.
- `data.json`: (자동 생성됨) 수집된 매물 데이터가 저장되는 파일.

## 🚀 실행 방법

### 1. 라이브러리 설치
터미널에서 다음 명령어를 실행하여 필요한 패키지를 설치합니다:
```bash
pip install -r requirements.txt
```

### 2. 대시보드 실행
다음 명령어로 대시보드를 실행합니다 (PATH 오류 방지를 위해 `python -m` 사용 권장):
```bash
python -m streamlit run app.py
```
실행 후 브라우저가 자동으로 열리며 대시보드가 표시됩니다 (보통 `http://localhost:8501`).

### 3. 사용 가이드
1. **기본 설정 (사이드바)**:
    - **단지 식별 번호 (hscpNo)** 입력: 네이버 부동산에서 특정 아파트 단지를 조회할 때 URL에 포함된 번호입니다.
    - 예시: *은마아파트*의 경우 `1116`. (기본값 `108064`로 설정됨)
    - **매물 종류** 선택 (매매/전세/월세).
2. **증거 수집**:
    - **"매물 수집 시작"** 버튼을 클릭합니다.
    - 시스템이 현재 등록된 매물 정보를 가져와 `data.json` 파일에 시간 기록과 함께 저장합니다.
3. **데이터 분석**:
    - 대시보드 중앙의 차트를 통해 가격 분포와 통계를 확인합니다.
    - 여러 날에 걸쳐 수집하면 시계열 변화를 추적하여 매물이 사라지거나 가격이 변동된 내역을 확인할 수 있습니다.
4. **데이터 내보내기**:
    - **"데이터 다운로드 (CSV)"** 버튼을 눌러 엑셀 등으로 열어볼 수 있는 파일로 저장합니다.

## ❓ 단지 식별 번호 (hscpNo) 찾는 법
네이버 부동산에서 원하는 아파트 단지를 찾은 후, URL에서 번호를 확인할 수 있습니다.

**방법 1: 모바일 웹 (m.land.naver.com)**
1. 네이버 부동산 모바일 페이지 접속.
2. 원하는 아파트 단지 검색 및 선택.
3. 주소창의 URL을 확인합니다.
   - 예: `https://m.land.naver.com/complex/1116?tradeType=A1`
   - 여기서 `complex/` 뒤에 있는 숫자 **1116**이 단지 번호입니다.

**방법 2: PC 웹 (land.naver.com)**
1. 네이버 부동산 PC 페이지 접속.
2. 아파트 단지 선택 후 '단지정보' 클릭.
3. URL이 `https://new.land.naver.com/complexes/1116?ms=...` 형태입니다.
   - `complexes/` 바로 뒤의 숫자 **1116**이 단지 번호입니다.

## ☁️ Google Sheets 연동 (클라우드 배포용)
Streamlit Cloud 등에 배포 시 데이터 유지를 위해 **구글 스프레드시트**를 저장소로 사용할 수 있도록 코드가 수정되었습니다.

**설정 방법:**
1. `.streamlit/secrets.toml` 파일 생성 (로컬 실행 시) 또는 Streamlit Cloud의 Secrets 설정에 아래 내용을 추가합니다.
2. 구글 클라우드 콘솔 서비스 계정(JSON 키)이 필요합니다.

```toml
[connections.gsheets]
spreadsheet = "https://docs.google.com/spreadsheets/d/14QzR2C5p89rHfnX9RGhl-o5bOdLdndBwExAQeX8hr5A/edit?usp=sharing"
worksheet = "data"
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "..."
client_email = "..."
client_id = "..."
auth_uri = "..."
token_uri = "..."
auth_provider_x509_cert_url = "..."
client_x509_cert_url = "..."
```
*설정이 없으면 자동으로 로컬 JSON 파일모드로 작동합니다.*

## ⚠️ 참고 사항
- 이 크롤러는 네이버 부동산 모바일 웹 API 로직을 사용합니다. 네이버 측의 업데이트로 구조가 변경되면 실행되지 않을 수 있습니다.
- 본 도구는 개인적인 매물 분석 및 허위매물 증거 수집을 위한 학습용 도구입니다.
