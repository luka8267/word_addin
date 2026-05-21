const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..");
const source = path.join(repoRoot, "bunkenn", "word-app", "static");
const destination = path.join(repoRoot, "public");

fs.rmSync(destination, { recursive: true, force: true });
fs.cpSync(source, destination, { recursive: true });
console.log(`copied ${source} -> ${destination}`);
