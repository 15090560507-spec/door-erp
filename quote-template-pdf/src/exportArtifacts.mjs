import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { buildQuoteHtml } from "./renderQuote.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(projectRoot, "..");

async function exists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch {
    return await import(pathToFileURL(path.join(repoRoot, "frontend", "node_modules", "playwright", "index.mjs")).href);
  }
}

async function launchBrowser(chromium) {
  const envPath = process.env.PLAYWRIGHT_EXECUTABLE_PATH;
  if (envPath && await exists(envPath)) {
    return chromium.launch({ headless: true, executablePath: envPath });
  }

  try {
    return await chromium.launch({ headless: true });
  } catch (error) {
    const candidates = [
      "/usr/bin/chromium",
      "/usr/bin/chromium-browser",
      "/usr/bin/google-chrome",
      "/usr/bin/google-chrome-stable",
      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
      "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    ];

    for (const executablePath of candidates) {
      if (await exists(executablePath)) {
        return chromium.launch({ headless: true, executablePath });
      }
    }

    throw error;
  }
}

export async function renderQuoteArtifacts({ quotePath, outputDir }) {
  const htmlPath = path.join(outputDir, "quote.html");
  const pdfPath = path.join(outputDir, "quote.pdf");
  const jpgPath = path.join(outputDir, "quote.jpg");
  const previewPath = path.join(outputDir, "quote-preview.png");

  await fs.mkdir(outputDir, { recursive: true });

  const html = await buildQuoteHtml(quotePath);
  await fs.writeFile(htmlPath, html, "utf8");

  const { chromium } = await loadPlaywright();
  const browser = await launchBrowser(chromium);

  try {
    const page = await browser.newPage({
      viewport: {
        width: 794,
        height: 1123,
        deviceScaleFactor: 2,
      },
    });

    await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
    await page.emulateMedia({ media: "print" });

    await page.pdf({
      path: pdfPath,
      printBackground: true,
      preferCSSPageSize: true,
    });

    await page.screenshot({
      path: jpgPath,
      type: "jpeg",
      quality: 92,
      fullPage: true,
    });

    await page.screenshot({
      path: previewPath,
      fullPage: true,
    });
  } finally {
    await browser.close();
  }

  return {
    htmlPath,
    pdfPath,
    jpgPath,
    previewPath,
  };
}

