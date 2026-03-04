"""💬 Interactive dialog tool for DevDuck.

Rich terminal UI dialogs: input, yes/no, radio, checkbox, forms,
file picker, progress bars, password input, and more.

Uses prompt_toolkit for beautiful terminal interfaces.

Examples:
    dialog(dialog_type="message", text="Hello!", title="Info")
    dialog(dialog_type="input", text="Your name?", title="Name")
    dialog(dialog_type="yes_no", text="Continue?", title="Confirm")
    dialog(dialog_type="radio", text="Pick one:", options=[["a", "Option A"], ["b", "Option B"]])
    dialog(dialog_type="checkbox", text="Select:", options=[["x", "X"], ["y", "Y"]])
    dialog(dialog_type="password", text="Enter password:")
    dialog(dialog_type="form", text="Fill out:", form_fields=[{"name": "email", "label": "Email"}])
"""

import asyncio
import json
import os
import re
from typing import Any, Dict, List, Optional

from strands import tool

# Style presets
STYLES = {
    "default": {
        "dialog": "bg:#f0f0f0",
        "dialog frame.label": "bg:#6688ff #ffffff",
        "dialog.body": "bg:#ffffff #000000",
        "button.focused": "bg:#6688ff #ffffff",
    },
    "dark": {
        "dialog": "bg:#333333",
        "dialog frame.label": "bg:#555555 #ffffff",
        "dialog.body": "bg:#222222 #ffffff",
        "button.focused": "bg:#555555 #ffffff",
    },
    "blue": {
        "dialog": "bg:#4444ff",
        "dialog frame.label": "bg:#6688ff #ffffff",
        "dialog.body": "bg:#ffffff #000000",
        "button.focused": "bg:#6688ff #ffffff",
    },
    "green": {
        "dialog": "bg:#286c3a",
        "dialog frame.label": "bg:#44aa55 #ffffff",
        "dialog.body": "bg:#ffffff #000000",
        "button.focused": "bg:#44aa55 #ffffff",
    },
    "purple": {
        "dialog": "bg:#6a2c70",
        "dialog frame.label": "bg:#9a4c90 #ffffff",
        "dialog.body": "bg:#ffffff #000000",
        "button.focused": "bg:#9a4c90 #ffffff",
    },
}


class _Validator:
    """Simple input validator."""

    def __init__(self, rules=None):
        if isinstance(rules, str):
            try:
                rules = json.loads(rules)
            except Exception:
                rules = {}
        self.rules = rules or {}

    def validate(self, document):
        from prompt_toolkit.validation import ValidationError

        text = document.text
        if self.rules.get("required") and not text.strip():
            raise ValidationError(message="Required field")
        min_len = self.rules.get("min_length")
        if min_len and len(text) < min_len:
            raise ValidationError(message=f"Min {min_len} chars")
        max_len = self.rules.get("max_length")
        if max_len and len(text) > max_len:
            raise ValidationError(message=f"Max {max_len} chars")
        pattern = self.rules.get("pattern")
        if pattern and not re.match(pattern, text):
            raise ValidationError(
                message=self.rules.get("error_message", "Invalid format")
            )


