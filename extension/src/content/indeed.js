// Indeed JD extractor. Same contract as the LinkedIn script.

const TITLE_SELECTORS = [
  "h1.jobsearch-JobInfoHeader-title",
  "[data-testid='jobsearch-JobInfoHeader-title']",
  "h1",
];
const COMPANY_SELECTORS = [
  "[data-testid='inlineHeader-companyName'] a",
  "[data-testid='inlineHeader-companyName']",
  ".jobsearch-CompanyInfoContainer a",
  ".jobsearch-InlineCompanyRating div",
];
const LOCATION_SELECTORS = [
  "[data-testid='inlineHeader-companyLocation']",
  ".jobsearch-CompanyInfoContainer div:nth-of-type(2)",
];
const DESCRIPTION_SELECTORS = [
  "#jobDescriptionText",
  "[data-testid='jobsearch-JobDescriptionSection']",
];

function firstText(selectors) {
  for (const sel of selectors) {
    const el = document.querySelector(sel);
    if (el && el.textContent && el.textContent.trim().length > 0) {
      return el.textContent.trim().replace(/\s+/g, " ");
    }
  }
  return null;
}

function descriptionText() {
  for (const sel of DESCRIPTION_SELECTORS) {
    const el = document.querySelector(sel);
    if (el && el.innerText && el.innerText.trim().length > 100) {
      return el.innerText.trim();
    }
  }
  return null;
}

function extract() {
  return {
    source: "indeed",
    url: window.location.href,
    title: firstText(TITLE_SELECTORS),
    company: firstText(COMPANY_SELECTORS),
    location: firstText(LOCATION_SELECTORS),
    raw_jd: descriptionText(),
    captured_at: new Date().toISOString(),
  };
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "EXTRACT_JD") {
    const payload = extract();
    sendResponse({ ok: true, payload });
    return true;
  }
  return false;
});
