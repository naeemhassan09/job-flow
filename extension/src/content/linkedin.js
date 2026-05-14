// LinkedIn JD extractor. Runs only when the user navigates to a job page
// (matches in manifest.json). Acts only on explicit message from popup —
// nothing is sent automatically.

const TITLE_SELECTORS = [
  ".job-details-jobs-unified-top-card__job-title",
  ".jobs-unified-top-card__job-title",
  ".topcard__title",
  "h1",
];
const COMPANY_SELECTORS = [
  ".job-details-jobs-unified-top-card__company-name a",
  ".job-details-jobs-unified-top-card__company-name",
  ".jobs-unified-top-card__company-name",
  ".topcard__org-name-link",
];
const LOCATION_SELECTORS = [
  ".job-details-jobs-unified-top-card__primary-description-container",
  ".jobs-unified-top-card__bullet",
  ".topcard__flavor--bullet",
];
const DESCRIPTION_SELECTORS = [
  ".jobs-description-content__text",
  ".jobs-description__content",
  ".show-more-less-html__markup",
  "#job-details",
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
    source: "linkedin",
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
