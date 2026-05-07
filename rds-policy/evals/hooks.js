const path = require('path');
const { execSync } = require('child_process');
const fs = require('fs');

const workspacePath = path.join(__dirname, 'fixtures');
const skillSrc = path.join(__dirname, '..', 'rds_agent', 'skills', 'rds-policy-update');
const skillDest = path.join(workspacePath, '.claude', 'skills', 'rds-policy-update');

function extensionHook(hookName, context) {
  // Copy skill into fixtures/.claude/skills/ so the agent can load it
  if (hookName === 'beforeAll') {
    try {
      fs.mkdirSync(path.join(workspacePath, '.claude', 'skills'), { recursive: true });
      execSync(`cp -r "${skillSrc}" "${skillDest}"`, { stdio: 'pipe' });
    } catch (error) {
      console.error('Skill copy failed:', error.message);
      throw error;
    }
  // Remove .claude/ copy
  } else if (hookName === 'afterAll') {
    try {
      const claudeDir = path.join(workspacePath, '.claude');
      if (fs.existsSync(claudeDir)) {
        fs.rmSync(claudeDir, { recursive: true, force: true });
      }
    } catch (error) {
      console.error('Cleanup failed:', error.message);
    }
  }
}

module.exports = extensionHook;