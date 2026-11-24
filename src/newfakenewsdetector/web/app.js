const form = document.querySelector("#check-form");
const claim = document.querySelector("#claim");
const language = document.querySelector("#language");
const online = document.querySelector("#online");
const onlineHelp = document.querySelector("#online-help");
const count = document.querySelector("#count");
const submit = document.querySelector("#submit");
const empty = document.querySelector("#empty");
const result = document.querySelector("#result");
const resultCount = document.querySelector("#result-count");
const status = document.querySelector("#status");
const error = document.querySelector("#error");

const verdicts = {
  supported: ["출처 자료가 뒷받침함", "일치하는 주장에 대해 출처가 뒷받침하는 근거를 제공합니다."],
  refuted: ["출처 자료가 반박함", "일치하는 주장에 대해 출처가 반박하는 근거를 제공합니다."],
  mixed: ["출처 평가가 부분적임", "일치하는 주장에 대해 출처가 참과 거짓이 섞여 있다고 평가했습니다."],
  conflicting: ["출처 평가가 다름", "일치하는 주장에 대한 출처의 평가가 다릅니다. 원문을 확인하세요."],
  review_found: ["검증 자료 발견", "일치하는 주장의 검증 자료를 찾았습니다. 출처별 평가를 확인하세요."],
  insufficient: ["판정 보류", "일치하는 주장을 다룬 검증 자료를 찾지 못했습니다."],
};

function element(tag, value, className) {
  const node = document.createElement(tag);
  if (value) node.textContent = value;
  if (className) node.className = className;
  return node;
}

function updateCount() {
  count.textContent = `${claim.value.length} / 500자`;
}

function restoreSelection() {
  const params = new URLSearchParams(location.hash.slice(1));
  const selection = params.get("claim");
  const tooLong = params.get("selection") === "too-long" || (selection?.length ?? 0) > 500;
  if (selection === null && !tooLong) return;
  if (tooLong) {
    error.textContent = "선택한 문장이 500자를 넘습니다. 더 짧은 주장 한 문장을 선택하세요.";
    error.hidden = false;
  } else {
    claim.value = selection;
    error.hidden = true;
  }
  language.value = "auto";
  online.checked = false;
  history.replaceState(null, "", location.pathname + location.search);
  claim.focus();
  updateCount();
}

async function loadConfig() {
  try {
    const response = await fetch("/api/v1/config");
    if (!response.ok) throw new Error("Configuration unavailable");
    const config = await response.json();
    online.disabled = !config.online_available;
    onlineHelp.textContent = config.online_available
      ? "선택하면 입력한 주장이 Google로 전송됩니다."
      : "API 키가 없어서 로컬 자료만 검색합니다.";
  } catch {
    onlineHelp.textContent = "온라인 검색 설정을 불러오지 못했습니다.";
  }
}

function renderSource(source) {
  const item = element("div", null, "source");
  const link = element("a", source.title + " ↗");
  link.href = source.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  item.append(link, element("span", [source.publisher, source.date].filter(Boolean).join(" · ")));
  if (source.original_rating) item.append(element("span", "출처 평가 · " + source.original_rating));
  if (source.summary) item.append(element("span", source.summary));
  return item;
}

function renderMatches(matches, title) {
  const group = element("section", null, "match-group");
  const list = element("ul", null, "match-list");
  for (const match of matches) {
    const item = element("li", null, "match");
    const provider = match.provider === "google" ? "Google Fact Check" : "로컬 자료";
    item.append(element("p", provider, "provider-name"), element("p", match.claim));
    item.append(...match.evidence.map(renderSource));
    list.append(item);
  }
  group.append(element("h3", title), list);
  return group;
}

function render(data) {
  const [title, detail] = verdicts[data.verdict];
  const verdict = element("div", null, "verdict");
  verdict.dataset.verdict = data.verdict;
  verdict.append(
    element("h3", title),
    element("p", data.claim, "input-quote"),
    element("p", detail),
  );
  if (data.online_status === "unavailable" || data.online_status === "unconfigured") {
    verdict.append(element("p", "온라인 검색을 사용할 수 없어 로컬 자료만 확인했습니다."));
  }
  result.replaceChildren(verdict);
  for (const [type, label] of [["exact", "일치하는 검증 자료"], ["related", "관련 자료"]]) {
    const matches = data.matches.filter((match) => match.match === type);
    if (matches.length) result.append(renderMatches(matches, label));
  }
  resultCount.textContent = `주장 ${data.matches.length}건`;
  resultCount.hidden = false;
  empty.hidden = true;
  result.hidden = false;
  status.textContent = title;
}

claim.addEventListener("input", updateCount);
window.addEventListener("hashchange", restoreSelection);
for (const button of document.querySelectorAll("[data-claim]")) {
  button.addEventListener("click", () => {
    claim.value = button.dataset.claim;
    language.value = "auto";
    updateCount();
    claim.focus();
  });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (submit.disabled) return;
  submit.disabled = true;
  error.hidden = true;
  result.hidden = true;
  resultCount.hidden = true;
  empty.hidden = false;
  empty.querySelector("p").textContent = "검증 자료를 확인하고 있습니다.";
  status.textContent = "검색 중";
  try {
    const response = await fetch("/api/v1/check", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        claim: claim.value, language: language.value, online: !online.disabled && online.checked,
      }),
    });
    if (response.status === 422) {
      error.textContent = "8자 이상, 500자 이하의 주장 한 문장을 입력하세요.";
      error.hidden = false;
      return;
    }
    if (!response.ok) throw new Error("Check unavailable");
    render(await response.json());
  } catch {
    error.textContent = "검색에 실패했습니다. 앱이 실행 중인지 확인하고 다시 시도하세요.";
    error.hidden = false;
  } finally {
    if (result.hidden) {
      status.textContent = "";
      empty.querySelector("p").textContent = "아직 확인한 주장이 없습니다.";
    }
    submit.disabled = false;
  }
});

restoreSelection();
updateCount();
loadConfig();
