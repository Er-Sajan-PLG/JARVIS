"""
Persistent Attachments Library.

This module backs the web app's "Attachments" feature: a user-facing library
where uploaded files live permanently (rather than only being held in the
browser until a single chat message is sent).

Design
------
* Files are stored on disk under ``<data_dir>/attachments/``. Each file gets a
  stable id and is written to ``<attachments_dir>/files/<id>__<safe_name>``.
  Metadata (original name, folder path, mtime, size, mime type) lives in a JSON
  index at ``<attachments_dir>/index.json``. Keeping the bytes and the metadata
  separate means we can rename / move files between folders cheaply (just edit
  the index) without touching the bytes.

* Folders are a virtual tree expressed in the metadata only. A folder is
  identified by its slash-delimited path, e.g. ``Physics/Quantum Mechanics``.
  There is no requirement that the on-disk layout mirror the folder tree — the
  tree is purely a tagging/drill-down affordance for the user. This keeps
  moves/renames O(1) and avoids the pain of nested filesystem directories.

* The whole index is small (just metadata), so we load it into memory and keep
  a single writer lock for mutations. This is plenty for a single-user local
  web app.

Public API
----------
* :class:`AttachmentStore` — the main entry point.
* Methods: ``list_tree``, ``create_folder``, ``rename_folder``, ``delete_folder``,
  ``list_files``, ``save_file``, ``get_file``, ``delete_file``, ``move_file``,
  ``search``.
"""

from __future__ import annotations

import json
import re
import shutil
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# Folders are stored as slash-delimited paths. This is the separator and the
# only character we forbid inside a single folder name (so paths stay
# unambiguous). We also forbid path-traversal tricks (".", "..").
_FORBIDDEN_NAME = re.compile(r"[\/]|^\.{1,2}$|[\x00-\x1f]")


def _now() -> float:
    return datetime.now(timezone.utc).timestamp()


def _normalize_folder(path: str) -> str:
    """Collapse empty / duplicate slashes and strip leading+trailing slashes.

    Raises ``ValueError`` if any segment is invalid (empty, ``.``, ``..`` or
    contains a forbidden character). Returns ``""`` for the root folder.
    """
    if path is None:
        return ""
    path = (path or "").strip().strip("/")
    if not path:
        return ""
    segments = [s for s in path.split("/") if s != ""]
    for seg in segments:
        if not seg or seg in (".", "..") or _FORBIDDEN_NAME.search(seg):
            raise ValueError(f"Invalid folder segment: {seg!r}")
    return "/".join(segments)


def _safe_filename(name: str) -> str:
    """Make a filename safe for on-disk storage (no path components)."""
    name = Path(name).name or "file"
    # Keep it readable but strip anything that could be sketchy.
    name = re.sub(r"[\x00-\x1f]", "_", name)
    if len(name) > 120:
        stem, ext = Path(name).stem, Path(name).suffix
        name = stem[: 120 - len(ext)] + ext
    return name or "file"


@dataclass
class FileMeta:
    id: str
    name: str               # original display name
    folder: str             # slash-delimited folder path ("" = root)
    size: int
    mime: str
    created_at: float
    updated_at: float
    storage_name: str       # on-disk filename under files/


