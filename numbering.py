"""Cloze numbering in reading order, and moving review history when the numbers change.

When cards are generated, every box and list item is renumbered 1, 2, 3... with no gaps, in the
order the chart is read: rows from top to bottom, boxes from left to right within a row, and each
box followed by its own list (top to bottom) before the next box.

A card's review history belongs to its cloze number (the card's ordinal), so renumbering would
hand one box's history to another. move_card_history() prevents that: each existing card is given
the ordinal of its box or item's new number, so the history follows the box or item. Cards whose
box or item no longer exists are moved past the last number, where they are empty cards
(Tools > Empty Cards removes them).

No aqt imports here, so this can be tested against a plain Anki collection.
"""

from typing import Dict, List, Tuple

# Boxes whose tops are within this many pixels of the first box in a row belong to that row.
ROW_TOLERANCE = 40


def _num(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _pos(node, key) -> float:
    try:
        return float(node.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _has_text(item) -> bool:
    return isinstance(item, dict) and str(item.get("text") or "").strip() != ""


def reading_order(nodes: List[dict]) -> List[dict]:
    """The boxes in reading order: rows top to bottom, left to right within a row."""
    boxes = sorted((n for n in nodes if isinstance(n, dict)), key=lambda n: (_pos(n, "y"), _pos(n, "x")))
    rows: List[Tuple[float, List[dict]]] = []
    for node in boxes:
        y = _pos(node, "y")
        if rows and y - rows[-1][0] <= ROW_TOLERANCE:
            rows[-1][1].append(node)
        else:
            rows.append((y, [node]))
    ordered: List[dict] = []
    for _y, row in rows:
        ordered.extend(sorted(row, key=lambda n: _pos(n, "x")))
    return ordered


def renumber(nodes: List[dict]) -> Tuple[Dict[int, int], int]:
    """Renumbers boxes and list items 1..N in reading order, in place.

    Each box comes first, then its list items. A box at 0 stays untested (its list is still
    numbered); boxes that share a number keep sharing one. Empty list lines get no number.
    Returns ({old number: new number}, N).
    """
    mapping: Dict[int, int] = {}
    box_numbers: Dict[int, int] = {}
    total = 0
    for node in reading_order(nodes):
        old = _num(node.get("cloze"))
        if old > 0:
            if old not in box_numbers:
                total += 1
                box_numbers[old] = total
            node["cloze"] = box_numbers[old]
            mapping.setdefault(old, box_numbers[old])
        items = node.get("items")
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            if not _has_text(item):
                item["cloze"] = 0
                continue
            total += 1
            old = _num(item.get("cloze"))
            if old > 0:
                mapping.setdefault(old, total)
            item["cloze"] = total
    return mapping, total


def move_card_history(col, note, mapping: Dict[int, int], total: int) -> int:
    """Gives each of the note's cards the ordinal of its box or item's new number, so the review
    history moves with it. Call before saving the renumbered note. Cards whose box or item is gone
    get ordinals after `total` (empty cards). Returns how many such leftover cards there are."""
    plan = []
    taken = set()
    leftovers = []
    for card in sorted(note.cards(), key=lambda c: c.ord):
        new = mapping.get(card.ord + 1)
        if new and new - 1 not in taken:
            taken.add(new - 1)
            plan.append((card, new - 1))
        else:
            leftovers.append(card)
    spare = total  # renumbered ordinals are all below `total`, so these never collide
    for card in leftovers:
        while spare in taken:
            spare += 1
        taken.add(spare)
        plan.append((card, spare))
    changed = []
    for card, ordinal in plan:
        if card.ord != ordinal:
            card.ord = ordinal
            changed.append(card)
    if changed:
        if hasattr(col, "update_cards"):
            col.update_cards(changed)
        else:
            for card in changed:
                col.update_card(card)
    return len(leftovers)
