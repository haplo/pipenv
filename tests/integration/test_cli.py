"""Tests to ensure `pipenv --option` works.
"""

import os
import re
from pathlib import Path
import pytest

from flaky import flaky

from pipenv.utils.processes import subprocess_run
from pipenv.utils.shell import normalize_drive


@pytest.mark.cli
def test_pipenv_where(pipenv_instance_pypi):
    with pipenv_instance_pypi() as p:
        c = p.pipenv("--where")
        assert c.returncode == 0
        assert normalize_drive(p.path) in c.stdout


@pytest.mark.cli
def test_pipenv_venv(pipenv_instance_pypi):
    with pipenv_instance_pypi() as p:
        c = p.pipenv('--python python')
        assert c.returncode == 0
        c = p.pipenv('--venv')
        assert c.returncode == 0
        venv_path = c.stdout.strip()
        assert os.path.isdir(venv_path)


@pytest.mark.cli
def test_pipenv_py(pipenv_instance_pypi):
    with pipenv_instance_pypi() as p:
        c = p.pipenv('--python python')
        assert c.returncode == 0
        c = p.pipenv('--py')
        assert c.returncode == 0
        python = c.stdout.strip()
        assert os.path.basename(python).startswith('python')


@pytest.mark.cli
def test_pipenv_site_packages(pipenv_instance_pypi):
    with pipenv_instance_pypi() as p:
        c = p.pipenv('--python python --site-packages')
        assert c.returncode == 0
        assert 'Making site-packages available' in c.stderr

        # no-global-site-packages.txt under stdlib dir should not exist.
        c = p.pipenv('run python -c "import sysconfig; print(sysconfig.get_path(\'stdlib\'))"')
        assert c.returncode == 0
        stdlib_path = c.stdout.strip()
        assert not os.path.isfile(os.path.join(stdlib_path, 'no-global-site-packages.txt'))


@pytest.mark.cli
def test_pipenv_support(pipenv_instance_pypi):
    with pipenv_instance_pypi() as p:
        c = p.pipenv('--support')
        assert c.returncode == 0
        assert c.stdout


@pytest.mark.cli
def test_pipenv_rm(pipenv_instance_pypi):
    with pipenv_instance_pypi() as p:
        c = p.pipenv('--python python')
        assert c.returncode == 0
        c = p.pipenv('--venv')
        assert c.returncode == 0
        venv_path = c.stdout.strip()
        assert os.path.isdir(venv_path)

        c = p.pipenv('--rm')
        assert c.returncode == 0
        assert c.stdout
        assert not os.path.isdir(venv_path)


@pytest.mark.cli
def test_pipenv_graph(pipenv_instance_pypi):
    with pipenv_instance_pypi() as p:
        c = p.pipenv('install tablib')
        assert c.returncode == 0
        graph = p.pipenv("graph")
        assert graph.returncode == 0
        assert "tablib" in graph.stdout
        graph_json = p.pipenv("graph --json")
        assert graph_json.returncode == 0
        assert "tablib" in graph_json.stdout
        graph_json_tree = p.pipenv("graph --json-tree")
        assert graph_json_tree.returncode == 0
        assert "tablib" in graph_json_tree.stdout


@pytest.mark.cli
def test_pipenv_graph_reverse(pipenv_instance_private_pypi):
    with pipenv_instance_private_pypi() as p:
        c = p.pipenv('install tablib==0.13.0')
        assert c.returncode == 0
        c = p.pipenv('graph --reverse')
        assert c.returncode == 0
        output = c.stdout

        c = p.pipenv('graph --reverse --json')
        assert c.returncode == 1
        assert 'Warning: Using both --reverse and --json together is not supported.' in c.stderr

        requests_dependency = [
            ('backports.csv', 'backports.csv'),
            ('odfpy', 'odfpy'),
            ('openpyxl', 'openpyxl>=2.4.0'),
            ('pyyaml', 'pyyaml'),
            ('xlrd', 'xlrd'),
            ('xlwt', 'xlwt'),
        ]

        for dep_name, dep_constraint in requests_dependency:
            pat = fr'^[ -]*{dep_name}==[\d.]+'
            dep_match = re.search(pat, output, flags=re.MULTILINE)
            assert dep_match is not None, f'{pat} not found in {output}'

            # openpyxl should be indented
            if dep_name == 'openpyxl':
                openpyxl_dep = re.search(r'^openpyxl', output, flags=re.MULTILINE)
                assert openpyxl_dep is None, f'openpyxl should not appear at beginning of lines in {output}'

                assert '  - openpyxl==2.5.4 [requires: et-xmlfile]' in output
            else:
                dep_match = re.search(fr'^[ -]*{dep_name}==[\d.]+$', output, flags=re.MULTILINE)
                assert dep_match is not None, f'{dep_name} not found at beginning of line in {output}'

            dep_requests_match = re.search(fr'^ +- tablib==0.13.0 \[requires: {dep_constraint}\]$', output, flags=re.MULTILINE)
            assert dep_requests_match is not None, f'constraint {dep_constraint} not found in {output}'
            assert dep_requests_match.start() > dep_match.start()


