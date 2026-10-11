"""备份：把用户数据目录打成一个压缩包。

- 本地快照放在 数据目录/backups，保留最近 7 份，作为最后一道保险。
- 设置了同步文件夹（例如百度网盘的「同步空间」）时，再复制一份过去，保留最近 30 份，由网盘客户端负责上传。
- 数据库用 SQLite 在线备份得到一致的副本；API Key 不在数据目录里，也就不会进入备份。
- 恢复前先给当前数据拍一份「恢复前」快照，再整体替换。
"""
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import zipfile

PREFIX = 'Violet-备份-'
LOCAL_KEEP = 7
SYNC_KEEP = 30
# geese-sessions.bin: portal logins stay on this machine (they are DPAPI-bound to it anyway) and never reach a sync folder.
SKIP = {'backups', 'instance.json', 'restore-tmp', 'geese-sessions.bin'}
SKIP_SUFFIX = ('.tmp', '-journal', '-wal', '-shm')


def _is_backup(name):
    return name.startswith(PREFIX) and name.endswith('.zip')


def list_backups(folder):
    folder = Path(folder) if folder else None
    if not folder or not folder.is_dir():
        return []
    out = []
    for path in folder.iterdir():
        if path.is_file() and _is_backup(path.name):
            stat = path.stat()
            out.append({'name': path.name, 'folder': str(folder), 'size': stat.st_size, 'time': stat.st_mtime})
    return sorted(out, key=lambda b: b['time'], reverse=True)


def _prune(folder, keep):
    for item in list_backups(folder)[keep:]:
        try:
            (Path(item['folder']) / item['name']).unlink()
        except OSError:
            pass


def snapshot(data_dir, desk, folder, reason='日常'):
    """Write one zip into folder and return its path."""
    data_dir, folder = Path(data_dir), Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    target = folder / f'{PREFIX}{stamp}.zip'
    counter = 2
    while target.exists():  # two snapshots within one second (e.g. the safety copy before a restore)
        target = folder / f'{PREFIX}{stamp}-{counter}.zip'
        counter += 1
    partial = target.with_name(target.name + '.part')
    with tempfile.TemporaryDirectory(prefix='violet-backup-') as scratch:
        db_copy = Path(scratch) / 'desk.db'
        if desk is not None:
            desk.backup_to(db_copy)
        with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('violet-backup.json', json.dumps(
                {'reason': reason, 'time': datetime.now().isoformat(timespec='seconds'), 'format': 1},
                ensure_ascii=False))
            if db_copy.exists():
                archive.write(db_copy, 'desk.db')
            for path in sorted(data_dir.rglob('*')):
                relative = path.relative_to(data_dir)
                if (not path.is_file() or relative.parts[0] in SKIP or path.name == 'desk.db'
                        or path.name.endswith(SKIP_SUFFIX)):
                    continue
                archive.write(path, relative.as_posix())
    partial.replace(target)
    return target


def run(data_dir, desk, sync_dir='', reason='日常'):
    """Local snapshot, then a copy to the sync folder if one is set. Returns {'local':…, 'sync':…, 'error':…}."""
    result = {'local': None, 'sync': None, 'error': ''}
    local = snapshot(data_dir, desk, Path(data_dir) / 'backups', reason)
    result['local'] = str(local)
    _prune(Path(data_dir) / 'backups', LOCAL_KEEP)
    if sync_dir:
        try:
            Path(sync_dir).mkdir(parents=True, exist_ok=True)
            copy = Path(sync_dir) / local.name
            shutil.copy2(local, copy.with_name(copy.name + '.part'))
            copy.with_name(copy.name + '.part').replace(copy)
            result['sync'] = str(copy)
            _prune(sync_dir, SYNC_KEEP)
        except OSError as error:
            result['error'] = f'同步文件夹写不进去：{error.strerror or error}'
    return result


def last_backup_day(data_dir):
    items = list_backups(Path(data_dir) / 'backups')
    return datetime.fromtimestamp(items[0]['time']).date() if items else None


def check(path):
    """Open the archive and make sure the database inside is healthy. Returns the archive's manifest."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if 'violet-backup.json' not in names:
            raise ValueError('这不是 Violet 的备份文件')
        for name in names:
            if name.startswith('/') or '..' in Path(name).parts:
                raise ValueError('备份文件里有不安全的路径')
        manifest = json.loads(archive.read('violet-backup.json').decode('utf-8'))
        if 'desk.db' in names:
            with tempfile.TemporaryDirectory(prefix='violet-check-') as scratch:
                archive.extract('desk.db', scratch)
                db = sqlite3.connect(os.path.join(scratch, 'desk.db'))
                try:
                    if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise ValueError('备份里的数据库已损坏')
                finally:
                    db.close()
    return manifest


def extract(path, data_dir):
    """Unpack a checked archive over data_dir (the caller has closed the database)."""
    data_dir = Path(data_dir)
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name == 'violet-backup.json' or name.endswith('/'):
                continue
            target = data_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + '.tmp')
            with archive.open(name) as source, open(partial, 'wb') as out:
                shutil.copyfileobj(source, out)
            partial.replace(target)
