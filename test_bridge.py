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
