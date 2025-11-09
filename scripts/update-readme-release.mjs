#!/usr/bin/env node
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');
const README_PATH = path.join(ROOT_DIR, 'README.md');
const CHANGELOG_PATH = path.join(ROOT_DIR, 'CHANGELOG.md');
const MARKER_START = '<!-- RELEASE_HIGHLIGHTS_START -->';
const MARKER_END = '<!-- RELEASE_HIGHLIGHTS_END -->';
const MAX_RELEASES = 5;

const cleanItem = (raw) => {
  let text = raw.replace(/^\*\s*/, '');
  text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
  text = text.replace(/\s*\([0-9a-f]{7,}\)$/i, '');
  text = text.replace(/\s+/g, ' ').trim();
  if (!/[.!?]$/.test(text)) {
    text += '.';
  }
  return text;
};

const parseChangelog = async () => {
  const changelogRaw = await readFile(CHANGELOG_PATH, 'utf8');
  const releases = [];
  const releaseRegex = /^#{1,2} \[?(\d+\.\d+\.\d+)\]?[^\n]*\((\d{4}-\d{2}-\d{2})\)\n([\s\S]*?)(?=^#{1,2} \[?\d+\.\d+\.\d+\]?|\Z)/gm;

  let match;
  while ((match = releaseRegex.exec(changelogRaw)) && releases.length < MAX_RELEASES) {
    const [, version, date, body] = match;
    const sections = [];

    const sectionRegex = /###\s+(.+?)\s*[\r\n]+([\s\S]*?)(?=^###\s|\Z)/gm;
    let sectionMatch;
    while ((sectionMatch = sectionRegex.exec(body))) {
      const [, title, sectionBody] = sectionMatch;
      const items = sectionBody
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line.startsWith('* '))
        .map(cleanItem);

      if (items.length) {
        sections.push({ title, items });
      }
    }

    if (!sections.length) {
      const fallbackItems = body
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line.startsWith('* '))
        .map(cleanItem);

      if (fallbackItems.length) {
        sections.push({ title: 'Changes', items: fallbackItems });
      }
    }

    releases.push({ version, date, sections });
  }

  return releases;
};

const buildReleaseMarkdown = (releases) => {
  return releases
    .map((release) => {
      const header = `### v${release.version} (${release.date})`;
      if (!release.sections.length) {
        return `${header}\n\n- _No notable changes recorded._`;
      }

      const bullets = release.sections
        .filter((section) => section.items.length)
        .map((section) => {
          const items = section.items.join(' ');
          return `- **${section.title}**: ${items}`;
        });

      return `${header}\n\n${bullets.join('\n')}`;
    })
    .join('\n\n');
};

const updateReadme = async () => {
  const [readmeRaw, releases] = await Promise.all([
    readFile(README_PATH, 'utf8'),
    parseChangelog(),
  ]);

  const startIndex = readmeRaw.indexOf(MARKER_START);
  const endIndex = readmeRaw.indexOf(MARKER_END);

  if (startIndex === -1 || endIndex === -1 || endIndex < startIndex) {
    throw new Error('Release highlight markers not found in README.md');
  }

  const before = readmeRaw.slice(0, startIndex + MARKER_START.length);
  const after = readmeRaw.slice(endIndex);

  const releaseMarkdown = buildReleaseMarkdown(releases);
  const updated = `${before}\n${releaseMarkdown}\n${after}`;

  if (updated !== readmeRaw) {
    await writeFile(README_PATH, updated, 'utf8');
    console.log('README.md release highlights updated.');
  } else {
    console.log('README.md release highlights already up to date.');
  }
};

updateReadme().catch((error) => {
  console.error(error);
  process.exit(1);
});
