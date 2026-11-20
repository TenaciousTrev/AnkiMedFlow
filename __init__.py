import html
import json
import os
import re
import tempfile
import time
from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo, tooltip, askUser

from . import numbering
from anki.hooks import addHook

try:
    from aqt.theme import theme_manager
except Exception:  # very old Anki
    theme_manager = None


def _night_mode():
    return bool(getattr(theme_manager, "night_mode", False))

try:  # Anki 2.1.50+ (PyQt6)
    from PyQt6.QtWebEngineCore import QWebEnginePage
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except ImportError:  # older Anki (PyQt5)
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

# ==========================================
# PART 1: CONSTANTS
# ==========================================

ADDON_NAME = "MedFlow"
MODEL_NAME = "MedFlow"
EDITOR_FILE = "medflow_editor.html"
BRIDGE_PREFIX = "__medflow__:"
SHARED_JS_TOKEN = "/*MF_SHARED*/"
CONFIG_TOKEN = "/*MF_CONFIG*/ null"

# ==========================================
# PART 1b: SETTINGS (config.json, edited through Tools > MedFlow settings)
# ==========================================
DEFAULT_CONFIG = {"arrow_style": "straight", "card_view": "path", "hint_bubbles": True, "extra_markers": True,
                  "toolbar_layout": "scroll"}
CONFIG_CHOICES = {"arrow_style": ("straight", "curved"), "card_view": ("path", "full"),
                  "hint_bubbles": (True, False), "extra_markers": (True, False),
                  "toolbar_layout": ("scroll", "wrap", "float")}


def _addon_module():
    return mw.addonManager.addonFromModule(__name__)


def get_config():
    try:
        conf = mw.addonManager.getConfig(_addon_module()) or {}
    except Exception:
        conf = {}
    out = dict(DEFAULT_CONFIG)
    for key, choices in CONFIG_CHOICES.items():
        if conf.get(key) in choices:
            out[key] = conf[key]
    return out


def save_config(conf):
    full = mw.addonManager.getConfig(_addon_module()) or {}
    full.update(conf)
    mw.addonManager.writeConfig(_addon_module(), full)

# ==========================================
# PART 2: NOTE TYPE INSTALLER
# ==========================================
def _read_addon_file(filename):
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _load_card_templates():
    """Returns (front, back). The shared rendering JS is injected into both templates."""
    source = _read_addon_file("card_templates.html")

    def extract(start_marker, end_marker):
        start = source.index(start_marker) + len(start_marker)
        end = source.index(end_marker, start)
        return source[start:end].strip()

    shared = extract("<!-- SHARED_JS_START -->", "<!-- SHARED_JS_END -->")
    # The settings are baked into the templates, so cards render the same on phones and AnkiWeb.
    # A flat dict of short strings: its JSON can never contain two curly braces in a row.
    shared = shared.replace(CONFIG_TOKEN, json.dumps(get_config()))
    front = extract("<!-- FRONT_TEMPLATE_START -->", "<!-- FRONT_TEMPLATE_END -->").replace(SHARED_JS_TOKEN, shared)
    back = extract("<!-- BACK_TEMPLATE_START -->", "<!-- BACK_TEMPLATE_END -->").replace(SHARED_JS_TOKEN, shared)
    return front, back


def install_model():
    css = _read_addon_file("style.css")
    front, back = _load_card_templates()
    m = mw.col.models.by_name(MODEL_NAME)

    if not m:
        mm = mw.col.models.new(MODEL_NAME)
        mm['type'] = 1  # cloze
        mw.col.models.add_field(mm, mw.col.models.new_field("Text"))
        mw.col.models.add_field(mm, mw.col.models.new_field("Algorithm_JSON"))
        mw.col.models.add_field(mm, mw.col.models.new_field("Extra"))
        mm['css'] = css
        t = mw.col.models.new_template("Card 1")
        t['qfmt'] = front
        t['afmt'] = back
        mw.col.models.add_template(mm, t)
        mw.col.models.add(mm)
        return

    # Existing note type: refresh it from the add-on files, but only save when something changed.
    changed = False
    if m.get('css') != css:
        m['css'] = css
        changed = True
    tmpls = m['tmpls']
    if tmpls and (tmpls[0]['qfmt'] != front or tmpls[0]['afmt'] != back):
        tmpls[0]['qfmt'] = front
        tmpls[0]['afmt'] = back
        changed = True
    if changed:
        mw.col.models.save(m)

addHook("profileLoaded", install_model)

# ==========================================
# PART 3: ADD-ON LOGIC
# ==========================================

# ---- Embedded editor window -------------------------------------------------

_open_windows = []  # keeps references so the windows are not garbage collected

