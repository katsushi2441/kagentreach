from __future__ import annotations

import importlib.util
import os
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "news-opinion-research.py"


def load_module():
    spec = importlib.util.spec_from_file_location("news_opinion_research", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_mcporter_finds_nvm_binary_without_shell_path(tmp_path, monkeypatch):
    module = load_module()
    binary = tmp_path / ".nvm" / "versions" / "node" / "v20.20.2" / "bin" / "mcporter"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)

    monkeypatch.delenv("KAGENTREACH_MCPORTER_BIN", raising=False)
    monkeypatch.setattr(module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(module.Path, "home", classmethod(lambda cls: tmp_path))

    assert module.resolve_mcporter() == str(binary)


def test_resolve_mcporter_prefers_configured_binary(tmp_path, monkeypatch):
    module = load_module()
    binary = tmp_path / "mcporter"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    monkeypatch.setenv("KAGENTREACH_MCPORTER_BIN", str(binary))

    assert module.resolve_mcporter() == str(binary)


def test_mcporter_command_uses_matching_nvm_node(tmp_path):
    module = load_module()
    binary = tmp_path / "bin" / "mcporter"
    node = binary.parent / "node"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/usr/bin/env node\n", encoding="utf-8")
    node.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    node.chmod(0o755)

    assert module.mcporter_command(str(binary)) == [str(node), str(binary)]
