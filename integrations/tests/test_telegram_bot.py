import importlib.util
import io
import json
import os
from pathlib import Path
import ssl
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

MODULE_PATH = Path(__file__).resolve().parents[1] / 'telegram_bot.py'
SPEC = importlib.util.spec_from_file_location('telegram_bot', MODULE_PATH)
bot = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bot
SPEC.loader.exec_module(bot)
FAKE_TOKEN = '12345:' + 'unit_test_not_a_real_token_12345'
CHAT_ID = 123456789


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class FakeClient:
    def __init__(self):
        self.messages = []
        self.failure = None

    def send(self, text):
        if self.failure:
            raise self.failure
        self.messages.append(text)


class BotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name) / 'telegram'
        self.config = bot.Config(FAKE_TOKEN, CHAT_ID, self.directory)
        self.store = bot.Store(self.directory)
        self.store.acquire()
        self.client = FakeClient()
        self.worker = bot.Worker(self.config, self.client, self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def update(self, update_id=1, text='Salom', chat_id=CHAT_ID, sender_id=CHAT_ID, chat_type='private'):
        return {'update_id': update_id, 'message': {'message_id': update_id + 10, 'date': 123,
                 'chat': {'id': chat_id, 'type': chat_type}, 'from': {'id': sender_id, 'is_bot': False}, 'text': text}}

    def test_configuration_primary_binding_and_no_token_in_repr(self):
        with patch.dict(os.environ, {'tg_key': FAKE_TOKEN, 'UNIFLOW_TELEGRAM_TOKEN': 'wrong', 'UNIFLOW_TELEGRAM_CHAT_ID': str(CHAT_ID)}, clear=True):
            config = bot.Config.from_environment()
        self.assertEqual(config.token, FAKE_TOKEN)
        self.assertNotIn(FAKE_TOKEN, repr(config))

    def test_missing_token_and_invalid_chat_redacted(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, 'exists', return_value=False):
            with self.assertRaisesRegex(bot.BotError, 'token topilmadi'):
                bot.Config.from_environment()

    def test_chat_id_argument_without_chat_environment(self):
        with patch.dict(os.environ, {'tg_key': FAKE_TOKEN}, clear=True):
            self.assertEqual(bot.Config.from_environment(chat_id=CHAT_ID).chat_id, CHAT_ID)
        with patch.dict(os.environ, {'tg_key': FAKE_TOKEN, 'UNIFLOW_TELEGRAM_CHAT_ID': '-12'}, clear=True):
            with self.assertRaisesRegex(bot.BotError, 'musbat'):
                bot.Config.from_environment()

    def test_token_file_permissions_and_symlink(self):
        token_path = Path(self.tmp.name) / 'token'
        token_path.write_text(FAKE_TOKEN)
        token_path.chmod(0o644)
        with self.assertRaisesRegex(bot.BotError, '0600'):
            bot.read_token_file(token_path)
        token_path.chmod(0o600)
        self.assertEqual(bot.read_token_file(token_path), FAKE_TOKEN)
        linked = token_path.with_name('link')
        linked.symlink_to(token_path)
        with self.assertRaises(bot.BotError):
            bot.read_token_file(linked)

    def test_private_authorized_message_is_durable(self):
        self.worker.process(self.update(text='Yangi talab: hisobotlar'))
        record = json.loads(self.store.inbox_file.read_text())
        self.assertEqual(record['text'], 'Yangi talab: hisobotlar')
        self.assertEqual(record['sender_id'], CHAT_ID)
        self.assertEqual(self.store.offset, 2)
        self.assertEqual(self.store.inbox_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.store.state_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)
        self.assertIn('avtomatik', self.client.messages[0])

    def test_other_chat_sender_group_and_bot_ignored(self):
        updates = [self.update(1, chat_id=999), self.update(2, sender_id=999), self.update(3, chat_type='group')]
        fourth = self.update(4)
        fourth['message']['from']['is_bot'] = True
        for update in [*updates, fourth]:
            self.worker.process(update)
        self.assertEqual(self.store.offset, 5)
        self.assertFalse(self.store.inbox_file.exists())
        self.assertEqual(self.client.messages, [])

    def test_commands_fixed_and_text_never_executed(self):
        self.worker.process(self.update(1, '/start'))
        self.worker.process(self.update(2, '/help@uniflow'))
        self.worker.process(self.update(3, '/status'))
        self.worker.process(self.update(4, '/run rm -rf example'))
        self.assertEqual(self.client.messages[0], bot.HELP_TEXT)
        self.assertEqual(self.client.messages[1], bot.HELP_TEXT)
        self.assertIn('holati fayli', self.client.messages[2])
        self.assertEqual(json.loads(self.store.inbox_file.read_text())['text'], '/run rm -rf example')

    def test_send_failure_preserves_offset_without_duplicate_inbox_on_retry(self):
        self.client.failure = bot.TelegramError(429, 'rate limit', retry_after=1)
        with self.assertRaises(bot.TelegramError):
            self.worker.process(self.update())
        self.assertEqual(self.store.offset, 0)
        self.store.close()
        self.store = bot.Store(self.directory)
        self.store.acquire()
        self.client.failure = None
        self.worker = bot.Worker(self.config, self.client, self.store)
        self.worker.process(self.update())
        self.assertEqual(len(self.store.inbox_file.read_text().splitlines()), 1)
        self.assertEqual(self.store.offset, 2)
        self.worker.process(self.update())
        self.assertEqual(len(self.client.messages), 1)

    def test_single_poller_lock(self):
        second = bot.Store(self.directory)
        with self.assertRaisesRegex(bot.BotError, 'allaqachon'):
            second.acquire()

    def test_api_post_inherits_urlopen_and_does_not_disable_tls(self):
        calls = []
        def opener(req, timeout):
            calls.append((req, timeout))
            return Response(json.dumps({'ok': True, 'result': {'message_id': 1}}).encode())
        client = bot.TelegramClient(self.config, opener=opener)
        client.send('Salom')
        req, timeout = calls[0]
        self.assertEqual(req.get_method(), 'POST')
        self.assertTrue(req.full_url.startswith('https://api.telegram.org/bot'))
        self.assertEqual(timeout, 15)
        self.assertEqual(json.loads(req.data)['chat_id'], CHAT_ID)
        self.assertNotIn('parse_mode', json.loads(req.data))

    def test_network_errors_cannot_leak_token(self):
        def opener(req, timeout):
            raise URLError(f'failed: https://api.telegram.org/bot{FAKE_TOKEN}/getMe')
        client = bot.TelegramClient(self.config, opener=opener)
        with self.assertRaises(bot.TelegramError) as error:
            client.call('getMe')
        self.assertNotIn(FAKE_TOKEN, str(error.exception))

    def test_api_http_errors_and_retry_after_are_safe(self):
        for code, body in [(403, b'blocked'), (401, b'{}'), (409, b'{}'), (429, b'{"ok":false,"parameters":{"retry_after":7}}')]:
            def opener(req, timeout, code=code, body=body):
                raise HTTPError(req.full_url, code, f'contains {FAKE_TOKEN}', {}, io.BytesIO(body))
            with self.assertRaises(bot.TelegramError) as error:
                bot.TelegramClient(self.config, opener=opener).call('getMe')
            self.assertEqual(error.exception.code, code)
            self.assertNotIn(FAKE_TOKEN, str(error.exception))
            if code == 429:
                self.assertEqual(error.exception.retry_after, 7)

    def test_status_allowlist_and_token_redaction(self):
        path = Path(self.tmp.name) / 'status.json'
        path.write_text(json.dumps({'summary': 'Ready', 'stage': FAKE_TOKEN, 'password': 'hidden', 'updated_at': 'today'}))
        status = bot.status_message(bot.Config(FAKE_TOKEN, CHAT_ID, self.directory, path))
        self.assertIn('Ready', status)
        self.assertNotIn(FAKE_TOKEN, status)
        self.assertNotIn('hidden', status)
        self.worker.process(self.update(1, f'new token {FAKE_TOKEN}'))
        self.assertNotIn(FAKE_TOKEN, self.store.inbox_file.read_text())

    def test_polling_conflict_terminates(self):
        class ConflictClient(FakeClient):
            def call(self, *args):
                raise bot.TelegramError(409, 'conflict')
        with self.assertRaises(bot.TelegramError):
            bot.Worker(self.config, ConflictClient(), self.store).poll(threading.Event())


if __name__ == '__main__':
    unittest.main()