async def _run_dialog(
    dialog_type,
    title,
    text,
    options,
    style_name,
    default_value,
    validation,
    form_fields,
    progress_steps,
    step_delay,
    path_filter,
    multiline,
):
    from prompt_toolkit.shortcuts import (
        message_dialog,
        input_dialog,
        yes_no_dialog,
        radiolist_dialog,
        checkboxlist_dialog,
        button_dialog,
        ProgressBar,
    )
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import HTML

    style = Style.from_dict(STYLES.get(style_name, STYLES["default"]))
    validator = _Validator(validation) if validation else None

    if dialog_type == "message":
        await message_dialog(title=title, text=text, style=style).run_async()
        return {"acknowledged": True}

    elif dialog_type == "rich_message":
        await message_dialog(title=title, text=HTML(text), style=style).run_async()
        return {"acknowledged": True}

    elif dialog_type == "input":
        return await input_dialog(
            title=title,
            text=text,
            default=default_value or "",
            style=style,
            validator=validator,
        ).run_async()

    elif dialog_type == "password":
        from prompt_toolkit import prompt as pt_prompt

        return await pt_prompt(
            f"{text}\n", is_password=True, validator=validator, async_=True
        )

    elif dialog_type == "yes_no":
        return await yes_no_dialog(title=title, text=text, style=style).run_async()

    elif dialog_type == "radio":
        return await radiolist_dialog(
            title=title, text=text, values=options, style=style
        ).run_async()

    elif dialog_type == "checkbox":
        return await checkboxlist_dialog(
            title=title, text=text, values=options, style=style
        ).run_async()

    elif dialog_type == "buttons":
        return await button_dialog(
            title=title,
            text=text,
            buttons=[(label, value) for value, label in options],
            style=style,
        ).run_async()

    elif dialog_type == "autocomplete":
        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.completion import WordCompleter

        completer = WordCompleter([v for v, _ in options])
        return await pt_prompt(
            f"{text}\n", completer=completer, default=default_value or "", async_=True
        )

    elif dialog_type == "file":
        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.completion import PathCompleter

        ext = None
        if path_filter and "*." in path_filter:
            ext = path_filter.split("*.")[1]
        if ext:
            completer = PathCompleter(
                file_filter=lambda f: f.endswith(f".{ext}"), min_input_len=0
            )
        else:
            completer = PathCompleter(min_input_len=0)
        result = await pt_prompt(
            f"{text}\nPath: ",
            completer=completer,
            default=os.path.expanduser("~/"),
            async_=True,
        )
        return (
            os.path.expanduser(result) if result and result.startswith("~") else result
        )

    elif dialog_type == "progress":
        steps = progress_steps or 10
        delay = step_delay or 0.1
        with ProgressBar(title=title) as pb:
            for _ in pb(range(steps)):
                await asyncio.sleep(delay)
        return {"completed": True, "steps": steps}

    elif dialog_type == "form":
        from prompt_toolkit.application import Application, get_app
        from prompt_toolkit.layout import D, HSplit, Layout
        from prompt_toolkit.widgets import Button, Dialog as PTDialog, Label, TextArea

        if isinstance(form_fields, str):
            form_fields = json.loads(form_fields)

        controls = {}
        widgets = []
        for field in form_fields:
            if not isinstance(field, dict):
                continue
            name = field.get("name", "")
            label = field.get("label", name)
            ftype = field.get("type", "text")
            default = field.get("default", "")

            ctrl = TextArea(
                text=default,
                multiline=(ftype == "textarea"),
                height=D(min=2, max=5) if ftype == "textarea" else 1,
                password=(ftype == "password"),
            )
            controls[name] = ctrl
            widgets.extend([Label(f"{label}:"), ctrl])

        result_box = [None]

        def submit():
            result_box[0] = {n: c.text for n, c in controls.items()}
            get_app().exit(result=True)

        dlg = PTDialog(
            title=title,
            body=HSplit([Label(text)] + widgets),
            buttons=[
                Button("Submit", handler=submit),
                Button("Cancel", handler=lambda: get_app().exit(result=False)),
            ],
        )
        app = Application(
            layout=Layout(dlg), full_screen=False, style=style, mouse_support=True
        )
        ok = await app.run_async()
        return result_box[0] if ok else None

    else:
        raise ValueError(f"Unknown dialog type: {dialog_type}")


@tool
def dialog(
    dialog_type: str,
    text: str,
    title: str = "Dialog",
    options: Optional[List[List[str]]] = None,
    style: str = "default",
    default_value: Optional[str] = None,
    validation: Optional[Dict[str, Any]] = None,
    form_fields: Optional[List[Dict[str, Any]]] = None,
    progress_steps: Optional[int] = None,
    step_delay: Optional[float] = None,
    path_filter: Optional[str] = None,
    multiline: bool = False,
) -> Dict[str, Any]:
    """💬 Interactive terminal dialogs with rich UI.

    Args:
        dialog_type: Type of dialog:
            - message: Simple message box
            - rich_message: HTML-formatted message
            - input: Text input with optional validation
            - password: Masked password input
            - yes_no: Yes/No confirmation
            - radio: Single selection from options
            - checkbox: Multiple selection from options
            - buttons: Button selection
            - autocomplete: Input with autocomplete
            - file: File path picker
            - progress: Progress bar
            - form: Multi-field form
        text: Main text/question to display
        title: Dialog title
        options: Options as [value, label] pairs (for radio/checkbox/buttons/autocomplete)
        style: Theme (default, dark, blue, green, purple)
        default_value: Default input value
        validation: Validation rules: {required, min_length, max_length, pattern, error_message}
        form_fields: Form field definitions: [{name, label, type, default, validation}]
        progress_steps: Number of progress steps
        step_delay: Delay between progress steps (seconds)
        path_filter: File filter (e.g., "*.py")
        multiline: Allow multiline input

    Returns:
        Dict with status and dialog result
    """
    if os.environ.get("DEV", "").lower() == "true":
        return {
            "status": "success",
            "content": [{"text": "Dialog disabled in DEV mode."}],
        }

    try:
        # Format options
        fmt_options = []
        if options:
            for opt in options:
                if isinstance(opt, list) and len(opt) == 2:
                    fmt_options.append((opt[0], opt[1]))
                elif isinstance(opt, dict):
                    fmt_options.append((opt.get("value", ""), opt.get("label", "")))
                else:
                    fmt_options.append((str(opt), str(opt)))

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            _run_dialog(
                dialog_type,
                title,
                text,
                fmt_options,
                style,
                default_value,
                validation,
                form_fields,
                progress_steps,
                step_delay,
                path_filter,
                multiline,
            )
        )

        return {"status": "success", "content": [{"text": f"Dialog result: {result}"}]}

    except Exception as e:
        return {"status": "error", "content": [{"text": f"Dialog error: {e}"}]}
