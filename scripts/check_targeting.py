"""Replay targeting mistakes without opening apps, using the microphone, or calling the cloud.
Run: .venv\\Scripts\\python scripts/check_targeting.py
"""
import sys
import json
import types
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from turo.sense import screen
from turo.ai import brain


def item(n, name, rect, kind="MenuItem"):
    return {"id": n, "name": name, "type": kind, "rect": rect}


def menu_description():
    rows = [item(1, "Connectors", (250, 210, 520, 235)),
            item(2, "Slash commands", (250, 185, 520, 210))]
    with patch.object(screen, "_clickable_at", return_value=(rows[1]["rect"], rows[1]["name"])):
        assert screen.snap(259, 200, "Connectors option in dropdown", rows) == (rows[0]["rect"], "Connectors")


def singular_label():
    rows = [item(1, "Connectors", (250, 210, 520, 235))]
    with patch.object(screen, "_clickable_at", return_value=None):
        assert screen.snap(259, 200, "connector", rows) == (rows[0]["rect"], "Connectors")


def wrong_neighbor():
    with patch.object(screen, "_clickable_at", return_value=((250, 185, 520, 210), "Slash commands")):
        rect, _ = screen.snap(259, 200, "Connectors", [])
        assert rect is None, "Unrelated control must not become the requested target"


def distant_tab():
    rows = [item(1, "View", (1000, 0, 1100, 30), "TabItem")]
    with patch.object(screen, "_clickable_at", return_value=None):
        assert screen.snap(10, 10, "View", rows)[0] is None, "Do not teleport to a distant same-named tab"


def disabled_hidden():
    class Rect:
        left, top, right, bottom = 0, 0, 100, 30
        def width(self): return 100
        def height(self): return 30
    class Control:
        ControlTypeName = "ButtonControl"
        BoundingRectangle = Rect()
        def __init__(self, name, hidden=False, enabled=True, children=()):
            self.Name, self.IsOffscreen, self.IsEnabled = name, hidden, enabled
            self.children = children
        def GetChildren(self): return self.children
    root = Control("root", children=[Control("Hidden", hidden=True), Control("Disabled", enabled=False),
                                    Control("Visible")])
    rows = []
    screen._walk(root, 0, rows, 120, 16)
    assert [r["name"] for r in rows] == ["Visible"], "Only visible enabled controls are candidates"


def invalid_boxes_and_ids():
    rows = [item(1, "Connectors", (250, 210, 520, 235))]
    for box in ([90, 30, 20, 10], [10, 20, 10, 40], [-1, 0, 30, 40], [0, 0, 1001, 20]):
        with patch.object(brain, "_chat", return_value=json.dumps({"action":"click", "bbox_2d":box,
                                                                 "label":"Connectors", "control_id":999})):
            reply = brain.locate("Open connectors", "Claude", "fixture", [], items=rows, viewport=(0,0,800,600))
        assert reply["point"] is None and reply["box"] is None and reply["control_id"] is None


def icon_opener():
    rows = [item(1, "Add files or photos", (405, 130, 430, 158), "Button")]
    with patch.object(screen, "_clickable_at", return_value=None):
        rect, name, verified = screen.resolve_target(418,143,"+",rows,control_id=1)
        assert rect == rows[0]["rect"] and name == rows[0]["name"] and verified


def visual_estimate():
    with patch.object(screen, "_clickable_at", return_value=None):
        rect, name, verified = screen.resolve_target(100,100,"Canvas action",[],box=(90,90,110,110))
        assert rect == (90,90,110,110) and not verified


def full_tutor_replay():
    # Substitute only runtime services: use the real compute_step -> model parser -> resolver chain.
    # Avoid session.py's microphone/model startup and any live desktop interaction.
    from unittest.mock import MagicMock
    fake = types.ModuleType("turo.session")
    for name in ("bridge", "busy", "open_follow_up", "say_and_show", "user32"):
        setattr(fake, name, MagicMock())
    fake.speak = fake.voice = None
    fake.state = {"hwnd":123,"question":"Open connectors","context":"","history":[],
                  "recalled":"unset","path":[],"app":""}
    with patch.dict(sys.modules, {"turo.session":fake}):
        import importlib
        tutor = importlib.import_module("turo.tutor")
    rows = [item(1,"Connectors",(250,210,520,235)), item(2,"Slash commands",(250,185,520,210))]
    response = {"action":"click","bbox_2d":[310,315,338,352], "label":"Connectors option in dropdown",
                "say":"Click Connectors.", "done":False}
    with patch.object(screen,"list_controls",return_value=("Claude",rows)), \
         patch.object(screen,"exe_of",return_value="claude.exe"), \
         patch.object(screen,"grab",return_value=("fixture",(0,0,800,600))), \
         patch.object(screen,"_clickable_at",return_value=(rows[1]["rect"],"Slash commands")), \
         patch.object(tutor.memory,"recall",return_value=None), \
         patch.object(tutor.time,"sleep"), patch.object(brain,"_chat",return_value=json.dumps(response)) as chat:
        step = tutor.compute_step()
        assert step["rect"] == rows[0]["rect"] and step["label"] == "Connectors" and step["verified"]
        assert "Visible controls" in str(chat.call_args) and "Connectors" in str(chat.call_args)
    # Agent mode must never click an unverified model box.
    fake.state.update(stop=False, history=[])
    tentative = dict(step, verified=False)
    with patch.object(tutor,"compute_step",return_value=tentative), patch.object(tutor,"present"), \
         patch.object(tutor.auto,"UIAutomationInitializerInThread"), patch.object(tutor.auto,"Click") as click:
        tutor.run_agent()
        click.assert_not_called()
    # Even a previously verified control must be checked again after the animation delay.
    with patch.object(tutor,"compute_step",return_value=step), patch.object(tutor,"present"), \
         patch.object(tutor.time,"sleep"), patch.object(screen,"verify_target",return_value=False), \
         patch.object(tutor.auto,"UIAutomationInitializerInThread"), patch.object(tutor.auto,"Click") as click:
        tutor.run_agent()
        click.assert_not_called()


