// Run after npm install; same parser family as Dify's browser-side validation.
const fs = require('node:fs');
const path = require('node:path');
const yaml = require('js-yaml');
const dir = __dirname;
const expected = JSON.parse(fs.readFileSync(path.join(dir, 'workflow-3.1.json'), 'utf8'));
const docs = yaml.loadAll(fs.readFileSync(path.join(dir, 'music-visual-style-3.1.yml'), 'utf8'));
if (docs.length !== 1 || JSON.stringify(docs[0]) !== JSON.stringify(expected)) throw new Error('DSL and JSON differ');
console.log('Dify browser YAML compatibility: PASS');
