#!/usr/bin/env python3
"""Private Telegram/Codex dialogue with a durable, serial job queue.

Incoming text is never evaluated as shell code. Ordinary messages use the
runner's read-only sandbox; only an explicit /task selects workspace-write.
Completed replies are persisted before Telegram delivery and retried without
repeating model work. A crashed running task is reported as interrupted.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import stat
import sys
import threading
import time
from typing import Any

if __package__:
    from .telegram_bot import (BotError, Config, DEFAULT_STATE_DIR, Store,
                               TelegramClient, TelegramError, Worker, status_message)
    from .codex_bridge import BridgeError, CodexRunner, PROJECT_ROOT
else:
    # Direct script execution and importlib-based tests use these local modules.
    module_directory = str(Path(__file__).resolve().parent)
    if module_directory not in sys.path:
        sys.path.insert(0, module_directory)
    from telegram_bot import (BotError, Config, DEFAULT_STATE_DIR, Store,
                              TelegramClient, TelegramError, Worker, status_message)
    from codex_bridge import BridgeError, CodexRunner, PROJECT_ROOT


MAX_PROMPT = 8000
MAX_PENDING = 20
CHUNK_UNITS = 3500
BOT_TOKEN = re.compile(r'\b[0-9]{5,}:[A-Za-z0-9_-]{20,}\b')
HELP_TEXT = (
    'UniFlow Codex yordamchisi\n\n'
    'Bu Telegram uchun alohida, saqlanadigan Codex suhbatidir. '
    'ChatGPTdagi avvalgi suhbat avtomatik ulanmaydi; loyiha konteksti va fayllaridan foydalaniladi.\n\n'
    'Oddiy xabar — suhbat va loyihani o‘qish; fayllar o‘zgartirilmaydi.\n'
    '/task TOPSHIRIQ — loyiha ichida kod yozish va sinash.\n'
    '/status — ishlayotgan topshiriq va navbat holati.\n'
    '/cancel — hozirgi Codex jarayonini bekor qilish.\n'
    '/new — navbat bo‘sh va jarayon tinch bo‘lganda yangi suhbat.\n'
    '/help — shu qo‘llanma.\n\n'
    'Topshiriqlar bittadan bajariladi. Qabul tasdig‘i ish tugaganini anglatmaydi. '
    'Git push faqat joriy /task matnida aniq so‘ralsa bajariladi. '
    'Token va parollarni xabarga yozmang.'
)


def sanitize(text: str, token: str = '') -> str:
    text = text.encode('utf-8', errors='replace').decode('utf-8')
    if token:
        text = text.replace(token, '[redacted]')
    text = BOT_TOKEN.sub('[redacted]', text)
    text = re.sub(r'(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+/-]+', r'\1[redacted]', text)
    return ''.join(char for char in text if char in '\n\t' or ord(char) >= 32)


def split_reply(text: str, max_units: int = CHUNK_UNITS) -> list[str]:
    """Split at Unicode scalar boundaries, counting Telegram's UTF-16 units."""
    if not 2 <= max_units <= 4096:
        raise ValueError('Invalid Telegram chunk size')
    result, current, units = [], [], 0
    for char in text:
        width = 2 if ord(char) > 0xFFFF else 1
        if units + width > max_units:
            result.append(''.join(current))
            current, units = [], 0
        current.append(char)
        units += width
    if current:
        result.append(''.join(current))
    return result or ['Codex matnli javob qaytarmadi.']


