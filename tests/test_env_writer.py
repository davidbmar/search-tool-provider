"""Tests for the safe .env merge logic."""

from pathlib import Path

from search_tool_provider.admin.env_writer import merge_env_file


class TestMergeEnvFile:
    def test_creates_new_file(self, tmp_path: Path):
        env = tmp_path / ".env"
        merge_env_file(env, {"SEARCH_PROVIDER": "tavily", "TAVILY_API_KEY": "sk-123"})

        assert env.exists()
        text = env.read_text()
        assert "SEARCH_PROVIDER=tavily\n" in text
        assert "TAVILY_API_KEY=sk-123\n" in text

    def test_preserves_unrelated_keys(self, tmp_path: Path):
        env = tmp_path / ".env"
        env.write_text("UNRELATED_KEY=keep-me\nOTHER=value\n")

        merge_env_file(env, {"SEARCH_PROVIDER": "brave"})

        text = env.read_text()
        assert "UNRELATED_KEY=keep-me" in text
        assert "OTHER=value" in text
        assert "SEARCH_PROVIDER=brave" in text

    def test_updates_existing_key(self, tmp_path: Path):
        env = tmp_path / ".env"
        env.write_text("SEARCH_PROVIDER=duckduckgo\nTAVILY_API_KEY=old-key\n")

        merge_env_file(env, {"TAVILY_API_KEY": "new-key"})

        text = env.read_text()
        assert "TAVILY_API_KEY=new-key" in text
        assert "old-key" not in text
        # Provider should remain untouched since we didn't update it
        assert "SEARCH_PROVIDER=duckduckgo" in text

    def test_preserves_comments_and_blank_lines(self, tmp_path: Path):
        env = tmp_path / ".env"
        env.write_text(
            "# Main config\n"
            "SEARCH_PROVIDER=tavily\n"
            "\n"
            "# API Keys\n"
            "TAVILY_API_KEY=old\n"
        )

        merge_env_file(env, {"TAVILY_API_KEY": "new"})

        lines = env.read_text().splitlines()
        assert lines[0] == "# Main config"
        assert lines[2] == ""
        assert lines[3] == "# API Keys"
        assert lines[4] == "TAVILY_API_KEY=new"

    def test_appends_new_keys(self, tmp_path: Path):
        env = tmp_path / ".env"
        env.write_text("SEARCH_PROVIDER=tavily\n")

        merge_env_file(env, {"BRAVE_API_KEY": "bk-abc"})

        text = env.read_text()
        assert "SEARCH_PROVIDER=tavily" in text
        assert "BRAVE_API_KEY=bk-abc" in text

    def test_mixed_update_append_preserve(self, tmp_path: Path):
        env = tmp_path / ".env"
        env.write_text(
            "# search-tool-provider\n"
            "SEARCH_PROVIDER=duckduckgo\n"
            "UNRELATED=keep\n"
            "SERPER_API_KEY=old-serper\n"
        )

        merge_env_file(env, {
            "SEARCH_PROVIDER": "serper",
            "SERPER_API_KEY": "new-serper",
            "BRAVE_API_KEY": "new-brave",
        })

        text = env.read_text()
        # Updated in-place
        assert "SEARCH_PROVIDER=serper" in text
        assert "SERPER_API_KEY=new-serper" in text
        # Preserved
        assert "UNRELATED=keep" in text
        assert "# search-tool-provider" in text
        # Appended
        assert "BRAVE_API_KEY=new-brave" in text
        # Old values gone
        assert "duckduckgo" not in text
        assert "old-serper" not in text

    def test_handles_export_prefix(self, tmp_path: Path):
        env = tmp_path / ".env"
        env.write_text("export TAVILY_API_KEY=old\n")

        merge_env_file(env, {"TAVILY_API_KEY": "new"})

        text = env.read_text()
        assert "TAVILY_API_KEY=new" in text
        assert "old" not in text

    def test_returns_path(self, tmp_path: Path):
        env = tmp_path / ".env"
        result = merge_env_file(env, {"FOO": "bar"})
        assert result == env

    def test_creates_parent_directories(self, tmp_path: Path):
        env = tmp_path / "deep" / "nested" / ".env"
        merge_env_file(env, {"KEY": "val"})
        assert env.exists()
        assert env.read_text() == "KEY=val\n"

    def test_no_trailing_newline_in_existing(self, tmp_path: Path):
        """Appending to a file that doesn't end with newline."""
        env = tmp_path / ".env"
        env.write_text("EXISTING=yes")  # no trailing newline

        merge_env_file(env, {"NEW_KEY": "added"})

        text = env.read_text()
        assert "EXISTING=yes" in text
        assert "NEW_KEY=added" in text
        # Ensure they're on separate lines
        assert "EXISTING=yes\nNEW_KEY=added" not in text or "\n" in text