@dataclass
class AttachmentStore:
    """Filesystem-backed store for the attachments library.

    Thread-safe for a single process. All mutating operations take a lock so
    concurrent web requests don't corrupt the JSON index.
    """

    attachments_dir: Path
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _index: dict = field(default=None, init=False)  # populated in __post_init__

    def __post_init__(self) -> None:
        self.attachments_dir = Path(self.attachments_dir)
        (self.attachments_dir / "files").mkdir(parents=True, exist_ok=True)
        self._index_path = self.attachments_dir / "index.json"
        self._index = self._load_index()

    # ------------------------------------------------------------------ index
    def _load_index(self) -> dict:
        if self._index_path.exists():
            try:
                data = json.loads(self._index_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "files" in data:
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        return {"version": 1, "files": {}}

    def _save_index(self) -> None:
        tmp = self._index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._index, indent=2), encoding="utf-8")
        # Atomic replace so a crash mid-write can't corrupt the index.
        shutil.move(str(tmp), str(self._index_path))

    # ----------------------------------------------------------------- folders
    def list_tree(self) -> list[dict]:
        """Return the folder tree with file counts per folder.

        Each node: ``{name, path, children: [...], file_count}``. The root is
        represented by a synthetic node with ``path == ""``.
        """
        tree: dict[str, dict] = {}
        counts: dict[str, int] = {}

        for fm in self._index["files"].values():
            folder = fm.get("folder", "") or ""
            counts[folder] = counts.get(folder, 0) + 1

        def _ensure(path: str) -> dict:
            if path == "":
                if "" not in tree:
                    tree[""] = {"name": "", "path": "", "children": {}, "file_count": counts.get("", 0)}
                return tree[""]
            if path in tree:
                return tree[path]
            parent = "/".join(path.split("/")[:-1])
            parent_node = _ensure(parent)
            node = {"name": path.split("/")[-1], "path": path,
                    "children": {}, "file_count": counts.get(path, 0)}
            parent_node["children"][node["name"]] = node
            tree[path] = node
            return node

        # Always materialize the root, even when there are no files yet.
        _ensure("")
        for path in counts:
            _ensure(path)
        return self._serialize_node(tree[""])

    def _serialize_node(self, node: dict) -> dict:
        children = [self._serialize_node(c) for c in sorted(
            node["children"].values(), key=lambda x: x["name"].lower())]
        return {
            "name": node["name"],
            "path": node["path"],
            "file_count": node.get("file_count", 0),
            "children": children,
        }

    def create_folder(self, path: str) -> dict:
        path = _normalize_folder(path)
        if not path:
            raise ValueError("Folder path cannot be empty")
        # Folders are virtual, so creation is a no-op if the path is already
        # implied by existing files; we just validate it. We still record it so
        # empty folders persist.
        with self._lock:
            self._index.setdefault("folders", {})
            self._index["folders"][path] = {
                "path": path,
                "created_at": _now(),
            }
            self._save_index()
        return {"ok": True, "path": path}

    def rename_folder(self, old_path: str, new_path: str) -> dict:
        old_path = _normalize_folder(old_path)
        new_path = _normalize_folder(new_path)
        if not old_path or not new_path:
            raise ValueError("Folder paths cannot be empty")
        if new_path == old_path:
            return {"ok": True, "path": new_path}
        with self._lock:
            # Re-parent every file whose folder == old_path or is a descendant.
            for fm in self._index["files"].values():
                f = fm.get("folder", "") or ""
                if f == old_path:
                    fm["folder"] = new_path
                elif f.startswith(old_path + "/"):
                    fm["folder"] = new_path + f[len(old_path):]
            # Re-point explicit folder records too.
            folders = self._index.setdefault("folders", {})
            new_folders = {}
            for p, meta in folders.items():
                if p == old_path:
                    new_folders[new_path] = meta
                elif p.startswith(old_path + "/"):
                    new_folders[new_path + p[len(old_path):]] = meta
                else:
                    new_folders[p] = meta
            self._index["folders"] = new_folders
            self._save_index()
        return {"ok": True, "path": new_path}

    def delete_folder(self, path: str, recursive: bool = False) -> dict:
        path = _normalize_folder(path)
        if not path:
            raise ValueError("Cannot delete the root folder")
        with self._lock:
            affected = [fm for fm in self._index["files"].values()
                        if (fm.get("folder", "") or "") == path
                        or (fm.get("folder", "") or "").startswith(path + "/")]
            if affected and not recursive:
                raise ValueError(
                    "Folder is not empty. Pass recursive=true to delete its files too.")
            for fm in affected:
                self._delete_file_bytes(fm)
                self._index["files"].pop(fm["id"], None)
            folders = self._index.setdefault("folders", {})
            self._index["folders"] = {
                p: m for p, m in folders.items()
                if p != path and not p.startswith(path + "/")
            }
            self._save_index()
        return {"ok": True, "deleted_files": len(affected)}

    # ------------------------------------------------------------------ files
    def list_files(self, folder: Optional[str] = None) -> list[dict]:
        folder = _normalize_folder(folder or "")
        out = []
        for fm in self._index["files"].values():
            f = fm.get("folder", "") or ""
            if folder == "" and f == "":
                out.append(self._public_file(fm))
            elif folder and (f == folder or f.startswith(folder + "/")):
                # Only direct children of the requested folder (or all if we
                # want the whole subtree). We expose direct children here; the
                # UI drills down via folder navigation.
                if f == folder:
                    out.append(self._public_file(fm))
        out.sort(key=lambda x: (x["name"].lower()))
        return out

    def save_file(self, raw: bytes, name: str, folder: str = "",
                  mime: str = "application/octet-stream") -> dict:
        folder = _normalize_folder(folder or "")
        safe = _safe_filename(name)
        fid = uuid.uuid4().hex
        storage_name = f"{fid}__{safe}"
        (self.attachments_dir / "files" / storage_name).write_bytes(raw)
        now = _now()
        with self._lock:
            self._index["files"][fid] = asdict(FileMeta(
                id=fid, name=name, folder=folder, size=len(raw),
                mime=mime, created_at=now, updated_at=now,
                storage_name=storage_name,
            ))
            self._save_index()
        return self._public_file(self._index["files"][fid])

    def get_file(self, file_id: str) -> Optional[FileMeta]:
        fm = self._index["files"].get(file_id)
        if not fm:
            return None
        return FileMeta(**fm)

    def read_file(self, file_id: str) -> tuple[bytes, FileMeta]:
        fm = self.get_file(file_id)
        if not fm:
            raise FileNotFoundError(file_id)
        data = (self.attachments_dir / "files" / fm.storage_name).read_bytes()
        return data, fm

    def delete_file(self, file_id: str) -> dict:
        with self._lock:
            fm = self._index["files"].pop(file_id, None)
            if not fm:
                raise FileNotFoundError(file_id)
            self._delete_file_bytes(fm)
            self._save_index()
        return {"ok": True, "id": file_id}

    def _delete_file_bytes(self, fm: dict) -> None:
        p = self.attachments_dir / "files" / fm["storage_name"]
        try:
            p.unlink()
        except OSError:
            pass

    def move_file(self, file_id: str, folder: str) -> dict:
        folder = _normalize_folder(folder or "")
        with self._lock:
            fm = self._index["files"].get(file_id)
            if not fm:
                raise FileNotFoundError(file_id)
            fm["folder"] = folder
            fm["updated_at"] = _now()
            self._save_index()
        return self._public_file(fm)

    def search(self, query: str) -> list[dict]:
        q = (query or "").strip().lower()
        if not q:
            return self.list_files()
        out = []
        for fm in self._index["files"].values():
            hay = f"{fm.get('name','')} {fm.get('folder','')}".lower()
            if q in hay:
                out.append(self._public_file(fm))
        out.sort(key=lambda x: x["name"].lower())
        return out

    # --------------------------------------------------------------- helpers
    def _public_file(self, fm: dict) -> dict:
        return {
            "id": fm["id"],
            "name": fm["name"],
            "folder": fm.get("folder", "") or "",
            "size": fm.get("size", 0),
            "mime": fm.get("mime", "application/octet-stream"),
            "updated_at": fm.get("updated_at", 0),
        }

