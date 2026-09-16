import shutil
from pathlib import Path

import pytest

from wiki_dispatcher.config import REPO_ROOT
from wiki_dispatcher.fixture import make_fixture_vault
from wiki_dispatcher.vault.index import VaultIndex


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    return make_fixture_vault(tmp_path / "vault")


@pytest.fixture
def ix(vault: Path, tmp_path: Path) -> VaultIndex:
    i = VaultIndex(vault, tmp_path / "index.db")
    i.build()
    return i


@pytest.fixture
def skills_copy(tmp_path: Path) -> Path:
    dst = tmp_path / "skills"
    shutil.copytree(REPO_ROOT / "skills", dst)
    return dst


@pytest.fixture
def garden_dir(tmp_path: Path) -> Path:
    g = tmp_path / "garden"
    (g / "wiki" / "patterns").mkdir(parents=True)
    (g / "raw" / "traces").mkdir(parents=True)
    (g / "pending").mkdir()
    (g / "wiki" / "index.md").write_text("# Garden index\n\n## Patterns\n\n")
    return g
