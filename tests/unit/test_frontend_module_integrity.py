"""Resolve every identifier a frontend module calls against what it imports.

This catches the `applyDefaultToChat is not defined` class of bug: a function
that exists elsewhere but was never imported into the module that calls it.
A plain "does the file parse" check cannot see it, because the reference is
only resolved at call time.

Comment and string bodies are stripped first — prose contains things like
"Not Connected (" that look like calls but are not code.
"""

from __future__ import annotations

import re
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[2] / "frontend" / "assets"

MODULES = ["core.js", "picker.js", "settings.js", "chat.js", "main.js"]


def read(name: str) -> str:
    return (ASSETS / name).read_text()


def strip_comments_and_strings(src: str) -> str:
    """Remove comments and string/template/regex literals so prose never parses."""
    out = []
    i = 0
    n = len(src)
    # Tracks whether a `/` here starts a regex literal rather than division:
    # a regex can only follow an operator, opening bracket, comma, or keyword.
    prev_sig = ""

    def regex_allowed() -> bool:
        return prev_sig == "" or prev_sig in "([{,;:!&|?=+-*%~^<>"

    while i < n:
        ch = src[i]
        two = src[i:i + 2]
        # line comment
        if two == "//":
            j = src.find("\n", i)
            i = n if j == -1 else j
            continue
        # block comment
        if two == "/*":
            j = src.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        # regex literal: /pattern/flags
        if ch == "/" and regex_allowed():
            j = i + 1
            in_class = False
            while j < n:
                c = src[j]
                if c == "\\":
                    j += 2
                    continue
                if c == "[":
                    in_class = True
                elif c == "]":
                    in_class = False
                elif c == "/" and not in_class or c == "\n":
                    break
                j += 1
            if j < n and src[j] == "/":
                j += 1
                while j < n and src[j].isalpha():
                    j += 1
                out.append(" ")  # regex collapses to a token separator
                i = j
                prev_sig = ")"
                continue
        # string / template literal
        if ch in "'\"`":
            quote = ch
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == quote:
                    i += 1
                    break
                # template interpolation: keep the ${...} expression
                if quote == "`" and src[i:i + 2] == "${":
                    depth = 1
                    i += 2
                    start = i
                    while i < n and depth:
                        if src[i] == "{":
                            depth += 1
                        elif src[i] == "}":
                            depth -= 1
                        i += 1
                    out.append(src[start:i - 1])
                    continue
                i += 1
            out.append('""')
            prev_sig = '"'
            continue
        out.append(ch)
        if not ch.isspace():
            prev_sig = ch
        i += 1
    return "".join(out)


def imported_names(src: str) -> set[str]:
    """Names bound by import statements, including aliases. [\\s\\S] spans lines."""
    names: set[str] = set()
    for block in re.findall(r"import\s*\{([\s\S]*?)\}\s*from", src):
        for part in block.split(","):
            part = part.strip()
            if not part:
                continue
            names.add(part.split(" as ")[-1].strip() if " as " in part else part)
    for m in re.finditer(r"import\s+(\*\s+as\s+\w+|\w+)\s+from", src):
        names.add(m.group(1).split()[-1])
    return names


