'use strict';

const fs = require('fs');
const path = require('path');

const newVersion = process.argv[2];

if (!newVersion) {
  console.error('Usage: node scripts/update-version.cjs <version>');
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