def duplicate_memory_names():
    rows = [item(1,"Connectors",(250,210,520,235)), item(2,"Connectors",(700,500,800,530))]
    assert screen.find_named("Connectors",rows) is None


def truncated_window_scan():
    # Browser/Electron scans can hit MAX_ITEMS before reaching the composer menu.
    rows = [item(1,"Connectors",(250,210,520,235)), item(2,"Slash commands",(250,185,520,210))]
    with patch.object(screen,"_nearby_controls",return_value=rows), \
         patch.object(screen,"_clickable_at",return_value=(rows[1]["rect"],"Slash commands")):
        rect, name, verified = screen.resolve_target(259,200,"Connectors option in dropdown",[])
        assert verified and rect == rows[0]["rect"] and name == "Connectors"


def valid_id_without_box():
    rows = [item(7,"Connectors",(250,210,520,235))]
    with patch.object(brain,"_chat",return_value='{"control_id":7,"label":"Connectors"}'):
        reply = brain.locate("Open connectors","Claude","fixture",[],items=rows,viewport=(0,0,800,600))
    assert reply["control_id"] == 7 and reply["action"] == "click" and reply["point"] is None


def bounded_candidates():
    rows = [item(n,f"Button {n}",(n,10,n+1,20),"Button") for n in range(1,121)]
    with patch.object(brain,"_chat",return_value='{"action":"click","control_id":60,"label":"Button 60"}') as chat:
        reply = brain.locate("Open a menu","App","fixture",[],items=rows,viewport=(0,0,800,600))
    text = chat.call_args.args[1][1]["text"]
    assert len(text.split("Visible controls (ID | type | exact name | bbox_2d):\n")[1].splitlines()) == 40
    assert reply["control_id"] is None, "An ID not shown to the model cannot override coordinates"


def _fake_session_import(name):
    from unittest.mock import MagicMock
    import importlib
    fake = types.ModuleType("turo.session")
    for attr in ("bridge", "busy", "open_follow_up", "say_and_show", "user32"):
        setattr(fake, attr, MagicMock())
    fake.speak = fake.voice = None
    fake.state = {}
    with patch.dict(sys.modules, {"turo.session": fake}):
        for mod in ("turo.tutor", "turo.commands", "turo.hotkeys"):   # all bound to turo.session at import
            sys.modules.pop(mod, None)
        return importlib.import_module(name), fake


def repeat_guard():
    # Logged loop: user clicked "New", said "I already did that", and the model pointed to "New" again.
    tutor, fake = _fake_session_import("turo.tutor")
    fake.state.update(hwnd=1, question="How do I use connectors?", context="", history=["Click New."],
                      recalled=None, path=[], app="", last_label="New")
    rows = [item(1, "New", (0, 70, 140, 96), "Button"), item(2, "Add files or connectors", (700, 990, 730, 1010), "Button")]
    replies = [{"action": "click", "control_id": 1, "label": "New", "say": "Click New."},
               {"action": "click", "control_id": 2, "label": "Add files or connectors", "say": "Click +."}]
    with patch.object(screen, "list_controls", return_value=("Claude", rows)), \
         patch.object(screen, "exe_of", return_value="claude.exe"), \
         patch.object(screen, "grab", return_value=("fixture", (0, 0, 1920, 1080))), \
         patch.object(screen, "_clickable_at", return_value=None), patch.object(tutor.time, "sleep"), \
         patch.object(brain, "_chat", side_effect=[json.dumps(r) for r in replies]) as chat:
        step = tutor.compute_step()
    assert chat.call_count == 2 and 'already clicked "New"' in chat.call_args.args[1][1]["text"]
    assert step["label"] == "Add files or connectors"


def follow_up_routing():
    commands, fake = _fake_session_import("turo.commands")
    fake.state.update(question="How do I use connectors?", last=None)
    with patch.object(commands, "tutor") as tutor, patch.object(commands.auto, "GetForegroundWindow"):
        for text in ("Okay, I already clicked that one", "I already did that", "It's not there"):
            commands.handle_speech(text, follow_up=True)
        assert tutor.add_remark.call_count == 3 and not tutor.new_question.called
        commands.handle_speech("What next?", follow_up=True)
        assert tutor.start_step.called
        commands.handle_speech("How do I add a new folder?", follow_up=True)
        assert tutor.new_question.called


