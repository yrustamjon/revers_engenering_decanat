#!/usr/bin/env python3
"""Optional private Telegram status/inbox worker; never executes incoming text."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import ssl
import stat
import sys
import tempfile
import threading
from dataclasses import dataclass
from typing import Any
from urllib import error, request


DEFAULT_STATE_DIR = Path(__file__).resolve().parents[1] / '.local' / 'telegram'
TOKEN_PATTERN = re.compile(r'^[0-9]+:[A-Za-z0-9_-]{20,}$')
HELP_TEXT = (
    'UniFlow loyiha boti\n\n'
    '/status — loyiha holati\n'
    '/help — foydalanish qo‘llanmasi\n\n'
    'Oddiy xabar yuborsangiz, u loyiha xabarlar qutisiga saqlanadi. '
    'Bu bot xabarlarni dastur yoki buyruq sifatida bajarmaydi. '
    'Xabar saqlanishi dasturchi uni hozir o‘qiganini anglatmaydi.'
)


class BotError(Exception):
    """Only safe, token-free diagnostics may be included in this exception."""


class TelegramError(BotError):
    def __init__(self, code: int, message: str, retry_after: int = 0):
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after


def read_token_file(path: Path) -> str:
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'r', encoding='utf-8') as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise BotError('Token fayli joriy foydalanuvchiga tegishli oddiy fayl bo‘lishi kerak.')
            if stat.S_IMODE(metadata.st_mode) != 0o600:
                raise BotError('Token fayli ruxsati 0600 bo‘lishi kerak: chmod 600 <token-fayl>.')
            token = stream.read(512).strip()
    except (OSError, UnicodeError):
        raise BotError('Token faylini xavfsiz o‘qib bo‘lmadi.') from None
    return token


@dataclass(frozen=True, repr=False)
class Config:
    token: str
    chat_id: int
    state_dir: Path = DEFAULT_STATE_DIR
    status_file: Path | None = None

    def __repr__(self) -> str:
        return f'Config(token=[redacted], chat_id={self.chat_id})'

    @classmethod
    def from_environment(cls, *, token_file: Path | None = None, state_dir: Path = DEFAULT_STATE_DIR,
                         status_file: Path | None = None, chat_id: str | int | None = None) -> 'Config':
        token = ''
        if token_file:
            token = read_token_file(token_file)
        else:
            token = os.environ.get('tg_key') or os.environ.get('UNIFLOW_TELEGRAM_TOKEN', '')
            default_token = DEFAULT_STATE_DIR / 'token'
            if not token and default_token.exists():
                token = read_token_file(default_token)
        if not token:
            raise BotError('Telegram token topilmadi. tg_key yoki UNIFLOW_TELEGRAM_TOKEN secretini sozlang.')
        if not TOKEN_PATTERN.fullmatch(token):
            raise BotError('Telegram token formati noto‘g‘ri; qiymatni xavfsiz sozlamalarda tekshiring.')
        chat = str(chat_id) if chat_id is not None else os.environ.get('UNIFLOW_TELEGRAM_CHAT_ID', '')
        if not re.fullmatch(r'[1-9][0-9]{0,19}', chat):
            raise BotError('UNIFLOW_TELEGRAM_CHAT_ID musbat shaxsiy Telegram ID bo‘lishi kerak.')
        return cls(token=token, chat_id=int(chat), state_dir=state_dir, status_file=status_file)


class TelegramClient:
    METHODS = {'getMe', 'sendMessage', 'getUpdates'}

    def __init__(self, config: Config, opener=None):
        self.config = config
        # urlopen preserves inherited HTTPS_PROXY and the system CA trust.
        self.opener = opener or request.urlopen

    @staticmethod
    def api_error(code: int, payload: dict[str, Any] | None = None) -> TelegramError:
        payload = payload or {}
        if code == 429:
            parameters = payload.get('parameters', {})
            value = parameters.get('retry_after', 5) if isinstance(parameters, dict) else 5
            retry = max(1, min(300, value)) if isinstance(value, int) else 5
            return TelegramError(code, 'Telegram so‘rovlar chegarasiga yetildi; keyinroq qayta uriniladi.', retry)
        if code == 409:
            return TelegramError(code, 'Boshqa polling jarayoni yoki webhook faol. Bitta qabul qiluvchini qoldiring.')
        if code == 401:
            return TelegramError(code, 'Telegram autentifikatsiyasi rad etildi. Token sozlamasini yangilang.')
        if code == 403:
            message = ('Telegram bu amalni rad etdi. Botni ochib /start yuboring va chat ruxsatini tekshiring.'
                       if payload.get('ok') is False else
                       'Tarmoq proksisi Telegram manziliga kirishni rad etdi (HTTP 403).')
            return TelegramError(code, message)
        return TelegramError(code, f'Telegram so‘rovi bajarilmadi (HTTP/API {code}).')

    def call(self, method: str, payload: dict[str, Any] | None = None) -> Any:
        if method not in self.METHODS:
            raise BotError('Qo‘llab-quvvatlanmaydigan Telegram amali.')
        url = f'https://api.telegram.org/bot{self.config.token}/{method}'
        req = request.Request(url, data=json.dumps(payload or {}).encode('utf-8'),
                              headers={'Content-Type': 'application/json', 'User-Agent': 'UniFlow-Telegram/1.0'},
                              method='POST')
        try:
            with self.opener(req, timeout=35 if method == 'getUpdates' else 15) as response:
                raw = response.read(2 * 1024 * 1024)
        except error.HTTPError as failure:
            try:
                parsed = json.loads(failure.read(65536))
                parsed = parsed if isinstance(parsed, dict) else {}
            except (ValueError, OSError):
                parsed = {}
            raise self.api_error(failure.code, parsed) from None
        except (error.URLError, TimeoutError, ssl.SSLError, OSError):
            # Original exception URLs can include the token. Do not expose them.
            raise TelegramError(0, 'Telegram bilan xavfsiz tarmoq aloqasi o‘rnatilmadi. Proksi va CA sozlamasini tekshiring.') from None
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            raise BotError('Telegram javobi JSON formatida emas.') from None
        if not isinstance(data, dict) or data.get('ok') is not True:
            code = data.get('error_code', 502) if isinstance(data, dict) else 502
            raise self.api_error(code if isinstance(code, int) else 502, data if isinstance(data, dict) else {})
        if 'result' not in data:
            raise BotError('Telegram javobida natija topilmadi.')
        return data['result']

    def send(self, text: str):
        text = text.replace(self.config.token, '[redacted]')
        if not text.strip() or len(text) > 4096:
            raise BotError('Xabar 1–4096 belgidan iborat bo‘lishi kerak.')
        return self.call('sendMessage', {'chat_id': self.config.chat_id, 'text': text,
                                         'link_preview_options': {'is_disabled': True}})


def ensure_private_directory(path: Path):
    if path.is_symlink():
        raise BotError('Telegram ma’lumotlar papkasi ramziy havola bo‘lmasligi kerak.')
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        metadata = path.stat()
        if metadata.st_uid != os.getuid() or not path.is_dir():
            raise BotError('Telegram papkasi joriy foydalanuvchiga tegishli bo‘lishi kerak.')
        os.chmod(path, 0o700)
    except OSError:
        raise BotError('Telegram ma’lumotlar papkasini yaratib bo‘lmadi.') from None


class Store:
    def __init__(self, directory: Path):
        self.directory = directory
        ensure_private_directory(directory)
        self.state_file = directory / 'state.json'
        self.inbox_file = directory / 'inbox.jsonl'
        self.offset = 0
        self.stored_ids: set[int] = set()
        self.lock_file = None

    def acquire(self):
        try:
            fd = os.open(self.directory / 'poll.lock', os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            self.lock_file = os.fdopen(fd, 'w')
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.close()
            raise BotError('Telegram polling allaqachon ishlayapti yoki lock fayliga ruxsat yo‘q.') from None
        self.load()

    def close(self):
        if self.lock_file:
            self.lock_file.close()
            self.lock_file = None

    def load(self):
        try:
            if self.state_file.exists():
                data = json.loads(self.state_file.read_text(encoding='utf-8'))
                offset = data.get('offset', 0)
                if not isinstance(offset, int) or offset < 0:
                    raise ValueError('offset')
                self.offset = offset
            if self.inbox_file.exists():
                with self.inbox_file.open(encoding='utf-8') as stream:
                    for line in stream:
                        item = json.loads(line)
                        self.stored_ids.add(item['update_id'])
        except (OSError, ValueError, KeyError, TypeError):
            self.close()
            raise BotError('Telegram saqlangan holatini o‘qib bo‘lmadi; fayllarni tekshiring.') from None

    def advance(self, offset: int):
        if offset <= self.offset:
            return
        descriptor, filename = tempfile.mkstemp(prefix='state-', suffix='.tmp', dir=self.directory)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump({'offset': offset}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(filename, self.state_file)
            self.offset = offset
        except OSError:
            raise BotError('Telegram holatini saqlab bo‘lmadi; qabul qilish to‘xtatildi.') from None
        finally:
            if os.path.exists(filename):
                os.unlink(filename)

    def record(self, update_id: int, message: dict[str, Any]):
        if update_id in self.stored_ids:
            return
        record = {'update_id': update_id, 'message_id': message.get('message_id'),
                  'date': message.get('date'), 'chat_id': message['chat']['id'],
                  'sender_id': message['from']['id'], 'text': message['text']}
        try:
            descriptor = os.open(self.inbox_file, os.O_CREAT | os.O_APPEND | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            with os.fdopen(descriptor, 'a', encoding='utf-8') as stream:
                metadata = os.fstat(stream.fileno())
                if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
                    raise BotError('Xabarlar fayli egasi yoki 0600 ruxsati noto‘g‘ri.')
                stream.write(json.dumps(record, ensure_ascii=False) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
            self.stored_ids.add(update_id)
        except OSError:
            raise BotError('Telegram xabarini saqlab bo‘lmadi; qabul qilish to‘xtatildi.') from None


def status_message(config: Config) -> str:
    if not config.status_file:
        return 'UniFlow bot ishlayapti. Loyiha holati fayli hali sozlanmagan. Xabar yuborishingiz mumkin.'
    try:
        with config.status_file.open(encoding='utf-8') as stream:
            status = json.loads(stream.read(65536))
        if not isinstance(status, dict):
            raise ValueError('status')
        labels = {'summary': 'Holat', 'stage': 'Bosqich', 'updated_at': 'Yangilangan'}
        lines = ['UniFlow loyiha holati']
        for key, label in labels.items():
            value = status.get(key)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                lines.append(f'{label}: {str(value)[:1000]}')
        return '\n\n'.join(lines).replace(config.token, '[redacted]')
    except (OSError, ValueError, UnicodeError):
        return 'UniFlow bot ishlayapti. Loyiha holatini hozir o‘qib bo‘lmadi.'


class Worker:
    def __init__(self, config: Config, client: TelegramClient, store: Store):
        self.config, self.client, self.store = config, client, store

    def process(self, update: dict[str, Any]):
        update_id = update.get('update_id')
        if not isinstance(update_id, int) or isinstance(update_id, bool) or update_id < self.store.offset:
            return
        message = update.get('message', {})
        if not isinstance(message, dict):
            self.store.advance(update_id + 1)
            return
        chat, sender = message.get('chat', {}), message.get('from', {})
        if not isinstance(chat, dict) or not isinstance(sender, dict):
            self.store.advance(update_id + 1)
            return
        allowed = (chat.get('id') == self.config.chat_id and chat.get('type') == 'private'
                   and sender.get('id') == self.config.chat_id and not sender.get('is_bot', False))
        text = message.get('text')
        if allowed and isinstance(text, str) and text.strip():
            command = text.strip().split(maxsplit=1)[0].split('@')[0].lower()
            if command in ['/start', '/help']:
                self.client.send(HELP_TEXT)
            elif command == '/status':
                self.client.send(status_message(self.config))
            else:
                # No interpretation, command execution, or AI calls happen here.
                sanitized = dict(message, text=text.replace(self.config.token, '[redacted]'))
                self.store.record(update_id, sanitized)
                self.client.send('Xabaringiz loyiha xabarlar qutisiga saqlandi. Bu avtomatik qabul tasdig‘i.')
        self.store.advance(update_id + 1)

    def poll(self, stop: threading.Event):
        backoff = 2
        while not stop.is_set():
            try:
                updates = self.client.call('getUpdates', {'offset': self.store.offset, 'timeout': 25, 'allowed_updates': ['message']})
                if not isinstance(updates, list):
                    raise BotError('Telegram xabarlar ro‘yxati noto‘g‘ri formatda.')
                ordered = sorted((item for item in updates if isinstance(item, dict)), key=lambda item: item.get('update_id', -1))
                for update in ordered:
                    if stop.is_set():
                        break
                    self.process(update)
                backoff = 2
            except TelegramError as failure:
                if failure.code in [401, 403, 409]:
                    raise
                print(str(failure), file=sys.stderr, flush=True)
                stop.wait(failure.retry_after if failure.code == 429 else backoff)
                backoff = min(30, backoff * 2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='UniFlow xususiy Telegram holat va xabarlar boti.')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check', action='store_true', help='Bot API autentifikatsiyasini tekshirish.')
    action.add_argument('--send', metavar='TEXT', help='Faqat sozlangan shaxsiy chatga xabar yuborish.')
    action.add_argument('--poll', action='store_true', help='Shaxsiy xabarlarni qabul qilishni boshlash.')
    parser.add_argument('--token-file', type=Path, help='0600 ruxsatli token fayli; secret muhit o‘zgaruvchisiga muqobil.')
    parser.add_argument('--chat-id', help='Ruxsat berilgan musbat shaxsiy chat ID; muhit o‘zgaruvchisiga muqobil.')
    parser.add_argument('--state-dir', type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument('--status-file', type=Path, help='summary/stage/updated_at maydonli maxfiy bo‘lmagan JSON.')
    args = parser.parse_args(argv)
    store = None
    try:
        config = Config.from_environment(token_file=args.token_file, state_dir=args.state_dir, status_file=args.status_file, chat_id=args.chat_id)
        client = TelegramClient(config)
        if args.check:
            client.call('getMe')
            print('Telegram botga ulanish tasdiqlandi.')
        elif args.send:
            client.send(args.send)
            print('Xabar yuborildi.')
        else:
            store = Store(config.state_dir)
            store.acquire()
            stop = threading.Event()
            signal.signal(signal.SIGINT, lambda *_: stop.set())
            signal.signal(signal.SIGTERM, lambda *_: stop.set())
            print('Telegram qabul qiluvchisi ishga tushdi. Faqat sozlangan shaxsiy chat qabul qilinadi.', flush=True)
            Worker(config, client, store).poll(stop)
        return 0
    except BotError as failure:
        print(str(failure), file=sys.stderr)
        return 1
    except (KeyboardInterrupt, BrokenPipeError):
        return 0
    finally:
        if store:
            store.close()


if __name__ == '__main__':
    sys.exit(main())
