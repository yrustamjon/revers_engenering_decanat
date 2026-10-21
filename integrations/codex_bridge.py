"""A bounded, authenticated-local-CLI bridge for private Telegram conversations.

This module does not read credentials, execute Telegram text as shell code, or
claim access to an existing hosted ChatGPT conversation. Its session is a
separate persistent Codex CLI thread in the configured repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import tempfile
import threading
import time
import sys
from typing import Callable, Mapping
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTEXT_FILE = Path(__file__).with_name('PROJECT_CONTEXT.md')
MODES = frozenset({'read-only', 'workspace-write'})
REMOVED_ENVIRONMENT = frozenset({'tg_key', 'UNIFLOW_TELEGRAM_TOKEN'})
TOKEN_PATTERN = re.compile(r'\b[0-9]{5,}:[A-Za-z0-9_-]{20,}\b')
MAX_PROMPT_BYTES = 128_000
MAX_EVENT_BYTES = 1024 * 1024
MAX_REPLY_BYTES = 128_000


class BridgeError(Exception):
    """A safe message suitable for delivery to the configured Telegram user."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RunResult:
    reply: str
    session_id: str
    mode: str
    elapsed_seconds: float
    log_path: Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _private_directory(path: Path):
    try:
        if path.is_symlink():
            raise BridgeError('unsafe_state', 'Codex holat papkasi ramziy havola bo‘lmasligi kerak.')
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        metadata = path.stat()
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise BridgeError('unsafe_state', 'Codex holat papkasi joriy foydalanuvchiga tegishli bo‘lishi kerak.')
        os.chmod(path, 0o700)
    except OSError:
        raise BridgeError('state_unavailable', 'Codex holat papkasiga yozib bo‘lmadi.') from None