# < > & are written as \\uXXXX escapes (still valid JSON): Anki's field editor treats the field as HTML and
# would otherwise mangle the formatting tags stored inside the JSON.
GET_DATA_JS = r"""(typeof syncHeights === 'function' && syncHeights(), JSON.stringify({title: (typeof mfTitle === 'string' ? mfTitle.trim() : ''), nodes: ns, edges: es}).replace(/</g, '\\u003c').replace(/>/g, '\\u003e').replace(/&/g, '\\u0026'))"""


def _encode_json(obj):
    """Same escaping as GET_DATA_JS, for JSON produced on the Python side."""
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _field_name(note, name, index):
    """Field called `name`, or the field at `index` for notes using a different note type."""
    if name in note:
        return name
    keys = note.keys()
    return keys[index] if len(keys) > index else None


def _get_json_field(editor):
    """Returns the raw content of the Algorithm_JSON field (or the 2nd field)."""
    f = _field_name(editor.note, "Algorithm_JSON", 1)
    return (editor.note[f] or "{}") if f else "{}"


def _set_json_field(editor, value):
    f = _field_name(editor.note, "Algorithm_JSON", 1)
    if f:
        editor.note[f] = value
    editor.loadNote()


def _clean_json(raw):
    """The field may contain HTML (<br>, &nbsp;...) - strip it before parsing."""
    raw = re.sub(r"<br\s*/?>", "", raw or "", flags=re.I)
    raw = raw.replace("&nbsp;", " ")
    raw = re.sub(r"<[^>]*>", "", raw)
    raw = raw.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", "&")
    return raw.strip()


def _add_to_media(path):
    media = mw.col.media
    add = getattr(media, "add_file", None) or media.addFile
    return add(path)


IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp")


def _images_from_clipboard():
    """Image data (screenshot / copied image) or copied image files -> Anki media names."""
    md = QApplication.clipboard().mimeData()
    if md is None:
        return []
    names = []
    if md.hasUrls():  # files copied in the file manager
        for url in md.urls():
            p = url.toLocalFile()
            if p and p.lower().endswith(IMAGE_EXTS) and os.path.isfile(p):
                names.append(_add_to_media(p))
        if names:
            return names
    if md.hasImage():
        img = QApplication.clipboard().image()
        if not img.isNull():
            tmp = os.path.join(tempfile.gettempdir(), "medflow_%d.png" % int(time.time() * 1000))
            if img.save(tmp, "PNG"):
                try:
                    names.append(_add_to_media(tmp))
                finally:
                    if os.path.exists(tmp):
                        os.remove(tmp)
    return names


class MedFlowPage(QWebEnginePage):
    """Lets the editor page talk to Python through prompt('__medflow__:<cmd>')."""

    def __init__(self, parent_widget, parent=None):
        super().__init__(parent)
        self.parent_widget = parent_widget

    def javaScriptPrompt(self, origin, msg, default):
        if not msg.startswith(BRIDGE_PREFIX):
            return super().javaScriptPrompt(origin, msg, default)
        cmd = msg[len(BRIDGE_PREFIX):]
        names = []
        try:
            if cmd == "pick":
                files, _ = QFileDialog.getOpenFileNames(
                    self.parent_widget, "Choose image", "",
                    "Images (*.png *.jpg *.jpeg *.gif *.webp *.svg *.bmp)")
                names = [_add_to_media(f) for f in files]
            elif cmd == "pasteimg":
                names = _images_from_clipboard()
        except Exception as e:
            showInfo(f"Could not add the image: {e}")
        return True, json.dumps(names)


