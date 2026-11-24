const APP_URL = "http://127.0.0.1:8000/";
const MENU_ITEM = "check-factual-claim";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: MENU_ITEM,
    title: "NewFakeNewsDetector에서 선택 문장 확인",
    contexts: ["selection"],
  });
});

chrome.contextMenus.onClicked.addListener(({menuItemId, selectionText}) => {
  if (menuItemId !== MENU_ITEM || !selectionText?.trim()) return;
  const text = selectionText.trim();
  const selection = text.length > 500 ? {selection: "too-long"} : {claim: text};
  chrome.tabs.create({url: APP_URL + "#" + new URLSearchParams(selection)});
});

chrome.action.onClicked.addListener(() => {
  chrome.tabs.create({url: APP_URL});
});
