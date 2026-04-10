from unittest.mock import patch

from bridge import PromptDetector


class TestHasPrompt:
    def test_detects_allow(self):
        assert PromptDetector.has_prompt(["Allow Read of foo.rb"]) is True

    def test_detects_deny(self):
        assert PromptDetector.has_prompt(["Deny this action"]) is True

    def test_detects_yes_no_choice(self):
        assert PromptDetector.has_prompt(["(y)es, (n)o, (a)lways"]) is True

    def test_detects_yn_bracket(self):
        assert PromptDetector.has_prompt(["Continue? [y/n]"]) is True

    def test_detects_claude_prompt_symbol(self):
        assert PromptDetector.has_prompt(["❯ "]) is True
        assert PromptDetector.has_prompt(["❯"]) is True

    def test_detects_question(self):
        assert PromptDetector.has_prompt(["Which approach do you prefer?"]) is True

    def test_ignores_regular_output(self):
        assert PromptDetector.has_prompt(["Reading file foo.rb..."]) is False
        assert PromptDetector.has_prompt(["def hello_world"]) is False

    def test_empty_input(self):
        assert PromptDetector.has_prompt([]) is False
        assert PromptDetector.has_prompt([""]) is False


class TestExtractContext:
    def test_extracts_last_n_lines(self):
        content = "\n".join(f"line {i}" for i in range(30))
        result = PromptDetector.extract_context(content, max_lines=5)
        assert result == "line 25\nline 26\nline 27\nline 28\nline 29"

    def test_returns_all_if_fewer_than_max(self):
        content = "line 1\nline 2\nline 3"
        result = PromptDetector.extract_context(content, max_lines=10)
        assert result == "line 1\nline 2\nline 3"

    def test_strips_trailing_whitespace(self):
        content = "line 1\nline 2\n\n"
        result = PromptDetector.extract_context(content)
        assert result == "line 1\nline 2"


class TestUpdate:
    def test_returns_none_on_first_content(self):
        detector = PromptDetector(quiescence_seconds=0)
        result = detector.update("Allow this?")
        assert result is None  # First call is always a content change

    def test_returns_context_when_quiescent_with_prompt(self):
        detector = PromptDetector(quiescence_seconds=0)
        detector.update("Allow this?")
        result = detector.update("Allow this?")
        assert result is not None
        assert "Allow this?" in result

    def test_deduplicates_notifications(self):
        detector = PromptDetector(quiescence_seconds=0)
        detector.update("Allow this?")
        detector.update("Allow this?")  # First notification
        result = detector.update("Allow this?")  # Same content — no re-notify
        assert result is None

    def test_notifies_again_after_content_changes(self):
        detector = PromptDetector(quiescence_seconds=0)
        detector.update("Allow this?")
        detector.update("Allow this?")  # Notifies
        detector.update("Working...")  # Content changed
        detector.update("Allow that?")  # New content
        result = detector.update("Allow that?")  # New prompt — should notify
        assert result is not None
        assert "Allow that?" in result

    def test_no_notification_without_prompt_pattern(self):
        detector = PromptDetector(quiescence_seconds=0)
        detector.update("Just regular output")
        result = detector.update("Just regular output")
        assert result is None

    @patch("bridge.time.monotonic")
    def test_respects_quiescence_period(self, mock_time):
        mock_time.return_value = 100.0
        detector = PromptDetector(quiescence_seconds=3.0)
        detector.update("Allow this?")

        mock_time.return_value = 101.0  # 1s later — not quiescent
        result = detector.update("Allow this?")
        assert result is None

        mock_time.return_value = 104.0  # 4s later — quiescent
        result = detector.update("Allow this?")
        assert result is not None
