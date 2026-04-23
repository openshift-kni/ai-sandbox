const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const workspacePath = path.join(__dirname, 'fixtures');
const skillSrc = path.join(__dirname, '..', 'rds_agent', 'skills', 'rds-policy-update');
const skillDest = path.join(workspacePath, '.claude', 'skills', 'rds-policy-update');

function getPartnerDirs() {
  return fs.readdirSync(workspacePath)
    .filter(d => d.startsWith('partner-'))
    .map(d => path.join(workspacePath, d))
    .filter(d => fs.statSync(d).isDirectory());
}

function extensionHook(hookName, context) {
  if (hookName === 'beforeAll') {
    try {
      fs.mkdirSync(path.join(workspacePath, '.claude', 'skills'), { recursive: true });
      execSync(`cp -r "${skillSrc}" "${skillDest}"`, { stdio: 'pipe' });
    } catch (error) {
      console.error('Skill copy failed:', error.message);
      throw error;
    }

    for (const dir of getPartnerDirs()) {
      const gitDir = path.join(dir, '.git');
      try {
        if (!fs.existsSync(gitDir)) {
          execSync('git init && git add -A && git commit -m "fixture baseline"', {
            cwd: dir,
            stdio: 'pipe',
            env: {
              ...process.env,
              GIT_AUTHOR_NAME: 'eval',
              GIT_AUTHOR_EMAIL: 'eval@test',
              GIT_COMMITTER_NAME: 'eval',
              GIT_COMMITTER_EMAIL: 'eval@test',
            },
          });
        }
      } catch (error) {
        console.error(`Git init failed for ${path.basename(dir)}:`, error.message);
        throw error;
      }
    }
  } else if (hookName === 'afterEach') {
    for (const dir of getPartnerDirs()) {
      try {
        execSync('git reset --hard HEAD && git clean -fd', {
          cwd: dir,
          stdio: 'pipe',
        });
      } catch (error) {
        console.error(`Git reset failed for ${path.basename(dir)}:`, error.message);
        throw error;
      }
    }
  } else if (hookName === 'afterAll') {
    for (const dir of getPartnerDirs()) {
      const gitDir = path.join(dir, '.git');
      try {
        if (fs.existsSync(gitDir)) {
          fs.rmSync(gitDir, { recursive: true, force: true });
        }
      } catch (error) {
        console.error(`Cleanup failed for ${path.basename(dir)}:`, error.message);
      }
    }
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