def declared_names(src: str) -> set[str]:
    """Top-level functions, consts, lets, classes, and exported aliases."""
    names: set[str] = set()
    names |= set(re.findall(r"^\s*export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", src, re.M))
    names |= set(re.findall(r"^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", src, re.M))
    names |= set(re.findall(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)", src, re.M))
    names |= set(re.findall(r"\bclass\s+([A-Za-z_$][\w$]*)", src))
    for block in re.findall(r"export\s*\{([\s\S]*?)\}", src):
        for part in block.split(","):
            part = part.strip()
            if not part:
                continue
            names.add(part.split(" as ")[-1].strip() if " as " in part else part)
    return names


# Identifiers available without any import.
GLOBAL_OK = {
    "console", "window", "document", "globalThis", "Math", "JSON", "Object",
    "Array", "String", "Number", "Boolean", "Date", "Set", "Map", "Promise",
    "Error", "TypeError", "RegExp", "URLSearchParams", "URL", "fetch",
    "setTimeout", "clearTimeout", "setInterval", "clearInterval", "queueMicrotask",
    "requestAnimationFrame", "confirm", "alert", "prompt", "parseInt", "parseFloat",
    "isNaN", "isFinite", "encodeURIComponent", "decodeURIComponent",
    "localStorage", "sessionStorage", "crypto", "FormData", "File", "Blob",
    "FileReader", "AbortController", "Intl", "Symbol", "BigInt", "WeakMap",
    "WeakSet", "Proxy", "Reflect", "import", "super", "this", "new", "typeof",
    "await", "async", "function", "if", "for", "while", "switch", "catch",
    "return", "delete", "void", "in", "of", "do", "else", "case", "try",
    "throw", "yield", "class", "extends", "default", "from", "as", "const",
    "let", "var", "true", "false", "null", "undefined", "NaN", "Infinity",
    # Common array/string builtins used as bare calls are impossible, but
    # local shims in the test harness may define these.
    "setImmediate", "structuredClone", "atob", "btoa",
}


def local_bindings(src: str) -> set[str]:
    """Parameters, destructured bindings, and any locally-declared name."""
    names: set[str] = set()
    for params in re.findall(r"function\s*\w*\s*\(([^)]*)\)", src):
        for p in params.split(","):
            p = p.strip().split("=")[0].strip().lstrip(".")
            if re.fullmatch(r"[A-Za-z_$][\w$]*", p):
                names.add(p)
    for params in re.findall(r"\(([^)]*)\)\s*=>", src):
        for p in params.split(","):
            p = p.strip().split("=")[0].strip().lstrip(".")
            if re.fullmatch(r"[A-Za-z_$][\w$]*", p):
                names.add(p)
    # single-param arrow without parens
    names |= set(re.findall(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*=>", src))
    # destructured params/declarations: { a, b: c }, [x, y]
    for block in re.findall(r"\{([^{}]*)\}\s*=", src) + re.findall(r"\(([^()]*)\)", src):
        for part in re.split(r"[,\s]+", block):
            part = part.strip().split(":")[-1].strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", part):
                names.add(part)
    names |= set(re.findall(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)", src))
    names |= set(re.findall(r"\bcatch\s*\(\s*(\w+)", src))
    names |= set(re.findall(r"\bfor\s*\(\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)", src))
    return names


def called_names(src: str) -> set[str]:
    """Identifiers used in a call position: `foo(` — excluding method calls."""
    out: set[str] = set()
    for m in re.finditer(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(", src):
        name = m.group(1)
        if name in {"function", "if", "for", "while", "switch", "catch", "return",
                    "typeof", "new", "await", "async", "of", "in", "do", "else",
                    "yield", "delete", "void", "case", "throw"}:
            continue
        out.add(name)
    return out


def test_no_undefined_callees():
    """Every called identifier must be imported, declared, or global."""
    problems: list[str] = []

    for name in MODULES:
        src = strip_comments_and_strings(read(name))
        available = (
            imported_names(src)
            | declared_names(src)
            | local_bindings(src)
            | GLOBAL_OK
        )
        for callee in sorted(called_names(src)):
            if callee in available:
                continue
            problems.append(f"{name}: calls `{callee}` but never imports or declares it")

    assert not problems, "undefined callees:\n" + "\n".join(problems)


def test_settings_imports_apply_default_to_chat():
    """Regression: settings.js calls applyDefaultToChat in every set-default
    handler, so it must import it from chat.js."""
    settings_src = read("settings.js")
    chat_src = read("chat.js")
    assert "export function applyDefaultToChat" in chat_src
    assert "applyDefaultToChat()" in settings_src
    assert re.search(
        r"import\s*\{[\s\S]*?applyDefaultToChat[\s\S]*?\}\s*from\s*['\"]\./chat\.js['\"]",
        settings_src,
    ), "settings.js must import applyDefaultToChat from ./chat.js"


def test_chat_does_not_statically_import_settings():
    """settings.js imports applyDefaultToChat from chat.js, so chat.js must
    reach settings.js lazily (dynamic import) to avoid a load-order cycle."""
    chat = read("chat.js")
    assert not re.search(r"^import[\s\S]*?from\s*['\"]\./settings\.js['\"]", chat, re.M), (
        "chat.js must not statically import settings.js — use a dynamic import"
    )
    assert "import('./settings.js')" in chat, (
        "chat.js should open settings via a dynamic import"
    )


def test_capability_registry_shape():
    """The capability list drives both the picker filters and the add-model
    form; every entry needs key/label/icon and a unique key."""
    src = read("core.js")
    assert "ALL_CAPABILITIES" in src
    assert "export const ALL_CAPABILITIES" in src, "ALL_CAPABILITIES must be exported"
    keys = re.findall(r"key:\s*'([a-z-]+)'", src)
    assert keys, "ALL_CAPABILITIES entries need string keys"
    assert len(keys) == len(set(keys)), f"duplicate capability keys: {keys}"
    for expected in ("text", "vision", "reasoning", "code", "tools"):
        assert expected in keys, f"capability `{expected}` missing"


def test_custom_model_form_collects_context_and_capabilities():
    """The add-model dialog must offer a context window and capability tags."""
    html = (ASSETS.parent / "index.html").read_text()
    assert 'id="addModelContext"' in html, "add-model form needs a context window input"
    assert 'id="addModelCaps"' in html, "add-model form needs a capability chip host"

    settings_src = read("settings.js")
    assert "pendingModelCaps" in settings_src
    assert "capabilities: [...pendingModelCaps]" in settings_src, (
        "submitting a custom model must send the ticked capabilities"
    )
    assert "context_length:" in settings_src


def test_chat_request_has_a_timeout_and_aborts_cleanly():
    """A slow provider must not hang the UI forever.

    The AGY CLI takes 30-45s for a one-word reply; without a ceiling the
    frontend waits indefinitely and a slow model is indistinguishable from a
    hung one.
    """
    src = read("core.js")
    assert "CHAT_TIMEOUT_MS" in src, "chat needs a timeout constant"
    assert "AbortController" in src, "the timeout must actually abort the request"
    assert "controller.abort()" in src
    assert "AbortError" in src, "an abort must be reported as a readable error"

    # The chat call must use the long chat timeout, not the 30s default.
    assert "timeoutMs: CHAT_TIMEOUT_MS" in src, "api.chat must pass the chat timeout"
    m = re.search(r"CHAT_TIMEOUT_MS\s*=\s*(\d+)", src)
    assert m and int(m.group(1)) >= 120000, "chat timeout must accommodate agentic providers"


def test_slow_replies_show_elapsed_progress():
    """A long wait must look like progress, not a freeze."""
    src = read("chat.js")
    assert "onProgress" in src, "sendMessage must pass a progress callback"
    assert "pending-label" in src, "the pending bubble needs an updatable label"
    core = read("core.js")
    assert "onProgress" in core, "the API client must support progress reporting"
    assert "setInterval" in core, "progress must tick while the request is in flight"
