/**
 * article-core.js — Shared library for article-craft plugin
 *
 * Exports 3 functions:
 *   loadConfig()           — reads ~/.claude/env.json, returns config object
 *   resolveScriptPath(name) — returns absolute path to shared Python script
 *   findSkills(pluginDir)  — scans skills/ subdirs, extracts YAML frontmatter
 */

const fs = require('fs');
const path = require('path');

const PLUGIN_ROOT = process.env.CLAUDE_PLUGIN_ROOT || path.join(process.env.HOME, '.claude/plugins/article-craft');

const SCRIPTS_DIR = path.join(PLUGIN_ROOT, 'scripts');

const ENV_JSON_PATH = path.join(process.env.HOME, '.claude/env.json');

/**
 * Read unified config from ~/.claude/env.json
 * Returns relevant keys: gemini_api_key, gemini_image_model, s3, wechat_*, timeouts
 */
function loadConfig() {
  try {
    const raw = fs.readFileSync(ENV_JSON_PATH, 'utf-8');
    return JSON.parse(raw);
  } catch (e) {
    return {};
  }
}

/**
 * Resolve absolute path to a shared Python script in article-craft/scripts/
 * Throws if the file does not exist.
 */
function resolveScriptPath(name) {
  const full = path.join(SCRIPTS_DIR, name);
  if (!fs.existsSync(full)) {
    throw new Error(
      `article-craft: script not found: ${full}\n` +
      `Check ${SCRIPTS_DIR} directory`
    );
  }
  return full;
}

/**
 * Scan skills/ subdirectories, extract YAML frontmatter from SKILL.md files.
 * Returns array of { name, description, path, skillFile }
 */
function findSkills(pluginDir) {
  const skillsDir = path.join(pluginDir || PLUGIN_ROOT, 'skills');
  if (!fs.existsSync(skillsDir)) return [];

  return fs.readdirSync(skillsDir, { withFileTypes: true })
    .filter(d => d.isDirectory())
    .map(d => {
      const skillFile = path.join(skillsDir, d.name, 'SKILL.md');
      if (!fs.existsSync(skillFile)) return null;

      const content = fs.readFileSync(skillFile, 'utf-8');
      const frontmatter = extractFrontmatter(content);
      return {
        name: frontmatter.name || `article-craft:${d.name}`,
        description: frontmatter.description || '',
        path: path.join(skillsDir, d.name),
        skillFile
      };
    })
    .filter(Boolean);
}

/**
 * Extract YAML frontmatter from a SKILL.md file content string.
 * Returns { name, description } or empty object if no frontmatter.
 */
function extractFrontmatter(content) {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return {};

  const yaml = match[1];
  const result = {};
  const nameMatch = yaml.match(/^name:\s*(.+)$/m);
  const descMatch = yaml.match(/^description:\s*["']?([\s\S]*?)["']?\s*$/m);
  if (nameMatch) result.name = nameMatch[1].trim();
  if (descMatch) result.description = descMatch[1].trim();
  return result;
}

module.exports = { loadConfig, resolveScriptPath, findSkills };
