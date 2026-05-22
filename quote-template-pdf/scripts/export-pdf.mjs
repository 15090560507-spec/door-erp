import path from "node:path";
import { fileURLToPath } from "node:url";
import { renderQuoteArtifacts } from "../src/exportArtifacts.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(projectRoot, "..");
const outputDir = path.join(repoRoot, "output");
const quotePath = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(projectRoot, "data", "sample-quote.json");
const result = await renderQuoteArtifacts({ quotePath, outputDir });
console.log(`HTML: ${result.htmlPath}`);
console.log(`PDF: ${result.pdfPath}`);
console.log(`JPG: ${result.jpgPath}`);
console.log(`Preview: ${result.previewPath}`);
