import io
import json
import os
import stat
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from baseplate import assistant, core


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def lines(*items):
    return FakeResponse("".join(i + "\n" for i in items).encode())


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XDG_DATA_HOME"] = str(Path(self.tmp.name) / "data")
        os.environ["XDG_CONFIG_HOME"] = str(Path(self.tmp.name) / "config")

    def tearDown(self):
        self.tmp.cleanup()

    def test_keys_are_private_and_removable(self):
        self.assertIsNone(assistant.get_key("claude"))
        assistant.set_key("claude", "sk-ant-" + "a" * 30)
        self.assertEqual(assistant.get_key("claude"), "sk-ant-" + "a" * 30)
        mode = stat.S_IMODE((core.config_dir() / "ai-keys.json").stat().st_mode)
        self.assertEqual(mode, 0o600)
        with self.assertRaises(core.BaseplateError):
            assistant.set_key("openai", "short")
        assistant.set_key("claude", None)
        self.assertIsNone(assistant.get_key("claude"))
        core.delete_all_data()
        self.assertFalse((core.config_dir() / "ai-keys.json").exists())

    def test_system_prompt_has_naming_rules(self):
        p = assistant.SYSTEM_PROMPT
        for word in ("InventorySystemV3", "PlayerMovement_New", "single source of truth",
                     "refactor the existing name"):
            self.assertIn(word, p)

    def test_context_and_messages(self):
        ctx = assistant.build_context("Inventory", ["notes.md", "src/shared/Item.luau"],
                                      "src/shared/Item.luau", "return {}", "Holds items")
        self.assertIn("Open file src/shared/Item.luau", ctx)
        self.assertIn("```lua\nreturn {}\n```", ctx)
        big = assistant.build_context("P", [], "a.luau", "x" * 50_000, None)
        self.assertLessEqual(len(big), assistant.MAX_CONTEXT_CHARS + 20)
        msgs = assistant.make_messages(
            [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"},
             {"role": "system", "content": "ignored"}], "fix it", ctx)
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant", "user"])
        self.assertIn("<context>", msgs[-1]["content"])

    def test_code_blocks(self):
        text = "Here:\n```lua\nlocal x = 1\n```\nand\n```json\n{}\n```"
        self.assertEqual(assistant.code_blocks(text),
                         [("lua", "local x = 1\n"), ("json", "{}\n")])

    def test_claude_stream(self):
        assistant.set_key("claude", "sk-ant-" + "a" * 30)
        body = lines(
            'event: message_start', 'data: {"type":"message_start"}', '',
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hel"}}',
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"lo"}}',
            'data: {"type":"message_stop"}')
        got = []
        with mock.patch("urllib.request.urlopen", return_value=body) as op:
            out = assistant.stream_chat("claude", "claude-sonnet-5-5",
                                        [{"role": "user", "content": "hi"}], got.append)
        self.assertEqual(out, "Hello")
        self.assertEqual(got, ["Hel", "lo"])
        req = op.call_args[0][0]
        self.assertEqual(req.get_header("X-api-key"), "sk-ant-" + "a" * 30)
        sent = json.loads(req.data)
        self.assertTrue(sent["stream"])
        self.assertIn("InventorySystemV3", sent["system"])

    def test_openai_stream(self):
        assistant.set_key("openai", "sk-" + "b" * 30)
        body = lines('data: {"choices":[{"delta":{"role":"assistant"}}]}',
                     'data: {"choices":[{"delta":{"content":"pri"}}]}',
                     'data: {"choices":[{"delta":{"content":"nt"}}]}',
                     'data: [DONE]')
        with mock.patch("urllib.request.urlopen", return_value=body) as op:
            out = assistant.stream_chat("openai", "gpt-6.1-sol",
                                        [{"role": "user", "content": "hi"}], lambda t: None)
        self.assertEqual(out, "print")
        sent = json.loads(op.call_args[0][0].data)
        self.assertEqual(sent["messages"][0]["role"], "system")

    def test_ollama_stream_and_cancel(self):
        body = lines('{"message":{"role":"assistant","content":"a"},"done":false}',
                     '{"message":{"role":"assistant","content":"b"},"done":false}',
                     '{"message":{"role":"assistant","content":"c"},"done":true}')
        stop = threading.Event()

        def on_text(t):
            if t == "b":
                stop.set()
        with mock.patch("urllib.request.urlopen", return_value=body):
            out = assistant.stream_chat("ollama", "qwen2.5-coder",
                                        [{"role": "user", "content": "hi"}], on_text, stop)
        self.assertEqual(out, "ab")

    def test_errors_are_plain(self):
        assistant.set_key("claude", "sk-ant-" + "a" * 30)

        def refuse(*_a, **_k):
            raise urllib.error.HTTPError(
                "u", 401, "no", {}, io.BytesIO(b'{"error":{"message":"invalid x-api-key"}}'))
        with mock.patch("urllib.request.urlopen", refuse):
            with self.assertRaises(assistant.AssistantError) as cm:
                assistant.stream_chat("claude", "m", [], lambda t: None)
        self.assertIn("invalid x-api-key", str(cm.exception))
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("refused")):
            with self.assertRaises(assistant.AssistantError) as cm:
                assistant.stream_chat("ollama", "m", [], lambda t: None)
        self.assertIn("ollama.com", str(cm.exception))
        with self.assertRaises(assistant.AssistantError):
            assistant.stream_chat("openai", "m", [], lambda t: None)  # no key

    def test_model_lists(self):
        assistant.set_key("openai", "sk-" + "b" * 30)
        data = FakeResponse(json.dumps({"data": [
            {"id": "gpt-6.1-sol"}, {"id": "gpt-6-astra"}, {"id": "gpt-audio"},
            {"id": "text-embedding-3"}]}).encode())
        with mock.patch("urllib.request.urlopen", return_value=data):
            self.assertEqual(assistant.list_models("openai"), ["gpt-6.1-sol", "gpt-6-astra"])
        tags = FakeResponse(b'{"models":[{"name":"qwen2.5-coder:latest"}]}')
        with mock.patch("urllib.request.urlopen", return_value=tags):
            self.assertEqual(assistant.list_models("ollama"), ["qwen2.5-coder:latest"])


if __name__ == "__main__":
    unittest.main()
