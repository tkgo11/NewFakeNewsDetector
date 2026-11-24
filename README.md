# NewFakeNewsDetector

[English](README-en.md) · [설계와 조사 자료](docs/methodology.md)

기사나 게시글에서 뽑은 **한국어·영어 주장 한 문장**을 기존 검증 자료와 대조합니다. 결과에서 어떤 주장이 일치했는지, 출처의 평가가 무엇인지, 원문을 어디에서 볼 수 있는지 확인할 수 있습니다.

## 시작하기

Python 3.11 이상과 [uv](https://docs.astral.sh/uv/getting-started/installation/)가 필요합니다.

```sh
git clone https://github.com/tkgo11/NewFakeNewsDetector.git
cd NewFakeNewsDetector
uv sync --locked
uv run --locked newfakenews serve
```

브라우저에서 [http://127.0.0.1:8000](http://127.0.0.1:8000)을 열고 **항생제와 감기** 예시를 선택한 뒤 **근거 확인**을 누르면 CDC 자료와 판정을 볼 수 있습니다.

### CLI와 API

```sh
uv run --locked newfakenews check '항생제는 감기 바이러스를 치료한다.'
uv run --locked newfakenews check --language en 'Pluto was reclassified as a dwarf planet in 2006.'
curl http://127.0.0.1:8000/api/v1/check \
  -H 'Content-Type: application/json' \
  -d '{"claim":"지구 자전축의 기울기가 계절 변화의 원인이다."}'
```

CLI에는 `-`를 전달해 표준 입력으로 주장을 읽을 수 있습니다. API는 `claim` 8~500자와 선택적인 `language` (`auto`, `ko`, `en`), `online` (기본값 `false`)을 받습니다. JSON 스키마는 실행 중인 앱의 [OpenAPI 문서](http://127.0.0.1:8000/openapi.json)에서 확인할 수 있습니다.

### Google 팩트체크 검색

Google Cloud에서 [Fact Check Tools API](https://developers.google.com/fact-check/tools/api)를 켜고 API 키를 `GOOGLE_FACTCHECK_API_KEY` 환경 변수에 설정한 뒤 앱을 다시 시작하세요. 웹에서 **Google 팩트체크 검색**을 선택하거나 CLI에서 `--online`을 사용하면 입력한 주장과 언어만 검색 요청에 포함합니다. 기본값에서는 앱이 로컬 자료만 확인합니다. API 키는 서버나 CLI 프로세스에서만 읽습니다.

Google에 대응하는 검증 자료가 없거나 API 요청이 실패해도 로컬 검색 결과를 볼 수 있습니다. 외부 검색 결과는 Google이 색인한 팩트체크 기사와 조회한 첫 페이지로 제한됩니다.

### Chrome 확장 프로그램

1. 앱을 기본 포트 `8000`에서 실행합니다.
2. `chrome://extensions`에서 **개발자 모드**를 켜고 **압축해제된 확장 프로그램을 로드합니다**를 선택합니다.
3. 저장소의 `extension` 폴더를 선택합니다.
4. 웹 페이지에서 문장을 선택하고 우클릭한 뒤 **NewFakeNewsDetector에서 선택 문장 확인**을 누릅니다. 새 탭에서 문장을 확인하고 직접 검증을 실행하세요.

확장 프로그램은 문장 선택 메뉴와 앱 열기만 사용합니다. 전체 페이지나 방문 기록을 읽는 권한은 요청하지 않습니다.

## 자료 범위와 추가 방법

기본 자료에는 AFP 팩트체크, USGS, CDC, NASA, NOAA 자료가 연결된 **10개 주장 문장**이 들어 있습니다. 새로운 뉴스의 진위를 자동으로 판정할 수 있는 범용 데이터셋은 아닙니다. 정확히 일치하는 검증 자료가 없으면 **판정 보류**가 표시되며, 관련 자료가 있으면 원문을 열어 비교할 수 있습니다. 사건의 날짜와 장소, 수치처럼 주장에 필요한 맥락도 함께 입력하세요.

별도 JSON 파일을 추가하려면 `FAKENEWS_CATALOG`를 파일 경로로 지정하세요. 레코드 형식은 [기본 자료](src/newfakenewsdetector/data/catalog.json)를 참고하면 됩니다. 각 주장은 `claim`, `language`, `evidence`를 가지며, 근거 항목에는 `publisher`, `title`, `url`이 필수입니다. `date`, `summary`, `original_rating`, `stance`는 선택 항목입니다. 일치하는 두 출처가 서로 다른 평가를 내리면 양쪽 근거를 보여줍니다.

## 개발

```sh
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv build
```

[MIT 라이선스](LICENSE)
