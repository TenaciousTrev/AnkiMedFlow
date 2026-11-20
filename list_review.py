"""Review a box's elaboration list item by item, on one screen, in list order.

Adapted from the list review of the Anki Papers add-on. A MedFlow note is one cloze note:
each box with a cloze number is a card, and so is every "+" item of a box's elaboration
list. Anki's scheduler would show a list's items one at a time, in its own order, mixed
in with everything else. This makes the desktop reviewer walk them as one list:

  * When a list item comes up, the reviewer starts at the first item of that list that
    is due, whichever item the scheduler offered.
  * After you rate an item, the next due item of the same list is shown straight away.
    Items that aren't due are skipped; they still show on the card as context, since
    every item above the current one is revealed.
  * Sibling burying is ignored for the list: rating item 1 would otherwise bury the rest
    of it (and the rest of the flowchart) until tomorrow.
  * Undo steps back one item.

Box cards are not part of any walk and are scheduled as usual. On AnkiMobile, AnkiDroid
and AnkiWeb no add-on runs, and the items come up one by one as ordinary cards, each
showing the items above it.

How it works. The reviewer shows whatever card sits on top of the v3 scheduler's queue,
and the backend refuses to answer any other card ("not at top of queue"). So when the
next item is not the top card we put it on screen ourselves (Reviewer._get_next_v3_card,
wrapped below) and, just before it is answered, drop the backend's cached queue with an
update_card that leaves no undo step. The answer then goes through Anki's normal path,
as a single undoable "Answer Card".
"""

from __future__ import annotations

import json
import time
from typing import Callable, Dict, List, Optional, Tuple

from aqt import gui_hooks, mw

_RATING_LABELS = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}

# Card queue values (anki/consts.py).
_NEW, _LRN, _REV, _DAY_LRN = 0, 1, 2, 3
_SIBLING_BURIED = -2

_model_name = "MedFlow"
_clean_json: Callable[[str], str] = lambda s: s


class _Chain:
    """The list being walked: which note, which box's list, how far, and what was rated."""

    def __init__(self) -> None:
        self.note_id: Optional[int] = None
        self.box: Optional[str] = None  # id of the box whose list is walked
        self.pos = -1  # list position of the last item answered
        self.ratings: Dict[int, int] = {}  # card ord -> ease, this session
        # The list walked last and its ratings, so a walk that ends and picks up again on the
        # same list (an item came back from learning) still labels what you rated a minute ago.
        self._last = (None, None, {})

    def start(self, note_id: Optional[int], box: Optional[str]) -> None:
        last_id, last_box, last_ratings = self._last
        same = note_id is not None and note_id == last_id and box == last_box
        self.note_id, self.box, self.pos = note_id, box, -1
        self.ratings = dict(last_ratings) if same else {}

    def clear(self) -> None:
        if self.note_id is not None:
            self._last = (self.note_id, self.box, dict(self.ratings))
        self.note_id, self.box, self.pos, self.ratings = None, None, -1, {}

    def forget(self) -> None:
        self.clear()
        self._last = (None, None, {})

    def snapshot(self):
        return (self.note_id, self.box, self.pos, dict(self.ratings))

    def restore(self, snap) -> None:
        self.note_id, self.box, self.pos, self.ratings = snap[0], snap[1], snap[2], dict(snap[3])


_chain = _Chain()
# One entry per item answered in a walk, newest last, so undo can step back:
# (card id, its reps after the answer, the walk as it was before the answer).
_answered: List[tuple] = []
# A card the next _get_next_v3_card must show (the item an undo restored).
_force_next: Optional[int] = None
# The card on screen when we put it there rather than the scheduler.
_placed_card_id: Optional[int] = None


# ─── List structure and due-ness ──────────────────────────────────────────

def _model_id(col) -> Optional[int]:
    model = col.models.by_name(_model_name)
    return int(model["id"]) if model else None


def is_medflow_card(col, card) -> bool:
    mid = _model_id(col)
    if mid is None or card is None:
        return False
    try:
        return int(card.note().mid) == mid
    except Exception:
        return False


def _lists(note) -> Dict[str, List[int]]:
    """Box id -> card ords of its list items, in list order (items with text only)."""
    try:
        name = "Algorithm_JSON" if "Algorithm_JSON" in note else note.keys()[1]
        data = json.loads(_clean_json(note[name]))
    except Exception:
        return {}
    out: Dict[str, List[int]] = {}
    for node in (data.get("nodes") or []) if isinstance(data, dict) else []:
        if not isinstance(node, dict) or not isinstance(node.get("items"), list):
            continue
        ords = []
        for it in node["items"]:
            if not isinstance(it, dict) or not str(it.get("text") or "").strip():
                continue
            try:
                c = int(it.get("cloze") or 0)
            except (TypeError, ValueError):
                c = 0
            if c > 0:
                ords.append(c - 1)
        if ords:
            out[str(node.get("id"))] = ords
    return out