@pytest.mark.cli
@pytest.mark.needs_internet(reason='required by check')
@flaky
def test_pipenv_check(pipenv_instance_private_pypi):
    with pipenv_instance_private_pypi() as p:
        c = p.pipenv('install pyyaml')
        assert c.returncode == 0
        c = p.pipenv('check')
        assert c.returncode != 0
        assert 'pyyaml' in c.stdout
        c = p.pipenv('uninstall pyyaml')
        assert c.returncode == 0
        c = p.pipenv('install six')
        assert c.returncode == 0
        # Note: added
        # 51457: py <=1.11.0 resolved (1.11.0 installed)!
        # this is install via pytest, and causes a false positive
        # https://github.com/pytest-dev/py/issues/287
        # the issue above is still not resolved.
        # added also 51499
        # https://github.com/pypa/wheel/issues/481
        c = p.pipenv('check --ignore 35015 -i 51457 -i 51499')
        assert c.returncode == 0
        assert 'Ignoring' in c.stderr


@pytest.mark.cli
def test_pipenv_clean(pipenv_instance_pypi):
    with pipenv_instance_pypi(chdir=True) as p:
        with open('setup.py', 'w') as f:
            f.write('from setuptools import setup; setup(name="empty")')
        c = p.pipenv('install -e .')
        assert c.returncode == 0
        c = p.pipenv(f'run pip install -i {p.index_url} six')
        assert c.returncode == 0
        c = p.pipenv('clean')
        assert c.returncode == 0
        assert 'six' in c.stdout, f"{c.stdout} -- STDERR: {c.stderr}"


@pytest.mark.cli
def test_venv_envs(pipenv_instance_pypi):
    with pipenv_instance_pypi() as p:
        assert p.pipenv('--envs').stdout


@pytest.mark.cli
def test_bare_output(pipenv_instance_pypi):
    with pipenv_instance_pypi() as p:
        assert p.pipenv('').stdout


@pytest.mark.cli
def test_scripts(pipenv_instance_pypi):
    with pipenv_instance_pypi() as p:
        with open(p.pipfile_path, "w") as f:
            contents = """
[scripts]
pyver = "which python"
            """.strip()
            f.write(contents)
        c = p.pipenv('scripts')
        assert 'pyver' in c.stdout
        assert 'which python' in c.stdout


@pytest.mark.cli
def test_help(pipenv_instance_pypi):
    with pipenv_instance_pypi() as p:
        assert p.pipenv('--help').stdout


@pytest.mark.cli
def test_man(pipenv_instance_pypi):
    with pipenv_instance_pypi():
        c = subprocess_run(["pipenv", "--man"])
        assert c.returncode == 0, c.stderr


@pytest.mark.cli
def test_install_parse_error(pipenv_instance_private_pypi):
    with pipenv_instance_private_pypi() as p:

        # Make sure unparseable packages don't wind up in the pipfile
        # Escape $ for shell input
        with open(p.pipfile_path, 'w') as f:
            contents = """
[packages]

[dev-packages]
            """.strip()
            f.write(contents)
        c = p.pipenv('install requests u/\\/p@r\\$34b13+pkg')
        assert c.returncode != 0
        assert 'u/\\/p@r$34b13+pkg' not in p.pipfile['packages']


@pytest.mark.cli
def test_pipenv_clear(pipenv_instance_pypi):
    with pipenv_instance_pypi() as p:
        c = p.pipenv('--clear')
        assert c.returncode == 0
        assert 'Clearing caches' in c.stdout


@pytest.mark.cli
def test_pipenv_three(pipenv_instance_pypi):
    with pipenv_instance_pypi() as p:
        c = p.pipenv('--three')
        assert c.returncode == 0
        assert 'Successfully created virtual environment' in c.stdout


@pytest.mark.outdated
def test_pipenv_outdated_prerelease(pipenv_instance_pypi):
    with pipenv_instance_pypi(chdir=True) as p:
        with open(p.pipfile_path, "w") as f:
            contents = """
[packages]
sqlalchemy = "<=1.2.3"
            """.strip()
            f.write(contents)
        c = p.pipenv('update --pre --outdated')
        assert c.returncode == 0


@pytest.mark.cli
def test_pipenv_verify_without_pipfile(pipenv_instance_pypi):
    with pipenv_instance_pypi(pipfile=False) as p:
        c = p.pipenv('verify')
        assert c.returncode == 1
        assert 'No Pipfile present at project home.' in c.stderr


@pytest.mark.cli
def test_pipenv_verify_without_pipfile_lock(pipenv_instance_pypi):
    with pipenv_instance_pypi() as p:
        c = p.pipenv('verify')
        assert c.returncode == 1
        assert 'Pipfile.lock is out-of-date.' in c.stderr


@pytest.mark.cli
def test_pipenv_verify_locked_passing(pipenv_instance_pypi):
    with pipenv_instance_pypi() as p:
        p.pipenv('lock')
        c = p.pipenv('verify')
        assert c.returncode == 0
        assert 'Pipfile.lock is up-to-date.' in c.stdout


@pytest.mark.cli
def test_pipenv_verify_locked_outdated_failing(pipenv_instance_private_pypi):
    with pipenv_instance_private_pypi() as p:
        p.pipenv('lock')

        # modify the Pipfile
        pf = Path(p.path).joinpath('Pipfile')
        pf_data = pf.read_text()
        pf_new = re.sub(r'\[packages\]', '[packages]\nrequests = "*"', pf_data)
        pf.write_text(pf_new)

        c = p.pipenv('verify')
        assert c.returncode == 1
        assert 'Pipfile.lock is out-of-date.' in c.stderr
