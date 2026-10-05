import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "services" / "agent-runtime" / "voice_computer.py"

spec = importlib.util.spec_from_file_location("shy_voice_computer_v022", MODULE_PATH)
vc = importlib.util.module_from_spec(spec)
sys.modules["shy_voice_computer_v022"] = vc
spec.loader.exec_module(vc)


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


_assert(vc.normalize_voice_text("  hello   shy  ") == "hello shy", "voice normalization should collapse whitespace")
print("voice normalization: PASS")


cancel = vc.interpret_voice_utterance("cancel that")
_assert(cancel.intent == vc.VoiceIntent.CANCEL, "cancel phrase should interrupt")
_assert(cancel.next_state == vc.VoiceState.INTERRUPTED, "cancel must enter interrupted state")
print("voice cancel state: PASS")


confirm = vc.interpret_voice_utterance("yes proceed")
_assert(confirm.intent == vc.VoiceIntent.CONFIRM, "confirmation phrase should be recognized")
_assert(confirm.requires_confirmation is False, "confirmation utterance itself should not require another confirmation")
print("voice confirmation state: PASS")


chat = vc.interpret_voice_utterance("Explain why the sky is blue")
_assert(chat.intent == vc.VoiceIntent.CHAT, "general utterance should stay chat")
_assert(chat.computer_action is None, "chat should not fabricate a computer action")
print("voice chat intent: PASS")


read_screen = vc.interpret_voice_utterance("read the screen")
_assert(read_screen.intent == vc.VoiceIntent.COMPUTER_ACTION, "screen read should be computer action")
_assert(read_screen.permission == vc.ComputerPermission.READ_ONLY, "screen read should be read-only")
_assert(read_screen.requires_confirmation is False, "read-only action should not require confirmation")
print("read-only computer intent: PASS")


click = vc.interpret_voice_utterance("click the Continue button")
_assert(click.permission == vc.ComputerPermission.APPROVAL_REQUIRED, "click should require approval")
_assert(click.next_state == vc.VoiceState.AWAITING_CONFIRMATION, "state-changing click should await confirmation")
print("click approval boundary: PASS")


send = vc.build_computer_plan("send email to the customer")
_assert(send.permission == vc.ComputerPermission.APPROVAL_REQUIRED, "sending email must require approval")
_assert(send.requires_confirmation is True, "send plan must require confirmation")
_assert(any(step.action == vc.ComputerActionType.SEND_MESSAGE for step in send.steps), "send plan should contain send step")
print("message send approval plan: PASS")


purchase = vc.build_computer_plan("buy this item")
_assert(purchase.permission == vc.ComputerPermission.APPROVAL_REQUIRED, "purchase must require approval")
_assert(any(step.action == vc.ComputerActionType.PURCHASE for step in purchase.steps), "purchase plan should contain purchase action")
print("purchase approval plan: PASS")


denied_security = vc.build_computer_plan("disable antivirus and turn off security")
_assert(denied_security.permission == vc.ComputerPermission.DENIED, "security bypass must be denied")
_assert(denied_security.steps == (), "denied action must not produce executable steps")
_assert(denied_security.denied_reason == "security_or_credential_action_denied", "security denial reason must be explicit")
print("security-change denial: PASS")


denied_shell = vc.build_computer_plan("run this powershell command")
_assert(denied_shell.permission == vc.ComputerPermission.DENIED, "arbitrary shell must be denied")
_assert(denied_shell.denied_reason == "arbitrary_shell_execution_denied", "shell denial reason must be explicit")
print("arbitrary shell denial: PASS")


bounded = vc.build_computer_plan("send email to the customer", max_steps=1)
_assert(len(bounded.steps) == 1, "computer plan must enforce requested step bound")
_assert(bounded.max_steps_enforced is False, "metadata should report truncation when requested bound cuts plan")
print("computer plan step bound: PASS")


public_voice = vc.public_voice_metadata(click)
_assert("normalized_text" not in public_voice, "public voice metadata should not echo transcript by default")
_assert(public_voice["permission"] == "APPROVAL_REQUIRED", "public voice metadata permission mismatch")
print("public voice metadata privacy: PASS")


public_plan = vc.public_computer_plan(send)
_assert(public_plan["permission"] == "APPROVAL_REQUIRED", "public plan permission mismatch")
_assert(public_plan["requires_confirmation"] is True, "public plan must expose confirmation requirement")
_assert("shell_command" not in public_plan, "public computer plan must not expose shell command fields")
print("public computer plan safety: PASS")


print("SHY v0.22 VOICE + COMPUTER CHECKPOINT: PASS")