class FlowchartDialog(QDialog):
    def __init__(self, editor, initial_json):
        super().__init__(editor.widget)
        self.editor = editor
        self.initial_json = initial_json
        self._loaded_state = None
        self._force_close = False

        self.setWindowTitle(ADDON_NAME)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(1280, 800)

        self.web = QWebEngineView(self)
        self.web.setPage(MedFlowPage(self, self.web))
        self._dark = _night_mode()
        if self._dark:
            self.web.page().setBackgroundColor(QColor("#161a24"))

        self.btn_save = QPushButton("Save to note")
        self.btn_sync = QPushButton("Save and generate cards")
        self.btn_cancel = QPushButton("Close")
        self.btn_settings = QPushButton("Settings")
        self.btn_settings.clicked.connect(lambda: open_settings(self))
        self.btn_save.setShortcut(QKeySequence("Ctrl+S"))
        self.btn_save.clicked.connect(lambda: self._save(sync=False))
        self.btn_sync.clicked.connect(lambda: self._save(sync=True))
        self.btn_cancel.clicked.connect(self.close)

        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 6)
        bar.addWidget(self.btn_settings)
        bar.addStretch(1)
        bar.addWidget(self.btn_cancel)
        bar.addWidget(self.btn_save)
        bar.addWidget(self.btn_sync)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.web, 1)
        layout.addLayout(bar)

        self.web.loadFinished.connect(self._on_loaded)
        path = os.path.join(os.path.dirname(__file__), EDITOR_FILE)
        self.web.load(QUrl.fromLocalFile(path))

    # -- loading -------------------------------------------------------------
    def _on_loaded(self, ok):
        if not ok:
            showInfo("Could not load the editor.")
            return
        media_url = QUrl.fromLocalFile(mw.col.media.dir()).toString().rstrip("/") + "/"
        js = (
            "(function(){"
            "var d = JSON.parse(%s);"
            "ns = Array.isArray(d.nodes) ? d.nodes : [];"
            "es = Array.isArray(d.edges) ? d.edges : [];"
            "mfTitle = typeof d.title === 'string' ? d.title : '';"
            "window.MF_CFG = %s;"
            "window.MEDFLOW_MEDIA_URL = %s;"
            "document.documentElement.setAttribute('data-theme', %s);"
            "sel = null; applyToolbarLayout(); loadedChart(); render();"
            # the native buttons below replace the clipboard-based Save/Copy
            "var b = document.querySelector('#toolbar .save'); if (b) b.style.display = 'none';"
            "})();"
        ) % (json.dumps(self.initial_json), json.dumps(get_config()), json.dumps(media_url),
             json.dumps("dark" if self._dark else "light"))
        self.web.page().runJavaScript(js)
        self.web.page().runJavaScript(GET_DATA_JS, self._remember_state)

    def apply_config(self):
        """Redraws the chart after the settings changed (arrow style, hint bubbles, extra markers)."""
        self.web.page().runJavaScript(
            "window.MF_CFG = %s; if (typeof applyToolbarLayout === 'function') applyToolbarLayout();"
        " if (typeof render === 'function') render();" % json.dumps(get_config()))

    def _remember_state(self, state):
        self._loaded_state = state

    # -- saving --------------------------------------------------------------
    def _save(self, sync):
        def done(state):
            if not state:
                showInfo("Could not read the data from the editor.")
                return
            _set_json_field(self.editor, state)
            self._loaded_state = state
            self._force_close = True
            self.close()
            if sync:
                sync_cards(self.editor)
            else:
                tooltip("Flowchart saved to the Algorithm_JSON field.")

        self.web.page().runJavaScript(GET_DATA_JS, done)

    # -- closing (warn about unsaved changes) --------------------------------
    def closeEvent(self, event):
        if self._force_close:
            if self in _open_windows:
                _open_windows.remove(self)
            event.accept()
            return
        event.ignore()

        def check(state):
            if state is None or state == self._loaded_state:
                self._force_close = True
                self.close()
            elif askUser("You have unsaved changes. Close anyway?", parent=self):
                self._force_close = True
                self.close()

        self.web.page().runJavaScript(GET_DATA_JS, check)


def open_ext(editor):
    path = os.path.join(os.path.dirname(__file__), EDITOR_FILE)
    if not os.path.isfile(path):
        showInfo(EDITOR_FILE + " was not found in the add-on folder.")
        return

    raw = _clean_json(_get_json_field(editor))
    try:
        parsed = json.loads(raw) if raw and raw != "null" else {}
        if not isinstance(parsed, dict):
            parsed = {}
    except Exception:
        if not askUser("The Algorithm_JSON field does not contain valid JSON. Open an empty editor?"):
            return
        parsed = {}

    dlg = FlowchartDialog(editor, json.dumps(parsed))
    _open_windows.append(dlg)
    dlg.showMaximized()


# ---- Card generation ----------------------------------------------------------

def sync_cards(editor):
    editor.saveNow(lambda: _sync_logic(editor))