def safe_failure(failure: Exception) -> str:
    """Only known error codes become user diagnostics; never return stderr."""
    code = failure.code if isinstance(failure, BridgeError) else 'runtime_error'
    explanations = {
        'cancelled': 'Topshiriq bekor qilindi. Shu paytgacha qilingan fayl o‘zgarishlari avtomatik qaytarilmaydi.',
        'timeout': 'Codex vaqt chegarasiga yetdi. Ish qisman bajarilgan bo‘lishi mumkin; avtomatik qayta bajarilmadi.',
        'cli_missing': 'Codex dasturi topilmadi. Loyiha mas’uli xizmat sozlamasini tekshirishi kerak.',
        'cli_unavailable': 'Codex jarayonini boshlashga ruxsat yetishmayapti. Cloud sozlamasini tekshirish kerak.',
        'authentication': 'Codex autentifikatsiyasi ishlamadi. Cloud muhitidagi mavjud kirishni tekshirish kerak.',
        'runtime_permissions': 'Codex xizmat fayllariga yozish ruxsati yetishmayapti. Cloud sozlamasini tekshirish kerak.',
        'runtime_read_only': 'Codex xizmat fayllari joylashgan disk faqat o‘qish rejimida. Cloud runtime ruxsatlarini tekshirish kerak.',
        'session_not_found': 'Saqlangan Codex suhbati topilmadi. Navbat bo‘sh bo‘lganda /new yuboring; avtomatik yangi suhbat ochilmadi.',
        'state_corrupt': 'Codex sessiya holatini o‘qib bo‘lmadi. Loyiha mas’uli saqlangan holatni tekshirishi kerak.',
        'busy': 'Boshqa Codex jarayoni ishlayapti. Topshiriq avtomatik takrorlanmadi; /status orqali tekshiring.',
        'cli_failed': 'Codex javobni yakunlay olmadi. Model yoki tarmoq aloqasi ishlamagan bo‘lishi mumkin; xizmat diagnostikasini tekshirish kerak.',
        'network': 'Codex modeliga tarmoq orqali ulanib bo‘lmadi. Cloud tarmoq ruxsatlarini tekshirish kerak.',
        'proxy_blocked': 'Tarmoq proksisi Codex modeliga ulanishni rad etdi. Cloud tarmoq ruxsatlarini tekshirish kerak.',
        'network_policy': 'Cloud tarmoq siyosati Codex modeliga ulanishga ruxsat bermadi. Muhit sozlamalarini tekshirish kerak.',
        'network_access': 'Codex modeliga tarmoq orqali kirish rad etildi. Cloud tarmoq sozlamalarini tekshirish kerak.',
        'output_limit': 'Codex chiqishi hajm chegarasiga yetdi va jarayon to‘xtatildi.',
    }
    explanation = explanations.get(code, 'Codex topshirig‘i kutilmagan texnik xato bilan to‘xtadi. Xavfsiz diagnostikani loyiha mas’uli tekshirishi kerak.')
    return explanation + ('\n\nBu bajarilganlik tasdig‘i emas. /status bilan holatni tekshiring.' if code != 'cancelled' else '')