def talk_tap_and_hold():
    hotkeys, fake = _fake_session_import("turo.hotkeys")
    from unittest.mock import MagicMock
    fake.voice = hotkeys.voice = MagicMock()
    hotkeys.voice.stop_and_transcribe.return_value = "How do I freeze the top row?"
    fake.state.update(talking=False, gen=0, active=False)
    clock = [100.0]
    with patch.object(hotkeys, "tutor"), patch.object(hotkeys, "brain"), patch.object(hotkeys.auto, "GetForegroundWindow"),          patch.object(hotkeys.time, "time", side_effect=lambda: clock[0]),          patch.object(hotkeys.threading, "Thread", side_effect=lambda target, daemon: MagicMock(start=target)),          patch.object(hotkeys, "handle_speech") as heard:
        hotkeys.talk_press(); clock[0] += 0.1; hotkeys.talk_release()   # tap: keep listening
        assert hotkeys.voice.hands_free.called and fake.state["talking"] and not heard.called
        hotkeys.talk_press(); hotkeys.talk_release()   # second tap ends it; its release is ignored
        assert heard.call_count == 1 and not fake.state["talking"]
        hotkeys.talk_press(); clock[0] += 1.0; hotkeys.talk_release()   # hold: ends on release
        assert heard.call_count == 2 and hotkeys.voice.hands_free.call_count == 1


def act_and_yes_routing():
    commands, fake = _fake_session_import("turo.commands")
    fake.state.update(question="", last=None, offered=False)
    with patch.object(commands, "tutor") as tutor, patch.object(commands.auto, "GetForegroundWindow"):
        commands.handle_speech("Open connectors for me")
        assert tutor.new_question.call_args.kwargs["mode"] == "do"
        commands.handle_speech("Can you show me how to add a folder?")
        assert tutor.new_question.call_args.kwargs["mode"] == "teach"
        commands.handle_speech("Turn on dark mode")
        assert tutor.new_question.call_args.kwargs["mode"] == "offer"
        commands.handle_speech("Hi Turo, how do I freeze the top row?")
        assert tutor.new_question.call_args.args[0] == "how do I freeze the top row?"
        commands.handle_speech("Yes")
        assert not tutor.start_agent.called, "yes without an offer does nothing"
        fake.state["offered"] = True
        commands.handle_speech("Yes please")
        assert tutor.start_agent.called


def offer_once_when_safe():
    tutor, fake = _fake_session_import("turo.tutor")
    fake.state.update(asked=False, offered=False, mode="teach")
    safe = {"rect": (0, 0, 9, 9), "verified": True, "action": "click", "label": "Freeze Panes"}
    tutor.offer(safe)
    assert not fake.state["asked"], "a how-to question is taught, not offered"
    fake.state["mode"] = "offer"
    safe = {"rect": (0, 0, 9, 9), "verified": True, "action": "click", "label": "Freeze Panes"}
    tutor.offer(dict(safe, label="Delete sheet"))
    assert not fake.state["asked"], "never offer a risky click"
    tutor.offer(dict(safe, verified=False))
    assert not fake.state["asked"], "never offer an unverified box"
    tutor.offer(safe)
    assert not fake.state["asked"], "instructions only: Turo never offers to click"


def greetings_and_noise():
    commands, fake = _fake_session_import("turo.commands")
    fake.state.update(question="", last=None, offered=False)
    with patch.object(commands, "tutor") as tutor, patch.object(commands, "ask_back") as ask_back, \
         patch.object(commands, "say_and_show") as said:
        for text in ("Hi Turo", "Hi to the", "Hello!", "Hey Toro."):   # Parakeet's versions of "Hi Turo"
            commands.handle_speech(text)
        assert ask_back.call_count == 4 and not tutor.new_question.called
        commands.handle_speech("Relevant")
        assert ask_back.call_count == 5 and not tutor.new_question.called
        commands.handle_speech("Thank you Turo")
        assert "welcome" in said.call_args.args[1] and not tutor.new_question.called


if __name__ == "__main__":
    checks = [menu_description, singular_label, wrong_neighbor, distant_tab, disabled_hidden,
              invalid_boxes_and_ids, icon_opener, visual_estimate, duplicate_memory_names,
              truncated_window_scan, valid_id_without_box, bounded_candidates, full_tutor_replay,
              repeat_guard, follow_up_routing, talk_tap_and_hold, act_and_yes_routing, offer_once_when_safe,
              greetings_and_noise]
    failures = []
    for check in checks:
        try:
            with patch.object(screen.auto,"ControlFromPoint",return_value=None):
                check()
            print("PASS", check.__name__)
        except AssertionError as err:
            failures.append(check.__name__)
            print("FAIL", check.__name__, str(err))
    print(f"{len(checks) - len(failures)}/{len(checks)} passed")
    sys.exit(bool(failures))