class CodexRunner:
    """One resumable CLI thread, serialized across processes.

    ``run()`` defaults to read-only dialogue. Only an explicit caller selection
    of ``mode='workspace-write'`` enables repository edits (for example /task).
    ``config_overrides`` contains deployment-verified Codex config keys; path
    values must resolve within state_dir. Authentication and CODEX_HOME are
    inherited unchanged. No credential files are inspected or copied.
    """

    def __init__(self, repo_path: str | Path = PROJECT_ROOT,
                 state_dir: str | Path | None = None, *, binary: str = 'codex',
                 allowed_repo_path: str | Path = PROJECT_ROOT,
                 mode: str = 'read-only', timeout: float = 900,
                 max_log_bytes: int = 2 * 1024 * 1024,
                 config_overrides: Mapping[str, str | Path] | None = None,
                 scalar_overrides: Mapping[str, str | bool] | None = None):
        if mode not in MODES:
            raise BridgeError('invalid_mode', 'Faqat read-only yoki workspace-write rejimi ruxsat etiladi.')
        if not 5 <= timeout <= 7200:
            raise BridgeError('invalid_timeout', 'Codex muddati 5–7200 soniya oralig‘ida bo‘lishi kerak.')
        if not 16384 <= max_log_bytes <= 20 * 1024 * 1024:
            raise BridgeError('invalid_log_limit', 'Codex log hajmi noto‘g‘ri sozlangan.')
        try:
            self.allowed_repo_path = Path(allowed_repo_path).resolve(strict=True)
            self.repo_path = Path(repo_path).resolve(strict=True)
            if not self.repo_path.is_dir() or not self.repo_path.is_relative_to(self.allowed_repo_path):
                raise BridgeError('invalid_repository', 'Codex faqat belgilangan loyiha ichida ishlaydi.')
            if not (self.allowed_repo_path / '.git').exists():
                raise BridgeError('invalid_repository', 'Belgilangan loyiha Git checkout bo‘lishi kerak.')
        except OSError:
            raise BridgeError('invalid_repository', 'Belgilangan loyiha papkasi topilmadi.') from None
        self.state_dir = Path(state_dir or self.allowed_repo_path / '.local' / 'codex-bridge').absolute()
        _private_directory(self.state_dir)
        self.state_dir = self.state_dir.resolve()
        self.runs_dir = self.state_dir / 'runs'
        _private_directory(self.runs_dir)
        self.state_file = self.state_dir / 'session.json'
        self.lock_path = self.state_dir / 'bridge.lock'
        self.binary, self.mode, self.timeout = binary, mode, float(timeout)
        self.max_log_bytes = max_log_bytes
        self.config_overrides: dict[str, str] = {}
        for key, value in (config_overrides or {}).items():
            if not re.fullmatch(r'[a-z][a-z0-9_.]{0,100}', key):
                raise BridgeError('invalid_config', 'Codex konfiguratsiya kaliti noto‘g‘ri.')
            destination = Path(value).absolute().resolve()
            if not destination.is_relative_to(self.state_dir):
                raise BridgeError('invalid_config', 'Codex ishchi konfiguratsiya yo‘llari holat papkasida bo‘lishi kerak.')
            _private_directory(destination)
            self.config_overrides[key] = str(destination)
        self.scalar_overrides: dict[str, str | bool] = {}
        for key, value in (scalar_overrides or {}).items():
            if key == 'history.persistence' and value in ['none', 'save-all']:
                self.scalar_overrides[key] = value
            elif re.fullmatch(r'mcp_servers\.[a-zA-Z0-9_-]{1,80}\.enabled', key) and isinstance(value, bool):
                self.scalar_overrides[key] = value
            else:
                raise BridgeError('invalid_config', 'Bu Codex scalar konfiguratsiyasi bridge orqali o‘zgartirilmaydi.')
        self._busy_lock = threading.Lock()
        self._sensitive = tuple(value for key, value in os.environ.items()
                                if key in REMOVED_ENVIRONMENT and len(value) >= 8)
        self._read_state()

    def _redact(self, text: str) -> str:
        for value in self._sensitive:
            text = text.replace(value, '[redacted]')
        text = TOKEN_PATTERN.sub('[redacted]', text)
        text = re.sub(r'(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+/-]+', r'\1[redacted]', text)
        return text

    def _read_state(self) -> dict:
        if not self.state_file.exists():
            return {'session_id': None, 'repo_path': str(self.repo_path), 'status': 'idle', 'mode': self.mode}
        try:
            if self.state_file.is_symlink():
                raise ValueError('symlink')
            metadata = self.state_file.stat()
            if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
                raise ValueError('permissions')
            state = json.loads(self.state_file.read_text(encoding='utf-8'))
            if not isinstance(state, dict) or state.get('repo_path') != str(self.repo_path):
                raise ValueError('repository')
            session_id = state.get('session_id')
            if session_id is not None:
                uuid.UUID(session_id)
            return state
        except (OSError, ValueError, TypeError, AttributeError):
            raise BridgeError('state_corrupt', 'Codex sessiya holatini o‘qib bo‘lmadi. Avtomatik yangi suhbat ochilmadi.') from None

    def _save_state(self, state: dict):
        descriptor, filename = tempfile.mkstemp(prefix='session-', suffix='.tmp', dir=self.state_dir)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump(state, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(filename, self.state_file)
        except OSError:
            raise BridgeError('state_unavailable', 'Codex sessiya holatini saqlab bo‘lmadi.') from None
        finally:
            if os.path.exists(filename):
                os.unlink(filename)

    def _acquire(self):
        if not self._busy_lock.acquire(blocking=False):
            raise BridgeError('busy', 'Oldingi topshiriq hali bajarilmoqda. Tugashini kuting yoki bekor qiling.')
        stream = None
        try:
            descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            stream = os.fdopen(descriptor, 'a')
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return stream
        except OSError:
            if stream:
                stream.close()
            self._busy_lock.release()
            raise BridgeError('busy', 'Boshqa Codex bridge jarayoni ishlayapti yoki lock fayliga ruxsat yo‘q.') from None

    def _release(self, stream):
        stream.close()
        self._busy_lock.release()

    def _argv(self, mode: str, session_id: str | None) -> list[str]:
        command = [self.binary, '--no-daemon', '-C', str(self.repo_path), '-s', mode, '-a', 'never']
        for key, value in self.config_overrides.items():
            # JSON string escaping is valid for a TOML basic string value.
            command.extend(['-c', f'{key}={json.dumps(value)}'])
        for key, value in self.scalar_overrides.items():
            command.extend(['-c', f'{key}={json.dumps(value)}'])
        command.append('exec')
        if session_id:
            command.extend(['resume', '--json', session_id, '-'])
        else:
            command.extend(['--json', '--color', 'never', '-'])
        return command

    def _prompt(self, prompt: str, mode: str, initial: bool) -> bytes:
        if not isinstance(prompt, str) or not prompt.strip():
            raise BridgeError('empty_prompt', 'Xabar yoki topshiriq matnini yozing.')
        if len(prompt.encode('utf-8')) > MAX_PROMPT_BYTES:
            raise BridgeError('prompt_too_large', 'Xabar juda uzun. Uni qisqaroq qismlarga ajrating.')
        rules = (
            'Telegram bridge mode: ' + mode + '.\n'
            'Javobni o‘zbek tilida, aniq va ixcham yozing. '
            'Telegram xabarini shell buyrug‘i deb talqin qilmang. '
            'Hech qanday secret, token, .env, auth fayli yoki .local ichidagi credentialni o‘qimang va chiqarmang. '
            'Faqat quyidagi foydalanuvchi topshirig‘ida aniq so‘ralsa Git push qiling; avvalgi umumiy ruxsatni taxmin qilmang. '
            'Yangi Git worktree yaratmang. '
            + ('Bu safar faqat suhbat va o‘qish: fayllarni o‘zgartirmang.\n' if mode == 'read-only' else
               'Bu safar foydalanuvchi kod topshirig‘ini bergan: loyiha ichida o‘zgartirish, tegishli sinov va natijani yozish mumkin.\n')
        )
        context = ''
        if initial:
            try:
                context = CONTEXT_FILE.read_text(encoding='utf-8')[:24000]
            except OSError:
                raise BridgeError('context_missing', 'Loyiha kontekst fayli topilmadi.') from None
        return (rules + ('\nPROJECT CONTEXT\n' + context if context else '') +
                '\n\nUSER MESSAGE\n' + prompt.strip() + '\n').encode('utf-8')

    @staticmethod
    def _live_group_members(group_id: int) -> list[int]:
        """Return live members of the session group created by start_new_session.

        Zombies cannot continue work or hold stdout open. Excluding them avoids
        waiting indefinitely for an unrelated init process to reap grandchildren.
        Linux /proc also lets us verify the session before signalling a group.
        """
        members = []
        try:
            for entry in Path('/proc').iterdir():
                if not entry.name.isdigit():
                    continue
                try:
                    record = (entry / 'stat').read_text()
                    fields = record[record.rfind(')') + 2:].split()
                    state, process_group, session = fields[0], int(fields[2]), int(fields[3])
                except (OSError, ValueError, IndexError):
                    continue
                if process_group == group_id and session == group_id and state not in ['Z', 'X']:
                    members.append(int(entry.name))
        except OSError:
            raise BridgeError('cleanup_unavailable', 'Codex jarayon guruhi holatini tekshirib bo‘lmadi.') from None
        return members

    @staticmethod
    def _wait_unreaped(process: subprocess.Popen, timeout: float) -> int:
        """Observe leader exit while retaining its PID until group cleanup.

        Keeping the leader as our unreaped child reserves its PID/group identity,
        preventing that numeric group ID from being recycled during cleanup.
        """
        if process.returncode is not None:
            return process.returncode
        deadline = time.monotonic() + timeout
        while True:
            try:
                result = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            except ChildProcessError:
                # Another explicit waiter may already have reaped the leader.
                return process.wait(timeout=max(.01, deadline - time.monotonic()))
            if result is not None:
                return result.si_status if result.si_code == os.CLD_EXITED else -result.si_status
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(process.args, timeout)
            time.sleep(.025)

    @classmethod
    def _terminate(cls, process: subprocess.Popen):
        if getattr(process, '_uniflow_group_cleaned', False):
            return
        group_id = process.pid
        # All runner children use start_new_session=True: PGID = SID = PID.
        # Do not use poll()/wait() here before descendants are gone: those reap
        # the leader and permit PID reuse while cleanup is still in progress.
        members = cls._live_group_members(group_id)
        if members:
            try:
                os.killpg(group_id, signal.SIGTERM)
            except ProcessLookupError:
                members = []
            deadline = time.monotonic() + (2.5 if getattr(process, '_uniflow_guardian', False) else .5)
            while members and time.monotonic() < deadline:
                time.sleep(.025)
                members = cls._live_group_members(group_id)
            if members:
                if getattr(process, '_uniflow_guardian', False):
                    # The guardian retains the cross-process lock until native
                    # descendants are gone. Killing it would release that lock
                    # while uninterruptible/otherwise unverified work survives.
                    raise BridgeError('cleanup_failed', 'Codex nazoratchisi quyi jarayonlarni to‘xtatyapti. Tugamaguncha yangi topshiriq bloklanadi.')
                try:
                    os.killpg(group_id, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                deadline = time.monotonic() + 1.5
                while cls._live_group_members(group_id) and time.monotonic() < deadline:
                    time.sleep(.025)
                if cls._live_group_members(group_id):
                    raise BridgeError('cleanup_failed', 'Codex quyi jarayonlarini to‘xtatib bo‘lmadi. Yangi topshiriqni boshlashdan oldin jarayonlar tekshirilishi kerak.')
        try:
            process.wait(timeout=.5)
        except subprocess.TimeoutExpired:
            # An unexpectedly detached leader is still our exact unreaped child.
            process.kill()
            process.wait(timeout=.5)
        process._uniflow_group_cleaned = True

    def run(self, prompt: str, on_progress: Callable[[str], None] | None = None,
            cancel_event: threading.Event | None = None, *, mode: str | None = None) -> RunResult:
        selected_mode = mode or self.mode
        if selected_mode not in MODES:
            raise BridgeError('invalid_mode', 'Faqat read-only yoki workspace-write rejimi ruxsat etiladi.')
        if cancel_event is not None and cancel_event.is_set():
            raise BridgeError('cancelled', 'Topshiriq boshlanishidan oldin bekor qilindi.')
        lock = self._acquire()
        try:
            state = self._read_state()
        except BridgeError:
            self._release(lock)
            raise
        process = None
        watch_writer = None
        selector = None
        log = None
        started = time.monotonic()
        log_path = self.runs_dir / f'run-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")}-{uuid.uuid4().hex[:8]}.jsonl'
        session_id = state.get('session_id')
        messages: list[str] = []
        diagnostic: list[str] = []
        turn_complete = False
        event_error = False
        written = 0
        log_truncated = False
        last_progress = 0.0

        def progress(text: str):
            nonlocal last_progress
            now = time.monotonic()
            if on_progress and now - last_progress >= 5:
                try:
                    on_progress(text)
                except Exception:
                    # A Telegram notification failure must not rerun code work.
                    pass
                last_progress = now

        def log_line(source: str, line: str):
            nonlocal written, log_truncated
            safe = self._redact(line)
            encoded = (json.dumps({'source': source, 'text': safe}, ensure_ascii=False) + '\n').encode('utf-8')
            if written + len(encoded) <= self.max_log_bytes - 256:
                log.write(encoded)
                log.flush()
                written += len(encoded)
            elif not log_truncated:
                marker = b'{"source":"bridge","text":"Log size limit reached; further output omitted."}\n'
                log.write(marker)
                log.flush()
                written += len(marker)
                log_truncated = True

        def consume(source: str, line: str):
            nonlocal session_id, turn_complete, event_error
            log_line(source, line)
            if source == 'stderr':
                diagnostic.append(self._redact(line)[:2000])
                del diagnostic[:-20]
                runtime_access_check(line)
                return
            try:
                event = json.loads(line)
            except ValueError:
                diagnostic.append(self._redact(line)[:2000])
                del diagnostic[:-20]
                return
            if not isinstance(event, dict):
                return
            event_type = event.get('type')
            if event_type == 'thread.started':
                candidate = event.get('thread_id')
                try:
                    uuid.UUID(candidate)
                except (ValueError, TypeError, AttributeError):
                    raise BridgeError('invalid_session', 'Codex noto‘g‘ri sessiya ID qaytardi.') from None
                if session_id and candidate != session_id:
                    raise BridgeError('session_changed', 'Codex boshqa sessiya ochdi; avvalgi suhbat avtomatik almashtirilmadi.')
                session_id = candidate
                state['session_id'] = session_id
                self._save_state(state)
            elif event_type == 'turn.started':
                progress('Codex xabaringiz ustida ishlayapti…')
            elif event_type == 'turn.completed':
                turn_complete = True
            elif event_type in ['error', 'turn.failed']:
                event_error = True
                error_text = json.dumps(event, ensure_ascii=False)
                diagnostic.append(self._redact(error_text)[:2000])
                del diagnostic[:-20]
                runtime_access_check(error_text)
            elif event_type in ['item.started', 'item.completed']:
                item = event.get('item', {})
                if not isinstance(item, dict):
                    return
                item_type = item.get('type')
                if event_type == 'item.completed' and item_type == 'agent_message' and isinstance(item.get('text'), str):
                    text = self._redact(item['text'])
                    if sum(len(message.encode('utf-8')) for message in messages) + len(text.encode('utf-8')) > MAX_REPLY_BYTES:
                        raise BridgeError('output_limit', 'Codex javobi belgilangan hajmdan oshdi; jarayon to‘xtatildi.')
                    messages.append(text)
                elif item_type == 'command_execution':
                    progress('Loyiha fayllari va sinovlar tekshirilmoqda…')
                elif item_type == 'file_change':
                    progress('Loyihadagi o‘zgarishlar tayyorlanmoqda…')

        def runtime_access_check(text: str):
            # Inspect only CLI stderr or top-level runtime error events, never
            # model tool-result events: an application may legitimately return403.
            lower = text.lower()
            explicit_proxy_denial = any(re.search(pattern, lower) for pattern in [
                r'http\s+connect[^\n]{0,150}\b403\b',
                r'proxy\s+connection\s+failed[^\n]{0,150}\b403\b',
                r'proxy[^\n]{0,80}\bconnect\b[^\n]{0,100}\b403\b',
            ])
            if explicit_proxy_denial:
                raise BridgeError('proxy_blocked', 'Cloud proksisi Codex ulanishini blokladi (403). Tarmoq ruxsati yangilangach qayta uriniladi.')
            if '401' in lower and any(marker in lower for marker in ['unauthorized', 'authentication', 'provider']) and any(
                marker in lower for marker in ['responses', 'chatgpt.com', 'api.openai.com', 'provider', 'unexpected status']
            ):
                raise BridgeError('authentication', 'Codex xizmatidagi autentifikatsiya rad etildi (401). Mavjud cloud kirishi tekshirilishi kerak.')

        try:
            payload = self._prompt(prompt, selected_mode, session_id is None)
            state.update({'repo_path': str(self.repo_path), 'status': 'running', 'mode': selected_mode,
                          'updated_at': _now(), 'last_error': None, 'log_path': str(log_path)})
            self._save_state(state)
            descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            log = os.fdopen(descriptor, 'wb')
            child_environment = os.environ.copy()
            for key in REMOVED_ENVIRONMENT:
                child_environment.pop(key, None)
            try:
                watch_reader, watch_writer = os.pipe()
                command = [sys.executable, str(Path(__file__).resolve()), '--guardian', str(watch_reader), str(lock.fileno()), '--']
                command.extend(self._argv(selected_mode, session_id))
                process = subprocess.Popen(command, cwd=self.repo_path,
                                           env=child_environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, start_new_session=True, bufsize=0,
                                           pass_fds=(watch_reader, lock.fileno()))
                process._uniflow_guardian = True
            except FileNotFoundError:
                raise BridgeError('cli_missing', 'Codex CLI o‘rnatilmagan yoki bajariladigan fayl topilmadi.') from None
            except OSError:
                raise BridgeError('cli_unavailable', 'Codex CLI jarayonini boshlashga ruxsat yo‘q.') from None
            finally:
                if 'watch_reader' in locals():
                    os.close(watch_reader)
            selector = selectors.DefaultSelector()
            for stream, name in [(process.stdout, 'stdout'), (process.stderr, 'stderr')]:
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, 'stdin')
            remaining = memoryview(payload)
            buffers = {'stdout': b'', 'stderr': b''}
            while selector.get_map():
                if cancel_event is not None and cancel_event.is_set():
                    raise BridgeError('cancelled', 'Topshiriq bekor qilindi. Shu paytgacha qilingan o‘zgarishlar saqlanadi.')
                if time.monotonic() - started > self.timeout:
                    raise BridgeError('timeout', 'Codex topshirig‘i vaqt chegarasiga yetdi. O‘zgarishlar va sessiya saqlanadi.')
                for key, _ in selector.select(timeout=.25):
                    source = key.data
                    if source == 'stdin':
                        try:
                            count = os.write(key.fd, remaining[:16384])
                            remaining = remaining[count:]
                        except (BrokenPipeError, OSError):
                            remaining = memoryview(b'')
                        if not remaining:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                        continue
                    try:
                        chunk = os.read(key.fd, 16384)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        if buffers[source]:
                            consume(source, buffers[source].decode('utf-8', errors='replace'))
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                        continue
                    buffers[source] += chunk
                    while b'\n' in buffers[source]:
                        line, buffers[source] = buffers[source].split(b'\n', 1)
                        if len(line) > MAX_EVENT_BYTES:
                            raise BridgeError('output_limit', 'Codex chiqishi belgilangan hajmdan oshdi; jarayon to‘xtatildi.')
                        consume(source, line.decode('utf-8', errors='replace'))
                    if len(buffers[source]) > MAX_EVENT_BYTES:
                        raise BridgeError('output_limit', 'Codex chiqishi belgilangan hajmdan oshdi; jarayon to‘xtatildi.')
            return_code = self._wait_unreaped(process, timeout=5)
            if return_code != 0 or event_error or not turn_complete or not messages or not session_id:
                diagnosis = '\n'.join(diagnostic).lower()
                if ('session' in diagnosis or 'thread' in diagnosis) and any(term in diagnosis for term in ['not found', 'no saved', 'does not exist', 'unknown session']):
                    raise BridgeError('session_not_found', 'Saqlangan Codex sessiyasi topilmadi. /new bilan yangi suhbatni aniq boshlash mumkin; avtomatik almashtirilmadi.')
                if any(term in diagnosis for term in ['unauthorized', 'not authenticated', 'login required', 'missing api key', '401 unauthorized']):
                    raise BridgeError('authentication', 'Codex autentifikatsiyasi ishlamayapti. Cloud muhitidagi mavjud Codex kirishini tekshirish kerak.')
                if 'read-only file system' in diagnosis or 'erofs' in diagnosis:
                    raise BridgeError('runtime_read_only', 'Codex xizmat papkasi faqat o‘qish rejimida. Cloud runtime yozish ruxsatini sozlash kerak.')
                if 'permission denied' in diagnosis:
                    raise BridgeError('runtime_permissions', 'Codex xizmat fayllarini yozish huquqi yetishmayapti. Cloud runtime sozlamasi tekshirilishi kerak.')
                if '403' in diagnosis:
                    if any(term in diagnosis for term in ['proxy', 'connect tunnel', 'websocket', 'wss://']):
                        raise BridgeError('network_policy', 'Cloud tarmog‘i Codex xizmatiga ulanishni rad etdi (403). Tarmoq ruxsatlari tekshirilishi kerak.')
                    raise BridgeError('network_access', 'Codex xizmatiga ulanish rad etildi (403). Tarmoq yoki xizmatga kirish ruxsatini tekshirish kerak.')
                raise BridgeError('cli_failed', 'Codex javobni yakunlay olmadi. Sessiya saqlandi; texnik logni loyiha mas’uli tekshirishi mumkin.')
            state.update({'status': 'completed', 'updated_at': _now(), 'last_error': None})
            self._save_state(state)
            return RunResult('\n\n'.join(messages), session_id, selected_mode, round(time.monotonic() - started, 2), log_path)
        except BridgeError as failure:
            if process:
                self._terminate(process)
            state.update({'status': failure.code, 'updated_at': _now(), 'last_error': failure.code})
            self._save_state(state)
            raise
        except (OSError, subprocess.SubprocessError):
            if process:
                self._terminate(process)
            state.update({'status': 'runtime_error', 'updated_at': _now(), 'last_error': 'runtime_error'})
            self._save_state(state)
            raise BridgeError('runtime_error', 'Codex jarayoni bilan aloqa uzildi. Sessiya avtomatik almashtirilmadi.') from None
        finally:
            if selector:
                selector.close()
            cleanup_error = None
            try:
                if process:
                    self._terminate(process)
            except BridgeError as failure:
                cleanup_error = failure
                state.update({'status': failure.code, 'last_error': failure.code, 'updated_at': _now()})
                self._save_state(state)
            finally:
                if process:
                    for stream in [process.stdin, process.stdout, process.stderr]:
                        if stream and not stream.closed:
                            stream.close()
                if log:
                    log.close()
                if watch_writer is not None:
                    os.close(watch_writer)
                self._release(lock)
            if cleanup_error:
                raise cleanup_error

    def reset(self):
        """Explicitly start a new bridge thread next time; preserve old CLI history."""
        lock = self._acquire()
        try:
            state = self._read_state()
            self._save_state({'session_id': None, 'previous_session_id': state.get('session_id'),
                              'repo_path': str(self.repo_path), 'status': 'idle', 'mode': self.mode,
                              'updated_at': _now(), 'last_error': None})
        finally:
            self._release(lock)

    def check(self, cancel_event: threading.Event | None = None) -> RunResult:
        """Make a real read-only model call; success establishes live CLI access."""
        return self.run('Bu Codex ulanish sinovi. Hech qanday vosita ishlatmang, fayl o‘qimang yoki o‘zgartirmang. '
                        'Faqat “Ulanish tayyor.” deb javob bering.', cancel_event=cancel_event, mode='read-only')

    def status(self) -> dict:
        state = self._read_state()
        result = {key: state.get(key) for key in ['session_id', 'repo_path', 'status', 'mode', 'updated_at', 'last_error', 'log_path']}
        busy = self._busy_lock.locked()
        if not busy:
            stream = None
            try:
                descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
                stream = os.fdopen(descriptor, 'a')
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                busy = True
            except OSError:
                raise BridgeError('state_unavailable', 'Codex jarayon holatini tekshirib bo‘lmadi.') from None
            finally:
                if stream:
                    stream.close()
        result['busy'] = busy
        if not busy and result['status'] == 'running':
            result['status'] = 'interrupted'
        return result


def _guardian_children() -> list[int]:
    """Direct children, including orphans adopted by the Linux subreaper."""
    parent = os.getpid()
    # Some managed Linux runtimes omit /proc/PID/task/TID/children. Inspect
    # ordinary stat records instead of treating an unavailable children file as
    # evidence that no descendants exist.
    children = []
    try:
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():
                continue
            try:
                raw = (entry / 'stat').read_text()
                fields = raw[raw.rfind(')') + 2:].split()
                if int(fields[1]) == parent:
                    children.append(int(entry.name))
            except (OSError, ValueError, IndexError):
                continue
    except OSError:
        raise BridgeError('cleanup_unavailable', 'Codex guardian quyi jarayonlarini tekshirib bo‘lmadi.') from None
    return children


def _guardian_cleanup_adopted():
    """Stop only our own adopted children; never signal arbitrary process IDs."""
    deadline = time.monotonic() + 1.5
    first = True
    while time.monotonic() < deadline:
        while True:
            try:
                child, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                child = 0
            if child == 0:
                break
        children = _guardian_children()
        if not children:
            return
        for pid in children:
            try:
                # Confirm this PID still belongs to us before signalling it.
                raw = Path(f'/proc/{pid}/stat').read_text()
                fields = raw[raw.rfind(')') + 2:].split()
                if int(fields[1]) == os.getpid() and fields[0] not in ['Z', 'X']:
                    os.kill(pid, signal.SIGTERM if first else signal.SIGKILL)
            except (OSError, ValueError, IndexError):
                continue
        time.sleep(.15 if first else .025)
        first = False
    if _guardian_children():
        raise BridgeError('cleanup_failed', 'Codex guardian quyi jarayonlarni to‘liq to‘xtata olmadi.')


def _guardian_main(arguments: list[str]) -> int:
    """Supervise native CLI if the Telegram worker crashes or is SIGKILLed.

    The inherited flock remains held until this process has stopped descendants.
    The parentwatch write end exists only in the calling worker; EOF therefore
    detects abrupt death even while the native CLI is detached in its session.
    Linux subreaping also captures descendants that deliberately call setsid().
    """
    if len(arguments) < 4 or arguments[2] != '--':
        return 2
    try:
        watch_fd, inherited_lock = int(arguments[0]), int(arguments[1])
        os.fstat(watch_fd)
        os.fstat(inherited_lock)
    except (OSError, ValueError):
        return 2
    try:
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
            print('Codex guardian: quyi jarayon nazoratini yoqib bo‘lmadi.', file=sys.stderr, flush=True)
            return 1
    except (OSError, AttributeError):
        print('Codex guardian: Linux subreaper talab qilinadi.', file=sys.stderr, flush=True)
        return 1
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    selector = selectors.DefaultSelector()
    selector.register(watch_fd, selectors.EVENT_READ)
    os.set_blocking(watch_fd, False)
    child = None
    try:
        # If the worker died before guardian startup, do not start any CLI.
        if selector.select(timeout=0):
            if os.read(watch_fd, 1) == b'':
                return 1
        child = subprocess.Popen(arguments[3:], stdin=sys.stdin.buffer, stdout=sys.stdout.buffer,
                                 stderr=sys.stderr.buffer, start_new_session=True, close_fds=True)
        while True:
            if stop.is_set():
                return 1
            for _, _ in selector.select(timeout=.05):
                if os.read(watch_fd, 1) == b'':
                    return 1
            result = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            if result is not None:
                return result.si_status if result.si_code == os.CLD_EXITED else 128 + result.si_status
    except FileNotFoundError:
        print('Codex CLI bajariladigan fayli topilmadi.', file=sys.stderr, flush=True)
        return 127
    except (OSError, ChildProcessError):
        print('Codex guardian: native jarayon bilan aloqa uzildi.', file=sys.stderr, flush=True)
        return 1
    finally:
        warned = False
        while True:
            try:
                if child:
                    CodexRunner._terminate(child)
                _guardian_cleanup_adopted()
                break
            except (BridgeError, OSError, subprocess.SubprocessError):
                # Fail closed: inherited flock remains held so another worker
                # cannot overlap with descendants whose termination is unknown.
                if not warned:
                    try:
                        print('Codex guardian: quyi jarayonlar to‘xtashi kutilmoqda; yangi ish bloklangan.', file=sys.stderr, flush=True)
                    except (BrokenPipeError, OSError):
                        pass
                    warned = True
                time.sleep(.25)
        selector.close()
        os.close(watch_fd)
        os.close(inherited_lock)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--guardian':
        sys.exit(_guardian_main(sys.argv[2:]))
    print('Bu modul Telegram assistant worker orqali ishlatiladi.', file=sys.stderr)
    sys.exit(2)