class DurableQueue:
    def __init__(self, directory: Path):
        self.path = directory / 'assistant.sqlite3'
        self._lock = threading.RLock()
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            with os.fdopen(descriptor, 'rb') as stream:
                metadata = os.fstat(stream.fileno())
                if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                        or stat.S_IMODE(metadata.st_mode) != 0o600):
                    raise BotError('Yordamchi bazasi joriy foydalanuvchiga tegishli va 0600 ruxsatli bo‘lishi kerak.')
            with self.connection() as connection:
                connection.executescript('''
                    CREATE TABLE IF NOT EXISTS accepted_updates (
                        update_id INTEGER PRIMARY KEY, created_at REAL NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS jobs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        update_id INTEGER UNIQUE NOT NULL,
                        mode TEXT NOT NULL CHECK(mode IN ('read-only','workspace-write')),
                        prompt TEXT NOT NULL,
                        state TEXT NOT NULL DEFAULT 'queued',
                        reply TEXT,
                        cancel_requested INTEGER NOT NULL DEFAULT 0,
                        created_at REAL NOT NULL, updated_at REAL NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS outbox (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_key TEXT NOT NULL UNIQUE,
                        job_id INTEGER,
                        text TEXT NOT NULL,
                        next_chunk INTEGER NOT NULL DEFAULT 0,
                        delivered INTEGER NOT NULL DEFAULT 0,
                        attempts INTEGER NOT NULL DEFAULT 0,
                        retry_at REAL NOT NULL DEFAULT 0
                    );
                ''')
                interrupted = connection.execute("SELECT id,update_id FROM jobs WHERE state='running'").fetchall()
                for row in interrupted:
                    reply = (f'Ish #{row["id"]} xizmat qayta ishga tushgani sabab uzilgan. '
                             'U avtomatik qayta bajarilmadi; qisman fayl o‘zgarishlari bo‘lishi mumkin. '
                             'Davom ettirishdan oldin /status va loyiha holatini tekshiring.')
                    connection.execute("UPDATE jobs SET state='interrupted',reply=?,updated_at=? WHERE id=?", (reply, time.time(), row['id']))
                    connection.execute('UPDATE outbox SET delivered=1 WHERE event_key=?', (f'ack:{row["update_id"]}',))
                    self._outbox(connection, f'result:{row["id"]}', reply, row['id'])
        except (OSError, sqlite3.Error):
            raise BotError('Yordamchi navbatini xavfsiz ochib bo‘lmadi. Saqlangan holatni tekshiring.') from None

    @contextmanager
    def connection(self):
        with self._lock:
            connection = sqlite3.connect(self.path, timeout=5)
            connection.row_factory = sqlite3.Row
            try:
                connection.execute('PRAGMA synchronous=FULL')
                connection.execute('BEGIN IMMEDIATE')
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    @staticmethod
    def _outbox(connection, key: str, text: str, job_id: int | None = None):
        connection.execute('INSERT OR IGNORE INTO outbox(event_key,job_id,text) VALUES(?,?,?)', (key, job_id, text))

    def has_update(self, update_id: int) -> bool:
        with self.connection() as connection:
            return connection.execute('SELECT 1 FROM accepted_updates WHERE update_id=?', (update_id,)).fetchone() is not None

    def accept_job(self, update_id: int, prompt: str, mode: str) -> int | None:
        with self.connection() as connection:
            if connection.execute('SELECT 1 FROM accepted_updates WHERE update_id=?', (update_id,)).fetchone():
                row = connection.execute('SELECT id FROM jobs WHERE update_id=?', (update_id,)).fetchone()
                return row['id'] if row else None
            pending = connection.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]
            if pending >= MAX_PENDING:
                self._outbox(connection, f'reject:{update_id}', 'Navbat to‘la (20 ta ish). Xabaringiz topshiriqqa olinmadi; keyinroq qayta yuboring.')
                job_id = None
            else:
                now = time.time()
                cursor = connection.execute('INSERT INTO jobs(update_id,mode,prompt,created_at,updated_at) VALUES(?,?,?,?,?)', (update_id, mode, prompt, now, now))
                job_id = cursor.lastrowid
                kind = 'Kod topshirig‘i' if mode == 'workspace-write' else 'Suhbat xabari'
                self._outbox(connection, f'ack:{update_id}', f'{kind} #{job_id} navbatga olindi. Bu qabul tasdig‘i; javob bajarilgach alohida yuboriladi.', job_id)
            connection.execute('INSERT INTO accepted_updates VALUES(?,?)', (update_id, time.time()))
            return job_id

    def accept_command(self, update_id: int, reply: str):
        with self.connection() as connection:
            if connection.execute('SELECT 1 FROM accepted_updates WHERE update_id=?', (update_id,)).fetchone():
                return
            self._outbox(connection, f'command:{update_id}', reply)
            connection.execute('INSERT INTO accepted_updates VALUES(?,?)', (update_id, time.time()))

    def claim(self) -> dict | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY id LIMIT 1").fetchone()
            if row is None:
                return None
            connection.execute("UPDATE jobs SET state='running',updated_at=? WHERE id=?", (time.time(), row['id']))
            return dict(row)

    def finish(self, job_id: int, state: str, reply: str):
        with self.connection() as connection:
            connection.execute('UPDATE jobs SET state=?,reply=?,updated_at=? WHERE id=?', (state, reply, time.time(), job_id))
            self._outbox(connection, f'result:{job_id}', reply, job_id)

    def cancel(self, job_id: int):
        with self.connection() as connection:
            connection.execute('UPDATE jobs SET cancel_requested=1 WHERE id=?', (job_id,))

    def add_progress(self, job_id: int, sequence: int, text: str):
        with self.connection() as connection:
            self._outbox(connection, f'progress:{job_id}:{sequence}', text, job_id)

    def pending_delivery(self) -> dict | None:
        with self.connection() as connection:
            row = connection.execute('SELECT * FROM outbox WHERE delivered=0 AND retry_at<=? ORDER BY id LIMIT 1', (time.time(),)).fetchone()
            return dict(row) if row else None

    def delivered(self, delivery_id: int, next_chunk: int, complete: bool):
        with self.connection() as connection:
            connection.execute('UPDATE outbox SET next_chunk=?,delivered=?,attempts=0,retry_at=0 WHERE id=?', (next_chunk, int(complete), delivery_id))

    def retry_delivery(self, delivery_id: int, delay: int):
        with self.connection() as connection:
            connection.execute('UPDATE outbox SET attempts=attempts+1,retry_at=? WHERE id=?', (time.time() + max(1, delay), delivery_id))

    def counts(self) -> dict[str, int]:
        with self.connection() as connection:
            counts = {row['state']: row['count'] for row in connection.execute('SELECT state,COUNT(*) AS count FROM jobs GROUP BY state')}
            counts['delivery_pending'] = connection.execute('SELECT COUNT(*) FROM outbox WHERE delivered=0').fetchone()[0]
            return counts

    def job(self, job_id: int) -> dict:
        with self.connection() as connection:
            return dict(connection.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())


