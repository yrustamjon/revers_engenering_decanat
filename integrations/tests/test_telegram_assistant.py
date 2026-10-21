import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / 'telegram_assistant.py'
SPEC = importlib.util.spec_from_file_location('telegram_assistant', MODULE_PATH)
assistant = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = assistant
SPEC.loader.exec_module(assistant)
FAKE_TOKEN = '12345:unit_test_not_a_real_token_12345'
CHAT_ID = 123456789


class FakeClient:
    def __init__(self):
        self.messages = []
        self.fail = False
        self.lock = threading.Lock()

    def send(self, text):
        with self.lock:
            if self.fail:
                raise assistant.TelegramError(429, 'Safe network diagnostic', 1)
            self.messages.append(text)


class FakeRunner:
    def __init__(self, *, block=False, failure=None, reply='Loyiha bo‘yicha javob.'):
        self.calls = []
        self.failure = failure
        self.reply = reply
        self.block = block
        self.started = threading.Event()
        self.release = threading.Event()
        self.cancelled = threading.Event()
        self.finished = threading.Event()
        self.resets = 0
        self.checks = 0

    def run(self, prompt, on_progress=None, cancel_event=None, *, mode=None):
        self.calls.append((prompt, mode))
        self.started.set()
        if self.block:
            deadline = time.monotonic() + 3
            while not self.release.wait(.01):
                if cancel_event.is_set():
                    self.cancelled.set()
                    self.finished.set()
                    raise assistant.BridgeError('cancelled', 'Safe cancellation')
                if time.monotonic() >= deadline:
                    self.finished.set()
                    raise TimeoutError('Fake runner wait exceeded')
        self.finished.set()
        if self.failure:
            raise self.failure
        return SimpleNamespace(reply=self.reply, session_id='persistent-test-session', mode=mode)

    def status(self):
        return {'status': 'running' if self.started.is_set() and not self.finished.is_set() else 'idle', 'session_id': 'persistent-test-session'}

    def reset(self):
        self.resets += 1

    def check(self):
        self.checks += 1
        if self.failure:
            raise self.failure
        return SimpleNamespace(reply='Ready')


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name) / 'telegram'
        self.config = assistant.Config(FAKE_TOKEN, CHAT_ID, self.directory)
        self.store = assistant.Store(self.directory)
        self.store.acquire()
        self.client = FakeClient()
        self.runner = FakeRunner()
        self.worker = assistant.AssistantWorker(self.config, self.client, self.store, self.runner)

    def tearDown(self):
        self.worker.stop()
        self.store.close()
        self.tmp.cleanup()

    @staticmethod
    def update(update_id=1, text='Salom', *, chat_id=CHAT_ID, sender_id=CHAT_ID, chat_type='private', is_bot=False):
        return {'update_id': update_id, 'message': {'message_id': update_id + 100, 'date': 123,
                'chat': {'id': chat_id, 'type': chat_type}, 'from': {'id': sender_id, 'is_bot': is_bot}, 'text': text}}

    def wait_state(self, job_id, state, timeout=2):
        deadline = time.monotonic() + timeout
        waiter = threading.Event()
        while time.monotonic() < deadline:
            if self.worker.queue.job(job_id)['state'] == state:
                return
            waiter.wait(.01)
        self.fail(f'Job {job_id} did not reach {state}')

    def make_retries_due(self):
        with self.worker.queue.connection() as connection:
            connection.execute('UPDATE outbox SET retry_at=0')

    def test_private_sender_allowlist_rejects_groups_bots_and_others(self):
        for update in [self.update(1, chat_id=7), self.update(2, sender_id=7), self.update(3, chat_type='group'), self.update(4, is_bot=True)]:
            self.worker.process(update)
        self.assertEqual(self.store.offset, 5)
        self.assertEqual(self.worker.queue.counts().get('queued', 0), 0)
        self.assertEqual(self.client.messages, [])
        self.assertFalse(self.store.inbox_file.exists())

    def test_chat_is_read_only_and_explicit_task_is_workspace_write(self):
        self.worker.process(self.update(1, 'Hisobot jarayonini tushuntir'))
        self.worker.process(self.update(2, '/task Hisobot formasini tuzat'))
        self.assertEqual(self.runner.calls, [])
        self.assertIn('navbatga olindi', self.client.messages[0])
        self.worker.work_once()
        self.worker.work_once()
        self.assertEqual(self.runner.calls, [('Hisobot jarayonini tushuntir', 'read-only'), ('Hisobot formasini tuzat', 'workspace-write')])
        self.assertEqual(self.worker.queue.counts()['completed'], 2)
        self.assertEqual(self.store.offset, 3)

    def test_durable_queue_private_files_and_duplicate_update(self):
        update = self.update(1, '/task Biror ish')
        self.worker.process(update)
        self.worker.process(update)
        self.assertEqual(self.worker.queue.counts()['queued'], 1)
        self.assertEqual(self.worker.queue.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.store.inbox_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(self.store.inbox_file.read_text().splitlines()), 1)
        self.worker.work_once()
        self.assertEqual(len(self.runner.calls), 1)

    def test_offset_not_advanced_when_durable_enqueue_fails(self):
        update = self.update()
        with patch.object(self.worker.queue, 'accept_job', side_effect=sqlite3.OperationalError('Disk unavailable')):
            with self.assertRaises(sqlite3.Error):
                self.worker.process(update)
        self.assertEqual(self.store.offset, 0)
        self.worker.process(update)
        self.assertEqual(self.worker.queue.counts()['queued'], 1)
        self.assertEqual(len(self.store.inbox_file.read_text().splitlines()), 1)

    def test_enqueue_before_offset_failure_does_not_duplicate_on_retry(self):
        update = self.update()
        with patch.object(self.store, 'advance', side_effect=assistant.BotError('Disk unavailable')):
            with self.assertRaises(assistant.BotError):
                self.worker.process(update)
        self.assertEqual(self.worker.queue.counts()['queued'], 1)
        self.worker.process(update)
        self.assertEqual(self.store.offset, 2)
        self.assertEqual(self.worker.queue.counts()['queued'], 1)

    def test_delivery_failure_retries_persisted_reply_without_rerunning_model(self):
        self.client.fail = True
        self.worker.process(self.update())
        self.assertEqual(self.store.offset, 2)
        self.worker.work_once()
        self.assertEqual(len(self.runner.calls), 1)
        self.assertEqual(self.worker.queue.counts()['completed'], 1)
        self.worker.queue = assistant.DurableQueue(self.directory)
        self.client.fail = False
        self.make_retries_due()
        self.worker.flush_outbox(50)
        self.assertTrue(any('Loyiha bo‘yicha javob.' in text for text in self.client.messages))
        self.assertEqual(self.worker.queue.counts()['delivery_pending'], 0)
        self.assertFalse(self.worker.work_once())
        self.assertEqual(len(self.runner.calls), 1)

    def test_restart_running_task_is_interrupted_and_never_reexecuted(self):
        self.worker.process(self.update(1, '/task Side effect task'))
        job = self.worker.queue.claim()
        self.assertIsNotNone(job)
        self.worker.queue = assistant.DurableQueue(self.directory)
        self.assertEqual(self.worker.queue.job(job['id'])['state'], 'interrupted')
        self.assertFalse(self.worker.work_once())
        self.worker.flush_outbox()
        self.assertEqual(self.runner.calls, [])
        self.assertTrue(any('avtomatik qayta bajarilmadi' in message for message in self.client.messages))

    def test_pending_queue_survives_restart_and_runs_once(self):
        self.worker.process(self.update())
        self.worker.queue = assistant.DurableQueue(self.directory)
        self.assertTrue(self.worker.work_once())
        self.assertFalse(self.worker.work_once())
        self.assertEqual(len(self.runner.calls), 1)

    def test_running_worker_status_cancel_and_new_are_responsive(self):
        self.runner.block = True
        self.worker.start()
        self.worker.process(self.update(1, '/task Uzoq topshiriq'))
        self.assertTrue(self.runner.started.wait(1))
        started = time.monotonic()
        self.worker.process(self.update(2, '/status'))
        self.assertLess(time.monotonic() - started, .5)
        self.assertTrue(any('Jarayon: ishlayapti' in text for text in self.client.messages))
        self.worker.process(self.update(3, '/new'))
        self.assertEqual(self.runner.resets, 0)
        self.worker.process(self.update(4, '/cancel'))
        self.assertTrue(self.runner.cancelled.wait(1))
        self.wait_state(1, 'cancelled')
        self.assertEqual(self.worker.queue.job(1)['cancel_requested'], 1)

    def test_cancel_persistence_failure_does_not_signal_or_partially_commit(self):
        self.worker.process(self.update(1, '/task First task'))
        first = self.worker.queue.claim()
        self.worker._current = first
        self.worker._cancel = threading.Event()
        cancellation = self.worker._cancel
        update = self.update(2, '/cancel')
        with patch.object(self.worker.queue, '_outbox', side_effect=sqlite3.OperationalError('Disk unavailable')):
            with self.assertRaises(sqlite3.Error):
                self.worker.process(update)
        self.assertFalse(cancellation.is_set())
        self.assertEqual(self.worker.queue.job(first['id'])['cancel_requested'], 0)
        self.assertFalse(self.worker.queue.has_update(2))
        self.assertEqual(self.store.offset, 2)
        self.worker.process(update)
        self.assertTrue(cancellation.is_set())
        self.assertEqual(self.worker.queue.job(first['id'])['cancel_requested'], 1)
        self.assertTrue(self.worker.queue.has_update(2))

    def test_cancel_committed_before_signal_failure_does_not_cancel_next_job_on_replay(self):
        self.worker.process(self.update(1, '/task First task'))
        self.worker.process(self.update(2, '/task Next task'))
        first = self.worker.queue.claim()
        self.worker._current = first
        self.worker._cancel = threading.Event()
        update = self.update(3, '/cancel')
        # Model a crash after the durable outcome but before the native process
        # receives its cancellation event and before the Telegram offset moves.
        with patch.object(self.worker._cancel, 'set', side_effect=RuntimeError('Simulated crash')):
            with self.assertRaises(RuntimeError):
                self.worker.process(update)
        self.assertTrue(self.worker.queue.has_update(3))
        self.assertEqual(self.worker.queue.job(first['id'])['cancel_requested'], 1)
        self.assertEqual(self.store.offset, 3)

        self.worker.queue = assistant.DurableQueue(self.directory)
        self.assertEqual(self.worker.queue.job(first['id'])['state'], 'interrupted')
        second = self.worker.queue.claim()
        self.worker._current = second
        self.worker._cancel = threading.Event()
        self.worker.process(update)
        self.assertFalse(self.worker._cancel.is_set())
        self.assertEqual(self.worker.queue.job(second['id'])['cancel_requested'], 0)
        self.assertEqual(self.store.offset, 4)
        with self.worker.queue.connection() as connection:
            outcomes = connection.execute('SELECT job_id FROM outbox WHERE event_key=?', ('command:3',)).fetchall()
        self.assertEqual([row['job_id'] for row in outcomes], [first['id']])

    def test_new_refuses_queued_work_and_resets_only_idle_once(self):
        self.worker.process(self.update(1, 'Salom'))
        self.worker.process(self.update(2, '/new'))
        self.assertEqual(self.runner.resets, 0)
        self.worker.work_once()
        self.worker.process(self.update(3, '/new'))
        self.worker.process(self.update(3, '/new'))
        self.assertEqual(self.runner.resets, 1)

    def test_poll_continues_serving_commands_while_model_runs(self):
        stop = threading.Event()
        test = self
        self.runner.block = True

        class PollClient(FakeClient):
            poll_count = 0
            def call(inner_self, method, payload):
                test.assertEqual(method, 'getUpdates')
                inner_self.poll_count += 1
                if inner_self.poll_count == 1:
                    return [test.update(1, '/task Uzoq ish')]
                if inner_self.poll_count == 2:
                    test.assertTrue(test.runner.started.wait(1))
                    return [test.update(2, '/status')]
                stop.set()
                return []

        client = PollClient()
        self.worker.client = client
        self.worker.poll(stop)
        self.assertTrue(any('Jarayon: ishlayapti' in text for text in client.messages))
        self.assertTrue(self.runner.cancelled.wait(1))

    def test_failed_job_does_not_crash_next_job_or_leak_stderr(self):
        self.runner.failure = RuntimeError('stderr contains ' + FAKE_TOKEN)
        self.worker.process(self.update(1, '/task Failure'))
        self.worker.work_once()
        self.assertEqual(self.worker.queue.job(1)['state'], 'failed')
        self.assertNotIn(FAKE_TOKEN, '\n'.join(self.client.messages))
        self.assertNotIn('stderr contains', self.worker.queue.job(1)['reply'])
        self.runner.failure = None
        self.worker.process(self.update(2, 'Recovery'))
        self.worker.work_once()
        self.assertEqual(self.worker.queue.job(2)['state'], 'completed')
        self.assertEqual(len(self.runner.calls), 2)

    def test_model_network_denial_is_clear_and_safe(self):
        self.runner.failure = assistant.BridgeError('proxy_blocked', 'raw secret ' + FAKE_TOKEN)
        self.worker.process(self.update())
        self.worker.work_once()
        reply = self.worker.queue.job(1)['reply']
        self.assertIn('proksisi', reply)
        self.assertIn('bajarilganlik tasdig‘i emas', reply)
        self.assertNotIn(FAKE_TOKEN, reply)

    def test_prompt_limit_queue_bound_and_unknown_commands(self):
        self.worker.process(self.update(1, 'a' * 8001))
        self.assertEqual(self.worker.queue.counts().get('queued', 0), 0)
        self.worker.process(self.update(2, '/run echo unsafe'))
        self.worker.process(self.update(3, '/task'))
        self.assertEqual(self.worker.queue.counts().get('queued', 0), 0)
        for update_id in range(4, 25):
            self.worker.process(self.update(update_id, 'Queued'))
        self.assertEqual(self.worker.queue.counts()['queued'], 20)
        self.assertTrue(any('Navbat to‘la' in text for text in self.client.messages))

    def test_unicode_utf16_chunks_fit_telegram_and_preserve_content(self):
        text = '🙂' * 5000 + ' O‘zbekiston — 𐐷' * 200
        chunks = assistant.split_reply(text)
        self.assertEqual(''.join(chunks), text)
        self.assertTrue(all(len(chunk.encode('utf-16-le')) // 2 <= 3500 for chunk in chunks))
        self.runner.reply = text
        self.worker.process(self.update())
        self.worker.work_once()
        self.worker.flush_outbox(30)
        self.assertTrue(all(len(chunk.encode('utf-16-le')) // 2 <= 3500 for chunk in self.client.messages))

    def test_sanitizes_inbox_and_queue_and_never_executes_shell_text(self):
        marker = Path(self.tmp.name) / 'should-not-exist'
        prompt = f'/task $(touch {marker}) token={FAKE_TOKEN} Authorization: Bearer secret-value'
        self.worker.process(self.update(1, prompt))
        stored = self.store.inbox_file.read_text()
        self.assertNotIn(FAKE_TOKEN, stored)
        self.assertNotIn('secret-value', stored)
        self.worker.work_once()
        self.assertFalse(marker.exists())
        self.assertIn('$(touch', self.runner.calls[0][0])
        self.assertNotIn(FAKE_TOKEN, self.runner.calls[0][0])

    def test_queue_rejects_symlink_and_insecure_database_permissions(self):
        separate = self.directory / 'other'
        separate.mkdir()
        actual = separate / 'target'
        actual.touch(mode=0o600)
        (separate / 'assistant.sqlite3').symlink_to(actual)
        with self.assertRaises(assistant.BotError):
            assistant.DurableQueue(separate)
        (separate / 'assistant.sqlite3').unlink()
        (separate / 'assistant.sqlite3').touch(mode=0o644)
        (separate / 'assistant.sqlite3').chmod(0o644)
        with self.assertRaises(assistant.BotError):
            assistant.DurableQueue(separate)

    def test_check_codex_calls_native_doctor_without_telegram_credentials(self):
        with patch.object(assistant, 'CodexRunner', return_value=self.runner) as constructor, patch('sys.stdout', new_callable=io.StringIO):
            code = assistant.main(['--check-codex', '--state-dir', str(self.directory)])
        self.assertEqual(code, 0)
        self.assertEqual(self.runner.checks, 1)
        self.assertEqual(constructor.call_args.kwargs['scalar_overrides'], {'history.persistence': 'none'})
        self.assertEqual(constructor.call_args.kwargs['config_overrides']['sqlite_home'], self.directory / 'codex' / 'state')

    def test_progress_enqueues_without_blocking_runner_on_telegram(self):
        test = self

        class ProgressRunner(FakeRunner):
            def run(inner_self, prompt, on_progress=None, cancel_event=None, *, mode=None):
                count = len(test.client.messages)
                on_progress('Fayllar tekshirilmoqda')
                test.assertEqual(len(test.client.messages), count)
                return SimpleNamespace(reply='Completed')

        self.worker.runner = ProgressRunner()
        self.worker.process(self.update())
        self.worker.work_once()
        self.assertTrue(any('Fayllar tekshirilmoqda' in message for message in self.client.messages))

    def test_request_stop_cancels_native_runner_before_poll_returns(self):
        self.runner.block = True
        self.worker.start()
        self.worker.process(self.update(1, '/task Uzoq ish'))
        self.assertTrue(self.runner.started.wait(1))
        self.worker.request_stop()
        self.assertTrue(self.runner.cancelled.wait(1))
        self.assertTrue(self.worker.stop())
        self.assertFalse(self.worker._thread.is_alive())

    def test_signal_stop_does_not_wait_for_state_lock_while_queue_is_held(self):
        self.runner.block = True
        self.worker.process(self.update(1, '/task Signal race'))
        entered_claim, stopped = threading.Event(), threading.Event()
        original_claim = self.worker.queue.claim

        def observed_claim():
            entered_claim.set()
            return original_claim()

        def request_stop():
            self.worker.request_stop()
            stopped.set()

        with patch.object(self.worker.queue, 'claim', side_effect=observed_claim):
            with self.worker.queue._lock:
                self.worker.start()
                self.assertTrue(entered_claim.wait(1))
                stopper = threading.Thread(target=request_stop)
                stopper.start()
                # The worker holds _state_lock and waits for this queue lock.
                # The signal path must return before this context releases it.
                returned_without_lock = stopped.wait(.25)
            stopper.join(1)
            self.assertTrue(returned_without_lock)
            self.assertTrue(self.worker.stop())

    def test_stop_between_claim_and_cancel_event_publication_is_not_lost(self):
        test = self

        class CancellationRunner(FakeRunner):
            def run(inner_self, prompt, on_progress=None, cancel_event=None, *, mode=None):
                test.assertTrue(cancel_event.is_set())
                raise assistant.BridgeError('cancelled', 'Cancelled before execution')

        self.worker.runner = CancellationRunner()
        self.worker.process(self.update(1, '/task Assignment race'))
        original_claim = self.worker.queue.claim

        def stop_during_claim():
            job = original_claim()
            self.worker.request_stop()
            return job

        with patch.object(self.worker.queue, 'claim', side_effect=stop_during_claim):
            self.assertTrue(self.worker.work_once())
        self.assertEqual(self.worker.queue.job(1)['state'], 'cancelled')


if __name__ == '__main__':
    unittest.main()