def list_of(note, ord_: int) -> Optional[Tuple[str, List[int]]]:
    """(box id, list order) of the list that card `ord_` is an item of, or None for a box card."""
    for box, ords in _lists(note).items():
        if ord_ in ords:
            return box, ords
    return None


def is_due_now(col, card) -> bool:
    """Whether an item would be studied now, if the scheduler offered it.

    New items count as due (a new list is introduced all at once), and so do items Anki
    buried only because a sibling was answered. Items in a filtered deck, suspended or
    buried by hand are left alone.
    """
    if card.odid:
        return False
    if card.did not in set(col.decks.active()):
        return False
    queue, ctype = card.queue, card.type
    if queue == _SIBLING_BURIED:
        queue = {0: _NEW, 1: _LRN, 2: _REV, 3: _DAY_LRN}.get(ctype, -99)
    if queue == _NEW:
        return True
    if queue in (_REV, _DAY_LRN):
        return card.due <= col.sched.today
    if queue == _LRN:
        # Strictly due. Anki's "learn ahead" window is for when nothing else is left;
        # pulling a sibling 15 minutes early would cut its step short.
        return card.due <= time.time()
    return False


def first_due(col, note_id: int, box: str, after_pos: int = -1):
    """The first due item of a box's list after list position after_pos, or None.

    Returns (position, card)."""
    try:
        note = col.get_note(note_id)
    except Exception:
        return None
    order = _lists(note).get(box) or []
    by_ord = {c.ord: c for c in note.cards()}
    for pos, ord_ in enumerate(order):
        if pos <= after_pos:
            continue
        card = by_ord.get(ord_)
        if card is not None and is_due_now(col, card):
            return pos, card
    return None


# ─── Putting a card on screen ─────────────────────────────────────────────

def _queued_card_for(col, card, queued):
    """A QueuedCards.QueuedCard for `card`: the scheduler's own entry when the card is in the
    queue, or one built from its current scheduling states."""
    from anki.scheduler_pb2 import QueuedCards, SchedulingContext

    for qc in queued.cards:
        if qc.card.id == card.id:
            return qc
    try:
        fuller = col.sched.get_queued_cards(fetch_limit=1000)
        for qc in fuller.cards:
            if qc.card.id == card.id:
                return qc
    except Exception:
        pass
    queue = card.queue
    if queue == _SIBLING_BURIED:
        queue = card.type
    kind = {_NEW: QueuedCards.NEW, _REV: QueuedCards.REVIEW}.get(queue, QueuedCards.LEARNING)
    return QueuedCards.QueuedCard(
        card=card._to_backend_card(),
        queue=kind,
        states=col._backend.get_scheduling_states(card.id),
        context=SchedulingContext(deck_name=col.decks.name(card.did), seed=card.id + card.reps),
    )


def _place(reviewer, card) -> None:
    """Make `card` the reviewer's current card, as if the scheduler chose it."""
    global _placed_card_id
    from anki.cards import Card
    from anki.scheduler_pb2 import QueuedCards
    from aqt.reviewer import V3CardInfo

    col = reviewer.mw.col
    queued = reviewer._v3.queued_cards if reviewer._v3 else QueuedCards()
    entry = _queued_card_for(col, card, queued)
    rest = [qc for qc in queued.cards if qc.card.id != card.id]
    combined = QueuedCards(
        cards=[entry] + rest,
        new_count=queued.new_count,
        learning_count=queued.learning_count,
        review_count=queued.review_count,
    )
    reviewer._v3 = V3CardInfo.from_queue(combined)
    reviewer.card = Card(col, backend_card=entry.card)
    reviewer.card.start_timer()
    _placed_card_id = card.id


def _wrap_get_next_v3_card(original):
    def _get_next_v3_card(reviewer) -> None:
        global _placed_card_id
        original(reviewer)
        _placed_card_id = None
        try:
            if getattr(reviewer, "_v3", None) is not None:
                _choose(reviewer)
        except Exception as e:  # never stand between the user and their reviews
            print(f"[MedFlow] List review: {e}")
            _chain.clear()

    def _choose(reviewer) -> None:
        global _force_next
        col = reviewer.mw.col
        top = reviewer.card

        if _force_next is not None:
            cid, _force_next = _force_next, None
            try:
                card = col.get_card(cid)
            except Exception:
                card = None
            if card is not None:
                if not top or top.id != card.id:
                    _place(reviewer, card)
                return

        # Carry on down the list being walked.
        if _chain.note_id is not None:
            nxt = first_due(col, _chain.note_id, _chain.box, _chain.pos)
            if nxt is not None:
                _pos, card = nxt
                if not top or top.id != card.id:
                    _place(reviewer, card)
                return
            _chain.clear()

        # The scheduler offered a list item: start that list at its first due item.
        if top is not None and is_medflow_card(col, top):
            found = list_of(top.note(), top.ord)
            if found is None:
                return  # a box card: scheduled as usual
            _chain.start(top.nid, found[0])
            first = first_due(col, top.nid, found[0])
            if first is not None and first[1].id != top.id:
                _place(reviewer, first[1])

    return _get_next_v3_card


