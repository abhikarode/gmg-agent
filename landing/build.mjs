import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { chromium } from "playwright";

const feedUrl = "https://www.garjemarathi.com/feed?cat=34556";
const marker = "<!-- GMG_NEWS_ITEMS -->";
const dateFormat = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
  timeZone: "UTC",
});

function escapeHtml(value) {
  const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return value.replace(/[&<>"']/g, (character) => entities[character]);
}

async function readNews() {
  const browser = await chromium.launch();
  try {
    // A fresh browser context reads the same public feed as a signed-out visitor.
    const page = await browser.newPage({ locale: "en-US", acceptDownloads: false });
    await page.goto(feedUrl, { waitUntil: "domcontentloaded", timeout: 25_000 });
    const titles = page.locator("#campus_feed_cards .ellipsis-2-lines.hover-primary");
    await titles.first().waitFor({ timeout: 25_000 });
    if (page.url() !== feedUrl) throw new Error("GMG NewsCorner redirected away from the public news category.");

    return await page.locator("#campus_feed_cards > div").evaluateAll((cards) => cards.map((card) => ({
      title: card.querySelector(".ellipsis-2-lines.hover-primary")?.textContent?.trim(),
      date: card.querySelector(".icon-event_note + span")?.textContent?.trim(),
    })));
  } finally {
    await browser.close();
  }
}

const destination = process.argv[2];
if (!destination) throw new Error("Provide a directory for the static site.");

const headlines = (await readNews()).flatMap(({ title, date }) => {
  if (!title || !date || !/^[A-Z][a-z]{2} \d{1,2}, \d{4}$/.test(date)) return [];
  const published = new Date(Date.parse(`${date} UTC`));
  if (!Number.isFinite(published.valueOf()) || published.valueOf() > Date.now()) return [];
  return [{ title, published }];
}).sort((first, second) => second.published - first.published).slice(0, 3);

// Fail before creating the deployment when the feed is unavailable or its markup changes.
if (headlines.length === 0) throw new Error("GMG NewsCorner returned no dated headlines. Keep the last published snapshot.");

const rows = headlines.map(({ title, published }) => {
  const lang = /\p{Script=Devanagari}/u.test(title) ? ' lang="mr"' : "";
  const date = published.toISOString().slice(0, 10);
  return `<li><time datetime="${date}">${dateFormat.format(published)}</time><span${lang}>${escapeHtml(title)}</span></li>`;
});
const template = await readFile(new URL("./index.html", import.meta.url), "utf8");
if (!template.includes(marker)) throw new Error("The landing page has no NewsCorner insertion point.");

await mkdir(destination, { recursive: true });
for (const file of ["landing.css", "staticwebapp.config.json"]) {
  await copyFile(new URL(`./${file}`, import.meta.url), join(destination, file));
}
await copyFile(new URL("./landing.js", import.meta.url), join(destination, "landing-flex-desk.js"));
await copyFile(new URL("../public/garje-marathi-logo.png", import.meta.url), join(destination, "garje-marathi-logo.png"));
await copyFile(new URL("../app/icon.jpg", import.meta.url), join(destination, "gmg-favicon.jpg"));
await writeFile(join(destination, "index.html"), template.replace(marker, () => `<ul class="news-list">${rows.join("")}</ul>`));
console.log(`Built landing page with ${headlines.length} GMG NewsCorner headlines.`);
