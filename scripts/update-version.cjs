'use strict';

const fs = require('fs');
const path = require('path');

const newVersion = process.argv[2];
const releaseType = process.argv[3] || '';

if (!newVersion) {
  console.error('Usage: node scripts/update-version.cjs <version> [releaseType]');
  process.exit(1);
}

const projectRoot = path.join(__dirname, '..');

const updateJsonFile = (relativePath, updater) => {
  const filePath = path.join(projectRoot, relativePath);
  const json = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  updater(json);
  fs.writeFileSync(filePath, JSON.stringify(json, null, 2) + '\n', 'utf8');
};

updateJsonFile('package.json', (pkg) => {
  pkg.version = newVersion;
});

updateJsonFile('package-lock.json', (lock) => {
  lock.version = newVersion;
  if (lock.packages && lock.packages['']) {
    lock.packages[''].version = newVersion;
  }
});

const shouldUpdateReadme = ['major', 'minor'].includes(releaseType.toLowerCase());

if (!shouldUpdateReadme) {
  process.exit(0);
}

const changelogPath = path.join(projectRoot, 'CHANGELOG.md');
const readmePath = path.join(projectRoot, 'README.md');

const changelogContent = fs.readFileSync(changelogPath, 'utf8');

const lines = changelogContent.split(/\r?\n/);
const releaseHeadingRegex = new RegExp(`^#{1,2} \\[${newVersion.replace(/\./g, '\\.')}]`);
const releaseStartIndex = lines.findIndex((line) => releaseHeadingRegex.test(line));

if (releaseStartIndex === -1) {
  console.warn(`Could not locate release ${newVersion} in CHANGELOG.md; skipping README highlights update.`);
  process.exit(0);
}

const isReleaseHeading = (line) => /^#{1,2} \[/.test(line);

let releaseEndIndex = releaseStartIndex + 1;
while (releaseEndIndex < lines.length && !isReleaseHeading(lines[releaseEndIndex])) {
  releaseEndIndex += 1;
}

const releaseSectionLines = lines.slice(releaseStartIndex, releaseEndIndex);
const headingLine = releaseSectionLines[0];
const dateMatch = headingLine.match(/\(([^)]+)\)/);
const releaseDate = dateMatch ? dateMatch[1] : '';

const parsedSections = [];
let currentSection = null;

for (let i = 1; i < releaseSectionLines.length; i += 1) {
  const line = releaseSectionLines[i].trim();
  if (!line) {
    continue;
  }

  if (line.startsWith('### ')) {
    const title = line.replace(/^###\s+/, '').trim();
    currentSection = { title, items: [] };
    parsedSections.push(currentSection);
    continue;
  }

  if (line.startsWith('* ')) {
    if (!currentSection) {
      currentSection = { title: 'Changes', items: [] };
      parsedSections.push(currentSection);
    }
    currentSection.items.push(line.replace(/^\*\s+/, '').trim());
  }
}

const buildReleaseHighlight = () => {
  const headerLine = `### v${newVersion}${releaseDate ? ` (${releaseDate})` : ''}`;
  const buffer = [headerLine, ''];

  if (parsedSections.length === 0) {
    buffer.push('- Refer to the [changelog](CHANGELOG.md) for detailed notes.');
  } else {
    parsedSections.forEach((section) => {
      if (!section.items.length) {
        return;
      }
      buffer.push(`- **${section.title}**`);
      section.items.forEach((item) => {
        buffer.push(`  - ${item}`);
      });
    });
  }

  buffer.push('');
  return buffer.join('\n');
};

const newEntry = buildReleaseHighlight();

const readmeContent = fs.readFileSync(readmePath, 'utf8');
const releaseSectionRegex = /(## Release Highlights\n)([\s\S]*?)(?=\n## [^\n]+\n)/;
const match = releaseSectionRegex.exec(readmeContent);

if (!match) {
  console.warn('Release Highlights section not found in README.md; skipping insert.');
  process.exit(0);
}

const existingContent = match[2];
const entryPattern = new RegExp(`### v${newVersion.replace(/\./g, '\\.')}`);

const prunedContent = existingContent
  .split(/\n{2,}/)
  .filter((block) => block && !entryPattern.test(block))
  .join('\n\n');



const updatedContent = `${newEntry}\n${prunedContent ? `${prunedContent}\n` : ''}`;

const updatedReadme =
  readmeContent.slice(0, match.index) +
  match[1] +
  updatedContent +
  readmeContent.slice(match.index + match[0].length);

fs.writeFileSync(readmePath, updatedReadme.replace(/\n{3,}/g, '\n\n'), 'utf8');