# ─── Hooks ────────────────────────────────────────────────────────────────

def _will_answer(proceed_ease, reviewer, card):
    """Let the backend answer an item we placed ahead of its queue."""
    proceed, _ease = proceed_ease
    if proceed and card is not None and card.id == _placed_card_id:
        try:
            col = reviewer.mw.col
            # Any card write drops the backend's cached queue, and with no queue there is no
            # "top" for the answer to be checked against. skip_undo_entry keeps undo to the one
            # "Answer Card" step.
            col.update_card(col.get_card(card.id), skip_undo_entry=True)
        except Exception as e:
            print(f"[MedFlow] List review: could not release the queue: {e}")
    return proceed_ease


def _did_answer(reviewer, card, ease) -> None:
    col = reviewer.mw.col
    if not is_medflow_card(col, card):
        return
    found = list_of(card.note(), card.ord)
    if found is None:
        return
    box, order = found
    before = _chain.snapshot()
    if _chain.note_id != card.nid or _chain.box != box:
        _chain.start(card.nid, box)
    _chain.pos = order.index(card.ord)
    _chain.ratings[card.ord] = int(ease)
    try:
        reps = col.get_card(card.id).reps
    except Exception:
        reps = None
    _answered.append((card.id, reps, before))
    del _answered[:-200]


def _did_undo(_out) -> None:
    """Step the walk back with Anki's undo of an item's answer."""
    global _force_next
    if not _answered or not mw or not mw.col:
        return
    cid, reps, before = _answered[-1]
    try:
        now = mw.col.get_card(cid).reps
    except Exception:
        return
    if reps is None or now >= reps:
        return  # that undo was something else
    _answered.pop()
    _chain.restore(before)
    _force_next = cid


def _will_end() -> None:
    global _force_next, _placed_card_id
    _chain.forget()
    _answered.clear()
    _force_next = _placed_card_id = None


# Labels the items above the asked one (rows rendered by the card template, keyed by cloze number).
_CHIPS_JS = """<script>(function(){var r=%s;
document.querySelectorAll('.elab-row[data-cloze]').forEach(function(row){
var c=r[row.getAttribute('data-cloze')];if(!c||row.querySelector('.mf-chip'))return;
var e=document.createElement('span');e.className='mf-chip mf-chip-'+c[0];e.textContent=c[1];row.appendChild(e);});})();</script>"""


def _card_will_show(text: str, card, kind: str) -> str:
    """Label the items above the current one: how you rated them on this walk, or "not due"
    for the ones the walk skipped."""
    if not kind.startswith("review") or _chain.note_id is None or card is None:
        return text
    try:
        col = mw.col
        if card.nid != _chain.note_id or not is_medflow_card(col, card):
            return text
        found = list_of(card.note(), card.ord)
        if found is None or found[0] != _chain.box:
            return text
        order = found[1]
        here = order.index(card.ord)
        by_ord = {c.ord: c for c in card.note().cards()}
        chips = {}
        for ord_ in order[:here]:
            if ord_ in _chain.ratings:
                ease = _chain.ratings[ord_]
                chips[str(ord_ + 1)] = [ease, _RATING_LABELS.get(ease, "")]
            elif ord_ in by_ord and not is_due_now(col, by_ord[ord_]):
                chips[str(ord_ + 1)] = [0, "not due"]
        if not chips:
            return text
        return text + (_CHIPS_JS % json.dumps(chips))
    except Exception as e:
        print(f"[MedFlow] List review chips: {e}")
        return text


_installed = False


def install(model_name: str, clean_json: Callable[[str], str]) -> None:
    """Wire list review into Anki's reviewer. Safe to call more than once."""
    global _installed, _model_name, _clean_json
    _model_name, _clean_json = model_name, clean_json
    if _installed:
        return
    from aqt.reviewer import Reviewer

    Reviewer._get_next_v3_card = _wrap_get_next_v3_card(Reviewer._get_next_v3_card)
    gui_hooks.reviewer_will_answer_card.append(_will_answer)
    gui_hooks.reviewer_did_answer_card.append(_did_answer)
    if hasattr(gui_hooks, "state_did_undo"):
        gui_hooks.state_did_undo.append(_did_undo)
    gui_hooks.reviewer_will_end.append(_will_end)
    gui_hooks.card_will_show.append(_card_will_show)
    _installed = True
