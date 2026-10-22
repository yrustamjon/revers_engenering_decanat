import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
export default function setup(){
  if(process.env.UNIFLOW_E2E!=='1')throw new Error('Run browser tests with scripts/test-e2e.sh in an isolated development database.');
  const root=resolve(import.meta.dirname,'../..');
  const python=process.env.E2E_PYTHON||(existsSync(resolve(root,'.venv/bin/python'))?resolve(root,'.venv/bin/python'):'python');
  execFileSync(python,['backend/manage.py','migrate','--noinput'],{cwd:root,stdio:'inherit'});
  execFileSync(python,['backend/manage.py','seed_e2e'],{cwd:root,stdio:'inherit'});
}
