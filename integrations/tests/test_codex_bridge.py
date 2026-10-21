import importlib.util
import json
import os
from pathlib import Path
import sys
import signal
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / 'codex_bridge.py'
SPEC = importlib.util.spec_from_file_location('codex_bridge_tests_module', MODULE_PATH)
bridge = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bridge
SPEC.loader.exec_module(bridge)

SESSION_ID = '01234567-89ab-cdef-0123-456789abcdef'
FAKE_TOKEN = '123456:unit_test_fake_value_not_real_12345'


class CodexBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='uniflow-codex-test-', dir='/tmp')
        self.directory = Path(self.tmp.name)
        self.fake = self.directory / 'codex-test-executable'
        self.fake.write_text(f'#!{sys.executable}\n' + '''
import json,os,sys,time,signal
prompt=sys.stdin.read()
assert 'tg_key' not in os.environ and 'UNIFLOW_TELEGRAM_TOKEN' not in os.environ
mode=sys.argv[sys.argv.index('-s')+1]
assert mode in ['read-only','workspace-write']
thread='01234567-89ab-cdef-0123-456789abcdef'
if 'resume' in sys.argv:
 assert sys.argv[sys.argv.index('resume')+2] == thread
if 'SIMULATE_MISSING_SESSION' in prompt:
 print(json.dumps({'type':'error','message':'No saved session found'}),flush=True);sys.exit(1)
if 'SIMULATE_READONLY' in prompt:
 print('Read-only file system (os error 30)',file=sys.stderr,flush=True);sys.exit(1)
if 'SIMULATE_NETWORK' in prompt:
 print(json.dumps({'type':'error','message':'WebSocket proxy CONNECT failed: HTTP 403 Forbidden'}),flush=True);sys.exit(1)
if 'SIMULATE_PROXY_WAIT' in prompt:
 print('HTTP CONNECT failed, status code: 403; Reconnecting...',file=sys.stderr,flush=True);time.sleep(30)
if 'SIMULATE_PROVIDER_AUTH_WAIT' in prompt:
 print('provider responses unexpected status 401 Unauthorized; Reconnecting...',file=sys.stderr,flush=True);time.sleep(30)
if 'SIMULATE_AUTH' in prompt:
 print(json.dumps({'type':'error','message':'401 Unauthorized'}),flush=True);sys.exit(1)
if 'SIMULATE_CHANGED_SESSION' in prompt:
 thread='11234567-89ab-cdef-0123-456789abcdef'
if 'SIMULATE_INVALID_ID' in prompt:thread='-invalid-session'
print(json.dumps({'type':'thread.started','thread_id':thread}),flush=True)
print(json.dumps({'type':'turn.started'}),flush=True)
if 'SIMULATE_DESCENDANT' in prompt or 'SIMULATE_ORPHAN' in prompt:
 pid=os.fork()
 if pid==0:
  if 'SIMULATE_DETACHED' in prompt:os.setsid()
  signal.signal(signal.SIGTERM,signal.SIG_IGN)
  os.write(1,b'')
  with open(os.environ['UNIFLOW_BRIDGE_TEST_CHILD_FILE'],'w') as f:json.dump({'pid':os.getpid(),'group':os.getpgrp()},f)
  if 'SIMULATE_CLOSED_CHILD_STDOUT' in prompt:
   os.close(1);os.close(2)
  if 'SIMULATE_ORPHAN' in prompt:
   time.sleep(1.5)
   with open(os.environ['UNIFLOW_BRIDGE_TEST_DELAYED_FILE'],'w') as f:f.write('should never execute')
  time.sleep(30);os._exit(0)
 while not os.path.exists(os.environ['UNIFLOW_BRIDGE_TEST_CHILD_FILE']):time.sleep(.005)
 if 'SIMULATE_LEADER_EXIT' in prompt:os._exit(0)
 if 'SIMULATE_ORPHAN' in prompt:time.sleep(30)
 if 'SIMULATE_CLOSED_CHILD_STDOUT' not in prompt:time.sleep(30)
if 'SIMULATE_WAIT' in prompt:time.sleep(30)
if 'SIMULATE_OVERSIZE' in prompt:print('x'*1100000,flush=True)
if 'SIMULATE_LOG_LIMIT' in prompt:
 for i in range(80):print(json.dumps({'type':'item.completed','item':{'type':'command_execution','aggregated_output':'z'*1000}}),flush=True)
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'Salom, sinov bajarildi.'}}),flush=True)
if 'SIMULATE_SECRET' in prompt:
 print('token: 123456:unit_test_fake_value_not_real_12345',file=sys.stderr,flush=True)
if 'SIMULATE_NO_COMPLETE' not in prompt:print(json.dumps({'type':'turn.completed'}),flush=True)
''', encoding='utf-8')
        self.fake.chmod(0o700)
        self.runner = bridge.CodexRunner(state_dir=self.directory / 'state', binary=str(self.fake), timeout=10)

    def tearDown(self):
        child_file = self.directory / 'child.json'
        if child_file.exists():
            # Emergency cleanup only for a live descendant created by this test.
            try:
                child = json.loads(child_file.read_text())
                raw = Path(f'/proc/{child["pid"]}/stat').read_text()
                fields = raw[raw.rfind(')') + 2:].split()
                if fields[0] not in ['Z', 'X'] and int(fields[2]) == child['group']:
                    os.kill(child['pid'], signal.SIGKILL)
            except (OSError, ValueError):
                pass
        self.tmp.cleanup()

    def child_is_alive(self):
        child = json.loads((self.directory / 'child.json').read_text())
        try:
            raw = Path(f'/proc/{child["pid"]}/stat').read_text()
            return raw[raw.rfind(')') + 2:].split()[0] not in ['Z', 'X']
        except FileNotFoundError:
            return False

    def child_environment(self):
        return {'UNIFLOW_BRIDGE_TEST_CHILD_FILE': str(self.directory / 'child.json'),
                'UNIFLOW_BRIDGE_TEST_DELAYED_FILE': str(self.directory / 'delayed-write')}

    def assert_failure(self, prompt, code, **kwargs):
        with self.assertRaises(bridge.BridgeError) as failure:
            self.runner.run(prompt, **kwargs)
        self.assertEqual(failure.exception.code, code)
        return failure.exception

    def test_initial_then_resume_same_uuid_and_mode_override(self):
        first = self.runner.run('Salom, o‘zbekcha savol.')
        second = self.runner.run('Vazifani bajar.', mode='workspace-write')
        self.assertEqual(first.reply, 'Salom, sinov bajarildi.')
        self.assertEqual(first.session_id, SESSION_ID)
        self.assertEqual(second.session_id, first.session_id)
        self.assertEqual(first.mode, 'read-only')
        self.assertEqual(second.mode, 'workspace-write')
        self.assertEqual(self.runner.status()['status'], 'completed')

    def test_cli_argv_uses_sandbox_and_stdin_no_dangerous_flags(self):
        initial = self.runner._argv('read-only', None)
        self.assertEqual(initial[-1], '-')
        self.assertIn('--no-daemon', initial)
        self.assertEqual(initial[initial.index('-a') + 1], 'never')
        self.assertEqual(initial[initial.index('-s') + 1], 'read-only')
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', initial)
        self.assertNotIn('--worktree', initial)
        resume = self.runner._argv('workspace-write', SESSION_ID)
        self.assertEqual(resume[-3:], ['--json', SESSION_ID, '-'])

    def test_stdin_does_not_execute_shell_and_token_environment_removed(self):
        marker = self.directory / 'should-not-exist'
        with patch.dict(os.environ, {'tg_key': FAKE_TOKEN, 'UNIFLOW_TELEGRAM_TOKEN': FAKE_TOKEN}):
            result = self.runner.run(f'Salom; $(touch {marker}) `touch {marker}`')
        self.assertFalse(marker.exists())
        self.assertEqual(result.session_id, SESSION_ID)

    def test_private_state_and_bounded_redacted_logs(self):
        self.runner.max_log_bytes = 16384
        result = self.runner.run('SIMULATE_LOG_LIMIT SIMULATE_SECRET')
        self.assertLessEqual(result.log_path.stat().st_size, 16384)
        self.assertEqual(result.log_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.runner.state_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.runner.state_dir.stat().st_mode & 0o777, 0o700)
        self.assertNotIn(FAKE_TOKEN, result.log_path.read_text())
        self.assertIn('Log size limit reached', result.log_path.read_text())

    def test_missing_session_preserves_id_no_automatic_reset(self):
        self.runner.run('Salom')
        self.assert_failure('SIMULATE_MISSING_SESSION', 'session_not_found')
        self.assertEqual(self.runner.status()['session_id'], SESSION_ID)

    def test_unknown_new_session_id_does_not_replace_saved_session(self):
        self.runner.run('Salom')
        self.assert_failure('SIMULATE_CHANGED_SESSION', 'session_changed')
        self.assertEqual(self.runner.status()['session_id'], SESSION_ID)

    def test_non_uuid_thread_id_rejected(self):
        self.assert_failure('SIMULATE_INVALID_ID', 'invalid_session')
        self.assertIsNone(self.runner.status()['session_id'])

    def test_network_readonly_and_authentication_failures_classified(self):
        for marker, code in [('SIMULATE_NETWORK', 'proxy_blocked'), ('SIMULATE_READONLY', 'runtime_read_only'), ('SIMULATE_AUTH', 'authentication')]:
            with self.subTest(code=code):
                failure = self.assert_failure(marker, code)
                self.assertNotIn(FAKE_TOKEN, str(failure))
                self.assertNotIn('wss://', str(failure))

    def test_explicit_proxy_denial_stops_retrying_cli_immediately(self):
        started = time.monotonic()
        self.assert_failure('SIMULATE_PROXY_WAIT', 'proxy_blocked')
        self.assertLess(time.monotonic() - started, 2)

    def test_provider_authentication_denial_stops_cli_immediately(self):
        started = time.monotonic()
        self.assert_failure('SIMULATE_PROVIDER_AUTH_WAIT', 'authentication')
        self.assertLess(time.monotonic() - started, 2)

    def test_output_without_completion_is_failure(self):
        self.assert_failure('SIMULATE_NO_COMPLETE', 'cli_failed')

    def test_oversized_event_stops_run(self):
        self.assert_failure('SIMULATE_OVERSIZE', 'output_limit')

    def test_cancel_terminates_process_and_retains_session(self):
        cancel = threading.Event()
        timer = threading.Timer(.2, cancel.set)
        timer.start()
        started = time.monotonic()
        try:
            self.assert_failure('SIMULATE_WAIT', 'cancelled', cancel_event=cancel)
        finally:
            timer.join()
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(self.runner.status()['session_id'], SESSION_ID)
        self.assertFalse(self.runner.status()['busy'])

    def test_cancel_before_start_does_not_create_cli_session(self):
        cancel = threading.Event()
        cancel.set()
        self.assert_failure('Salom', 'cancelled', cancel_event=cancel)
        self.assertFalse(self.runner.state_file.exists())

    def test_timeout_terminates_process(self):
        self.runner.timeout = .15
        self.assert_failure('SIMULATE_WAIT', 'timeout')
        self.assertFalse(self.runner.status()['busy'])

    def test_cancel_kills_sigterm_ignoring_descendant(self):
        cancel = threading.Event()
        timer = threading.Timer(.3, cancel.set)
        timer.start()
        try:
            with patch.dict(os.environ, self.child_environment()):
                self.assert_failure('SIMULATE_DESCENDANT', 'cancelled', cancel_event=cancel)
        finally:
            timer.join()
        self.assertFalse(self.child_is_alive())
        self.assertFalse(self.runner.status()['busy'])

    def test_leader_exit_with_inherited_stdout_cleans_descendant(self):
        self.runner.timeout = .3
        with patch.dict(os.environ, self.child_environment()):
            # The guardian detects native-leader exit and closes inherited pipes
            # after cleaning the child. It may finish before the runner deadline.
            with self.assertRaises(bridge.BridgeError) as failure:
                self.runner.run('SIMULATE_DESCENDANT SIMULATE_LEADER_EXIT')
        self.assertIn(failure.exception.code, ['timeout', 'cli_failed'])
        self.assertFalse(self.child_is_alive())

    def test_successful_leader_exit_cleans_child_with_closed_stdout(self):
        with patch.dict(os.environ, self.child_environment()):
            result = self.runner.run('SIMULATE_DESCENDANT SIMULATE_CLOSED_CHILD_STDOUT')
        self.assertEqual(result.session_id, SESSION_ID)
        self.assertFalse(self.child_is_alive())

    def test_already_reaped_leader_still_cleans_ignoring_child(self):
        script = '''import os,signal,time,json,sys
pid=os.fork()
if pid==0:
 signal.signal(signal.SIGTERM,signal.SIG_IGN)
 with open(sys.argv[1],'w') as f:json.dump({'pid':os.getpid(),'group':os.getpgrp()},f)
 time.sleep(30);os._exit(0)
while not os.path.exists(sys.argv[1]):time.sleep(.005)
os._exit(0)
'''
        process = subprocess.Popen([sys.executable, '-c', script, str(self.directory / 'child.json')],
                                   start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        process.wait(timeout=2)
        self.assertTrue(self.child_is_alive())
        bridge.CodexRunner._terminate(process)
        self.assertFalse(self.child_is_alive())
        # Cleanup must not inspect/re-signal a freed group ID on a second call.
        with patch.object(bridge.CodexRunner, '_live_group_members', side_effect=AssertionError('cleanup repeated')):
            bridge.CodexRunner._terminate(process)

    def test_unfinished_guardian_cleanup_keeps_guardian_alive_fail_closed(self):
        process = SimpleNamespace(pid=1234567, _uniflow_guardian=True)
        with patch.object(bridge.CodexRunner, '_live_group_members', return_value=[1234567]), \
             patch.object(bridge.os, 'killpg') as signal_group, \
             patch.object(bridge.time, 'monotonic', side_effect=[0, 3]), \
             patch.object(bridge.time, 'sleep'):
            with self.assertRaises(bridge.BridgeError) as failure:
                bridge.CodexRunner._terminate(process)
        self.assertEqual(failure.exception.code, 'cleanup_failed')
        signal_group.assert_called_once_with(1234567, signal.SIGTERM)

    def test_worker_sigkill_guardian_kills_detached_child_and_prevents_delayed_write(self):
        host_script = '''import importlib.util,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('bridge_host',sys.argv[1])
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
runner=module.CodexRunner(state_dir=Path(sys.argv[2]),binary=sys.argv[3],timeout=10)
runner.run('SIMULATE_ORPHAN SIMULATE_DETACHED')
'''
        environment = os.environ.copy()
        environment.update(self.child_environment())
        host = subprocess.Popen([sys.executable, '-c', host_script, str(MODULE_PATH), str(self.runner.state_dir), str(self.fake)],
                                env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 3
            while not (self.directory / 'child.json').exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue((self.directory / 'child.json').exists())
            self.assertTrue(self.child_is_alive())
            host.kill()
            host.wait(timeout=2)
            # The inherited flock remains held during guardian cleanup. A fresh
            # writer cannot overlap with descendants left by the killed host.
            deadline = time.monotonic() + 3
            while self.runner.status()['busy'] and time.monotonic() < deadline:
                time.sleep(.025)
            self.assertFalse(self.runner.status()['busy'])
            self.assertFalse(self.child_is_alive())
            time.sleep(1.6)
            self.assertFalse((self.directory / 'delayed-write').exists())
            self.assertEqual(self.runner.run('Yangi xavfsiz topshiriq').session_id, SESSION_ID)
        finally:
            if host.poll() is None:
                host.kill()
                host.wait(timeout=2)

    def test_reset_is_explicit_and_preserves_previous_session_id(self):
        self.runner.run('Salom')
        self.runner.reset()
        self.assertIsNone(self.runner.status()['session_id'])
        self.assertEqual(json.loads(self.runner.state_file.read_text())['previous_session_id'], SESSION_ID)
        self.assertEqual(self.runner.status()['status'], 'idle')

    def test_busy_lock_prevents_parallel_runner_and_reset(self):
        lock = self.runner._acquire()
        other = bridge.CodexRunner(state_dir=self.runner.state_dir, binary=str(self.fake))
        try:
            self.assertTrue(other.status()['busy'])
            with self.assertRaises(bridge.BridgeError) as failure:
                other.run('Salom')
            self.assertEqual(failure.exception.code, 'busy')
            with self.assertRaises(bridge.BridgeError):
                self.runner.reset()
        finally:
            self.runner._release(lock)

    def test_corrupt_state_does_not_silently_reset_or_leave_lock(self):
        self.runner.state_file.write_text('broken')
        self.runner.state_file.chmod(0o600)
        self.assert_failure('Salom', 'state_corrupt')
        self.runner.state_file.unlink()
        self.assertEqual(self.runner.run('Salom').session_id, SESSION_ID)

    def test_stale_running_status_is_interrupted(self):
        self.runner._save_state({'session_id': None, 'repo_path': str(self.runner.repo_path), 'status': 'running'})
        self.assertEqual(self.runner.status()['status'], 'interrupted')

    def test_allowed_state_config_paths_and_scalar_whitelist(self):
        directory = self.directory / 'overrides'
        runner = bridge.CodexRunner(state_dir=directory, binary=str(self.fake),
                                   config_overrides={'sqlite_home': directory / 'db', 'log_dir': directory / 'logs'},
                                   scalar_overrides={'history.persistence': 'none', 'mcp_servers.codex_apps.enabled': False})
        command = runner._argv('read-only', None)
        self.assertIn('history.persistence="none"', command)
        self.assertIn('mcp_servers.codex_apps.enabled=false', command)
        with self.assertRaises(bridge.BridgeError):
            bridge.CodexRunner(state_dir=directory, scalar_overrides={'sandbox_mode': 'danger-full-access'})
        with self.assertRaises(bridge.BridgeError):
            bridge.CodexRunner(state_dir=directory, config_overrides={'log_dir': '/tmp/outside-known-state'})

    def test_repository_escape_and_unsupported_mode_rejected(self):
        with self.assertRaises(bridge.BridgeError):
            bridge.CodexRunner(repo_path='/tmp', state_dir=self.directory / 'invalid')
        self.assert_failure('Salom', 'invalid_mode', mode='danger-full-access')

    def test_check_makes_real_readonly_call_and_preserves_thread(self):
        result = self.runner.check()
        self.assertEqual(result.mode, 'read-only')
        self.assertEqual(result.session_id, SESSION_ID)
        self.assertEqual(self.runner.check().session_id, SESSION_ID)

    def test_progress_callback_failure_does_not_repeat_or_fail_work(self):
        def progress(_):
            raise RuntimeError('Telegram delivery failed')
        result = self.runner.run('Salom', on_progress=progress)
        self.assertEqual(result.session_id, SESSION_ID)


if __name__ == '__main__':
    unittest.main()
