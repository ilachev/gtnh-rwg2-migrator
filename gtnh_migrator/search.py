"""Build the pinned upstream offline preview and run the migration adapter."""
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

UPSTREAM = 'https://github.com/GTNewHorizons/Realistic-World-Gen-2.git'
COMMIT = '497fc1f49dcab6032fb828a818931e2c391ff10e'
ASSETS = Path(__file__).parent / 'engine'


def execute(command, cwd, log, progress):
    with subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding='utf-8', errors='replace') as process, log.open('w') as out:
        for line in process.stdout:
            out.write(line)
            out.flush()
            if 'MIGRATION_PROGRESS\t' in line:
                progress(line.strip().split('\t', 2)[-1])
        code = process.wait()
    if code:
        tail = log.read_text(errors='replace')[-4000:]
        raise ValueError(f'RWG2 preview failed. Log: {log}\n{tail}')


def search(plan, progress=lambda message: None, mode='search', radius=8192, step=256):
    if not shutil.which('git') or not shutil.which('java'):
        raise ValueError('Install Git and JDK 21 (including javac), then restart the wizard')
    if not shutil.which('javac'):
        raise ValueError('A full JDK 21 is required; a Java runtime alone is insufficient')
    cache = Path(os.environ.get('GTNH_MIGRATOR_CACHE', Path.home() / '.cache/gtnh-rwg2-migrator')).expanduser().resolve()
    cache.mkdir(parents=True, exist_ok=True)
    source = cache / 'rwg2-2.0.6'
    if not source.exists():
        progress('Downloading the official RWG2 2.0.6 source')
        execute(['git', 'clone', '--depth', '1', '--branch', '2.0.6', UPSTREAM, str(source)], cache,
                cache / 'download.log', progress)
    current = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    if current != COMMIT:
        raise ValueError('Cached RWG2 source does not match the pinned release')
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD'], cwd=source).returncode:
        raise ValueError('The cached upstream source was modified; use a clean cache folder')
    # Never patch the game's JAR. Only add a preview entry point to a separate source checkout.
    shutil.copy2(ASSETS / 'MigrationSearch.java', source / 'src/preview/java/rwg2/world/MigrationSearch.java')
    job = Path(tempfile.mkdtemp(prefix='search-', dir=cache))
    config_root = Path(plan['info']['server']) / 'config'
    shutil.copy2(config_root / 'rwg2.cfg', job / 'rwg2.cfg')
    (job / 'survey.tsv').write_text(''.join('\t'.join(map(str, row)) + '\n' for row in plan['survey']))
    (job / 'targets.tsv').write_text(''.join('\t'.join(map(str, row)) + '\n' for row in plan['targets']))
    tc = (config_root / 'Thaumcraft.cfg').read_text() if (config_root / 'Thaumcraft.cfg').exists() else ''
    def tc_id(key, default):
        match = re.search(r'(?mi)^\s*I:' + key + r'=(\d+)', tc)
        return int(match[1]) if match else default
    args = [str(job / 'rwg2.cfg'), str(plan['info']['seed']), str(job / 'survey.tsv'),
            str(job / 'targets.tsv'), str(job / 'result.json'), str(radius), str(step),
            str(tc_id('biome_magical_forest', 192)), str(tc_id('biome_taint', 193)), mode]
    if any('|' in arg for arg in args):
        raise ValueError('Paths containing | are not supported by the RWG2 preview adapter')
    wrapper = ['cmd', '/c', 'gradlew.bat'] if os.name == 'nt' else ['./gradlew']
    command = wrapper + ['migrationSearch', '--no-daemon', '--console=plain', '-I', str(ASSETS / 'migrator.gradle'),
                         '-PmigrationArgs=' + '|'.join(args)]
    command += shlex.split(os.environ.get('GTNH_GRADLE_ARGS', ''))
    progress('Building the offline generator; the first run downloads build dependencies')
    execute(command, source, job / 'build.log', progress)
    result = json.loads((job / 'result.json').read_text())
    result['engine_commit'] = COMMIT
    result['log'] = str(job / 'build.log')
    return result