def _sync_logic(editor):
    note = editor.note
    json_field = _field_name(note, "Algorithm_JSON", 1)
    text_field = _field_name(note, "Text", 0)
    data_str = _clean_json(note[json_field]) if json_field else ""
    if not data_str or data_str == "null":
        tooltip("The Algorithm_JSON field is empty.")
        return

    try:
        data_obj = json.loads(data_str)
    except Exception as e:
        showInfo(f"Invalid JSON in the Algorithm_JSON field: {e}")
        return
    if not isinstance(data_obj, dict):
        showInfo("The Algorithm_JSON field does not hold a flowchart.")
        return

    nodes = [n for n in (data_obj.get("nodes") or []) if isinstance(n, dict)]
    data_obj["nodes"] = nodes

    # Number every box and list item 1..N in reading order: rows top to bottom, left to right,
    # each box followed by its own list.
    mapping, total = numbering.renumber(nodes)
    if not total:
        showInfo("No clozes found. Give at least one box a cloze number, or add a list item, in the editor.")
        return

    # The title goes first, so Anki's browser lists the note under it and searches find it.
    title = str(data_obj.get("title") or "").strip()
    trigger_str = f'<span class="mf-title">{html.escape(title)}</span> ' if title else ""
    trigger_str += "".join(f"{{{{c{c}::CLOZEID_{c}}}}} " for c in range(1, total + 1))

    # Reference the extra images in a field so Anki's media check, exports and
    # shared decks keep them (hidden: they are only used by the back of the card).
    images = []
    for n in nodes:
        for f in n.get("images", []) or []:
            if f not in images:
                images.append(f)
    for f in images:
        trigger_str += f'<img src="{html.escape(f, quote=True)}" style="display:none"> '

    if json_field:
        note[json_field] = _encode_json(data_obj)
    if text_field:
        note[text_field] = trigger_str

    # A note already in the collection: move each card to its box or item's new number, so its
    # review history stays with it, then save the note (which also creates cards for new numbers).
    leftovers = 0
    if getattr(note, "id", 0):
        leftovers = numbering.move_card_history(mw.col, note, mapping, total)
        mw.col.update_note(note)
    editor.loadNote()

    tooltip(f"{total} card(s), numbered in reading order.")
    if leftovers:
        showInfo("%d card(s) no longer belong to any box or list item and are now empty.\n"
                 "Remove them with Tools > Empty Cards." % leftovers)


def add_btns(buttons, editor):
    b1 = editor.addButton(icon=None, cmd="alg_open", func=lambda e=editor: open_ext(e), tip="Open Flowchart Editor", label="Alg")
    buttons.append(b1)
    return buttons

addHook("setupEditorButtons", add_btns)


# ---- Settings dialog ------------------------------------------------------------

class SettingsDialog(QDialog):
    ARROWS = [("straight", "Straight (right angles only)"), ("curved", "Curved")]
    VIEWS = [("path", "Only the boxes leading to the asked box"), ("full", "The whole flowchart")]
    LAYOUTS = [("float", "Float over the canvas (original layout)"),
               ("scroll", "Scroll: one row in the top bar, scrolls sideways when narrow"),
               ("wrap", "Wrap: in the top bar, adding rows when narrow")]

    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle("MedFlow settings")
        conf = get_config()

        self.arrows = QComboBox()
        for key, label in self.ARROWS:
            self.arrows.addItem(label, key)
        self.arrows.setCurrentIndex([k for k, _ in self.ARROWS].index(conf["arrow_style"]))

        self.view = QComboBox()
        for key, label in self.VIEWS:
            self.view.addItem(label, key)
        self.view.setCurrentIndex([k for k, _ in self.VIEWS].index(conf["card_view"]))

        self.layout_group = QButtonGroup(self)
        self.layout_radios = {}
        layout_col = QVBoxLayout()
        layout_col.setSpacing(4)
        for key, label in self.LAYOUTS:
            rb = QRadioButton(label)
            rb.setChecked(key == conf["toolbar_layout"])
            self.layout_group.addButton(rb)
            self.layout_radios[key] = rb
            layout_col.addWidget(rb)

        self.hint_bubbles = QCheckBox("Hint bubbles (top-left: shows the hint, click to edit it)")
        self.hint_bubbles.setChecked(conf["hint_bubbles"])
        self.extra_markers = QCheckBox("Extra markers (bottom-left: click to open the box's extra)")
        self.extra_markers.setChecked(conf["extra_markers"])

        form = QFormLayout()
        form.addRow("Arrows:", self.arrows)
        form.addRow("Review cards show:", self.view)
        form.addRow("Format and zoom bars:", layout_col)
        form.addRow("On boxes in the editor:", self.hint_bubbles)
        form.addRow("", self.extra_markers)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def accept(self):
        save_config({"arrow_style": self.arrows.currentData(), "card_view": self.view.currentData(),
                     "hint_bubbles": self.hint_bubbles.isChecked(), "extra_markers": self.extra_markers.isChecked(),
                     "toolbar_layout": next((k for k, rb in self.layout_radios.items() if rb.isChecked()), "scroll")})
        if mw.col:
            install_model()  # the settings are baked into the card templates
        for dlg in list(_open_windows):
            try:
                dlg.apply_config()
            except Exception:
                pass
        tooltip("MedFlow settings saved.")
        super().accept()


def open_settings(parent=None):
    SettingsDialog(parent).exec()


def _setup_menu():
    action = QAction("MedFlow settings…", mw)
    action.triggered.connect(lambda: open_settings())
    mw.form.menuTools.addAction(action)
    mw.addonManager.setConfigAction(_addon_module(), lambda: open_settings())

_setup_menu()


# ---- One-screen list review --------------------------------------------------------

try:
    from . import list_review
    list_review.install(MODEL_NAME, _clean_json)
except Exception as _e:  # never stand between the user and their reviews
    print(f"[MedFlow] List review is unavailable: {_e}")