class AssistantWorker(Worker):
    def __init__(self, config: Config, client: TelegramClient, store: Store, runner: CodexRunner,
                 queue: DurableQueue | None = None):
        super().__init__(config, client, store)
        self.runner = runner
        self.queue = queue or DurableQueue(config.state_dir)
        self._state_lock = threading.RLock()
        self._delivery_lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._cancel: threading.Event | None = None
        self._current: dict | None = None
        self._thread: threading.Thread | None = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._work_loop, name='telegram-codex', daemon=False)
        self._thread.start()

    def request_stop(self):
        self._stop.set()
        # A signal can interrupt the poll thread while it owns the queue lock.
        # Never wait for _state_lock here: the worker may own it while waiting
        # for that queue lock. Event references are published atomically; the
        # worker rechecks _stop after publishing a new cancellation event.
        cancellation = self._cancel
        if cancellation:
            cancellation.set()
        self._wake.set()

    def stop(self, timeout: float = 20) -> bool:
        self.request_stop()
        if self._thread:
            self._thread.join(timeout)
            return not self._thread.is_alive()
        return True

    def status_text(self) -> str:
        with self._state_lock:
            current = self._current
            counts = self.queue.counts()
            lines = ['UniFlow Codex yordamchisi',
                     f'Jarayon: {"ishlayapti" if current else "bo‘sh"}',
                     f'Navbat: {counts.get("queued", 0)} ta',
                     f'Yetkazish kutilayotgan xabarlar: {counts["delivery_pending"]} ta']
            if current:
                lines.append(f'Joriy ish: #{current["id"]} ({current["mode"]})')
            try:
                state = self.runner.status()
                known = {'idle', 'running', 'completed', 'cancelled', 'interrupted', 'authentication', 'runtime_permissions', 'runtime_read_only', 'cli_failed', 'cli_missing', 'cli_unavailable', 'timeout', 'session_not_found', 'proxy_blocked', 'network_policy', 'network_access'}
                label = state.get('status', 'idle')
                lines.append('Codex holati: ' + (label if label in known else 'texnik tekshiruv talab etiladi'))
            except Exception:
                lines.append('Codex holatini hozir o‘qib bo‘lmadi.')
        if self.config.status_file:
            lines.extend(['', status_message(self.config)])
        return sanitize('\n'.join(lines), self.config.token)

    def process(self, update: dict[str, Any]):
        update_id = update.get('update_id')
        if not isinstance(update_id, int) or isinstance(update_id, bool) or update_id < self.store.offset:
            return
        message = update.get('message')
        if not isinstance(message, dict):
            self.store.advance(update_id + 1)
            return
        chat, sender = message.get('chat', {}), message.get('from', {})
        if not isinstance(chat, dict) or not isinstance(sender, dict):
            self.store.advance(update_id + 1)
            return
        allowed = (chat.get('id') == self.config.chat_id and chat.get('type') == 'private'
                   and sender.get('id') == self.config.chat_id and not sender.get('is_bot', False))
        raw = message.get('text')
        if not allowed or not isinstance(raw, str) or not raw.strip():
            self.store.advance(update_id + 1)
            return
        if self.queue.has_update(update_id):
            self.store.advance(update_id + 1)
            return
        text = sanitize(raw.strip(), self.config.token)
        stored_text = text[:MAX_PROMPT] + ('\n[uzun xabar qisqartirildi]' if len(text) > MAX_PROMPT else '')
        self.store.record(update_id, dict(message, text=stored_text))
        command = text.split(maxsplit=1)[0].split('@')[0].lower()
        if len(raw) > MAX_PROMPT:
            self.queue.accept_command(update_id, 'Xabar 8000 belgidan oshmasin. Uni qisqartirib qayta yuboring; topshiriq navbatga olinmadi.')
        elif command in ['/help', '/start']:
            self.queue.accept_command(update_id, HELP_TEXT)
        elif command == '/status':
            self.queue.accept_command(update_id, self.status_text())
        elif command == '/cancel':
            with self._state_lock:
                if self._current and self._cancel:
                    self.queue.cancel(self._current['id'])
                    self._cancel.set()
                    reply = 'Joriy ishni bekor qilish so‘rovi yuborildi. Jarayon to‘xtashi kutilmoqda; qilingan o‘zgarishlar avtomatik qaytarilmaydi.'
                else:
                    reply = 'Hozir bekor qilinadigan Codex jarayoni yo‘q. Navbatdagi ishlar saqlanadi.'
                self.queue.accept_command(update_id, reply)
        elif command == '/new':
            with self._state_lock:
                counts = self.queue.counts()
                if self._current or counts.get('queued', 0) or counts.get('running', 0):
                    reply = 'Yangi suhbat uchun joriy ish tugashi va navbat bo‘shashini kuting. So‘ng /new yuboring.'
                else:
                    try:
                        self.runner.reset()
                        reply = 'Yangi Codex suhbati tayyorlandi. Keyingi xabar yangi sessiyada boshlanadi; eski loyiha fayllari saqlanadi.'
                    except Exception as failure:
                        reply = safe_failure(failure)
                self.queue.accept_command(update_id, reply)
        elif command.startswith('/') and command != '/task':
            self.queue.accept_command(update_id, 'Bu buyruq qo‘llab-quvvatlanmaydi. /help yuboring. Kod topshirig‘i uchun /task MATN ishlating.')
        else:
            prompt = text.split(maxsplit=1)[1].strip() if command == '/task' and len(text.split(maxsplit=1)) > 1 else ('' if command == '/task' else text)
            if not prompt:
                self.queue.accept_command(update_id, '/task dan keyin bajariladigan topshiriqni yozing.')
            else:
                self.queue.accept_job(update_id, prompt, 'workspace-write' if command == '/task' else 'read-only')
        # A durable job or durable command outcome exists before Telegram offset moves.
        self.store.advance(update_id + 1)
        self._wake.set()
        self.flush_outbox()

    def flush_outbox(self, max_chunks: int = 4):
        if not self._delivery_lock.acquire(blocking=False):
            return
        try:
            for _ in range(max_chunks):
                if self._stop.is_set():
                    return
                item = self.queue.pending_delivery()
                if item is None:
                    return
                chunks = split_reply(sanitize(item['text'], self.config.token))
                index = item['next_chunk']
                if index >= len(chunks):
                    self.queue.delivered(item['id'], index, True)
                    continue
                try:
                    self.client.send(chunks[index] if chunks[index].strip() else '…')
                except Exception as failure:
                    delay = failure.retry_after if isinstance(failure, TelegramError) and failure.retry_after else min(60, 2 ** min(item['attempts'] + 1, 6))
                    self.queue.retry_delivery(item['id'], delay)
                    return
                self.queue.delivered(item['id'], index + 1, index + 1 == len(chunks))
        finally:
            self._delivery_lock.release()

    def work_once(self) -> bool:
        with self._state_lock:
            if self._stop.is_set():
                return False
            job = self.queue.claim()
            if job is None:
                return False
            self._current = job
            self._cancel = threading.Event()
            cancellation = self._cancel
            if self._stop.is_set():
                cancellation.set()
        last_progress, sequence = 0.0, 0

        def progress(text: str):
            nonlocal last_progress, sequence
            now = time.monotonic()
            if sequence >= 6 or (sequence and now - last_progress < 30):
                return
            last_progress, sequence = now, sequence + 1
            self.queue.add_progress(job['id'], sequence, f'Ish #{job["id"]}: ' + sanitize(str(text), self.config.token)[:500])
            # Runner callbacks must not block on Telegram network requests.

        try:
            result = self.runner.run(job['prompt'], on_progress=progress, cancel_event=cancellation, mode=job['mode'])
            reply = sanitize(result.reply, self.config.token)
            if not reply.strip():
                raise BridgeError('empty_reply', 'Empty reply')
            self.queue.finish(job['id'], 'completed', f'Ish #{job["id"]}\n\n' + reply)
        except Exception as failure:
            state = 'cancelled' if isinstance(failure, BridgeError) and failure.code == 'cancelled' else 'failed'
            self.queue.finish(job['id'], state, f'Ish #{job["id"]}\n\n' + safe_failure(failure))
        finally:
            with self._state_lock:
                self._current = None
                self._cancel = None
        self.flush_outbox()
        return True

    def _work_loop(self):
        while not self._stop.is_set():
            try:
                if self.work_once():
                    continue
                self.flush_outbox()
                self._wake.wait(.5)
                self._wake.clear()
            except (sqlite3.Error, BotError, OSError):
                print('Yordamchi navbatini saqlashda xato. Qayta bajarishni oldini olish uchun worker to‘xtadi.', file=sys.stderr, flush=True)
                self._stop.set()

    def poll(self, stop: threading.Event):
        self.start()
        backoff = 2
        try:
            while not stop.is_set() and not self._stop.is_set():
                try:
                    self.flush_outbox()
                    updates = self.client.call('getUpdates', {'offset': self.store.offset, 'timeout': 25, 'allowed_updates': ['message']})
                    if not isinstance(updates, list):
                        raise BotError('Telegram javobidagi xabarlar ro‘yxati noto‘g‘ri.')
                    ordered = sorted((item for item in updates if isinstance(item, dict) and isinstance(item.get('update_id'), int) and not isinstance(item.get('update_id'), bool)), key=lambda item: item['update_id'])
                    for update in ordered:
                        if stop.is_set():
                            break
                        self.process(update)
                    backoff = 2
                except TelegramError as failure:
                    if failure.code in [401, 403, 409]:
                        raise
                    print('Telegram aloqasi uzildi; saqlangan navbat bilan qayta ulanish kutilmoqda.', file=sys.stderr, flush=True)
                    stop.wait(failure.retry_after if failure.code == 429 else backoff)
                    backoff = min(30, backoff * 2)
        finally:
            if not self.stop():
                raise BotError('Codex jarayoni hali to‘xtamadi. Poll lock saqlanmoqda; shutdown tugashi kutiladi.')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='UniFlow shaxsiy Telegram Codex yordamchisi.')
    parser.add_argument('--poll', action='store_true')
    parser.add_argument('--check-codex', action='store_true', help='Alohida Codex sessiyasida haqiqiy read-only ulanish sinovi.')
    parser.add_argument('--repo', type=Path, default=PROJECT_ROOT)
    parser.add_argument('--codex-binary', default='codex')
    parser.add_argument('--state-dir', type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument('--token-file', type=Path)
    parser.add_argument('--chat-id')
    parser.add_argument('--status-file', type=Path)
    args = parser.parse_args(argv)
    if not args.poll and not args.check_codex:
        parser.error('--poll yoki --check-codex kerak')
    store, worker = None, None
    try:
        state_dir = args.state_dir.absolute()
        runner_state = state_dir / 'codex'
        runner = CodexRunner(repo_path=args.repo, allowed_repo_path=args.repo,
                             state_dir=runner_state, binary=args.codex_binary,
                             config_overrides={'sqlite_home': runner_state / 'state', 'log_dir': runner_state / 'logs'},
                             scalar_overrides={'history.persistence': 'none'})
        if args.check_codex:
            runner.check()
            print('Codex read-only model sinovi muvaffaqiyatli. Bu alohida Telegram sessiyasi.', flush=True)
            if not args.poll:
                return 0
        config = Config.from_environment(token_file=args.token_file, state_dir=state_dir,
                                         status_file=args.status_file, chat_id=args.chat_id)
        client = TelegramClient(config)
        # This validates Telegram only; it does not claim model readiness.
        client.call('getMe')
        store = Store(config.state_dir)
        store.acquire()
        worker = AssistantWorker(config, client, store, runner)
        stop = threading.Event()

        def request_stop(*_):
            stop.set()
            # Do not wait for the outstanding getUpdates timeout to cancel Codex.
            worker.request_stop()

        signal.signal(signal.SIGINT, request_stop)
        signal.signal(signal.SIGTERM, request_stop)
        print('Telegram yordamchi polleri ishga tushdi. Model holati alohida tekshiriladi; faqat ruxsat etilgan shaxsiy chat qabul qilinadi.', flush=True)
        worker.poll(stop)
        return 0
    except BridgeError as failure:
        print(safe_failure(failure), file=sys.stderr)
        return 1
    except BotError as failure:
        # BotError messages originate in the fixed, token-safe Telegram client.
        print(sanitize(str(failure), ''), file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print('Yordamchi xizmatini ishga tushirib bo‘lmadi. Xususiy holat papkasi va runtime ruxsatlarini tekshiring.', file=sys.stderr)
        return 1
    except (KeyboardInterrupt, BrokenPipeError):
        return 0
    finally:
        stopped = worker.stop() if worker else True
        if store and stopped:
            store.close()
        elif store:
            # The non-daemon thread retains worker.store and its poll lock until
            # native cleanup finishes; never announce a clean shutdown early.
            print('Codex cleanup tugamadi; xizmat lockni ushlab, worker tugashini kutmoqda.', file=sys.stderr, flush=True)


if __name__ == '__main__':
    sys.exit(main())
