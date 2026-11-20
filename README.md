# MEDFlow – Interactive Medical Flowchart Generator & Cloze Flashcards

**Turn complex medical concepts into visual learning experiences.**

MEDFlow is an Anki add-on that lets you create interactive medical flowcharts and transform them into Cloze (fill-in-the-blank) flashcards. It combines visual organization, clinical reasoning, and Anki's spaced repetition system to make studying more active and engaging.

Inspired by the **ZeestMedical** project, MEDFlow was independently developed to provide a visual flowchart editor integrated into Anki.


## ✦ KEY FEATURES

### 1. 🎨 Interactive Flowchart Editor
Build medical algorithms using three types of elements:
- **Step / Box:** Represents a step, procedure, clinical finding, or piece of information.
- **Decision:** Represents a clinical decision or branching point (diamond shape).
- **Information:** Highlights additional explanations or important details.

Move elements freely, organize diagrams, and connect components to create complex clinical pathways. Automatic alignment guides make organization easier.

### 2. 🔗 Connections and Clinical Flows
- Connect elements using draggable blue connection points.
- Create parent-to-child relationships and reconnect arrows by dragging their endpoints.
- Add arrow labels such as "Yes", "No", "Positive", "Negative", or clinical criteria.
- Arrows are drawn with right angles only by default, like a printed algorithm; curved arrows are a setting away.
- Organize diagnostic and therapeutic decision trees.

<img src="https://raw.githubusercontent.com/davidbsouzaf-cloud/-MEDFlow-Interactive-Medical-Flowcharts-Cloze-Flashcards/7950bb0d3a145b5251460ae19bfb7093a2600f13/assets/como%20colocar%20multiplassetas.gif" width="750">

### 3. 🃏 Cloze Flashcard Generation
Assign Cloze numbers individually to flowchart elements. Elements sharing the same number belong to the same Anki card, while different numbers generate separate cards.

**Features:**
- Assign specific Cloze numbers or automatically increment them.
- Each card shows the flowchart's title and the boxes and arrows leading to the asked box (or the whole flowchart, in Settings).
- Identify the tested element through visual highlighting. The hidden node is revealed when clicked.

**Example:** Element 1 → c1 | Element 2 → c2 | Element 3 → c3

Click **Save and Generate Cards** to synchronize your flowchart with Anki.
<img src="https://raw.githubusercontent.com/davidbsouzaf-cloud/-MEDFlow-Interactive-Medical-Flowcharts-Cloze-Flashcards/7950bb0d3a145b5251460ae19bfb7093a2600f13/assets/como%20criar%20cards.gif" width="900">

### 4. 💡 Additional Notes and Images
Attach explanations and images to individual elements. Ideal for clinical pearls, detailed explanations, important observations, and illustrative medical images.

Select a box and use **≡ → Extra** in the sidebar (or click the box's **extra** marker). Extra content appears on the back of the corresponding Cloze card. Images can be added using the **+ Add Image** button or pasted directly with `Ctrl + V` (screenshots or copied image files).

<img src="https://raw.githubusercontent.com/davidbsouzaf-cloud/-MEDFlow-Interactive-Medical-Flowcharts-Cloze-Flashcards/7950bb0d3a145b5251460ae19bfb7093a2600f13/assets/como%20colocar%20imagens%20e%20extra.gif" width="900">

### 5. ✍️ Text Formatting
Customize element content with:
- Bold, italic, and underline.
- Different font sizes and font families.
- Bulleted and numbered lists.
- Clear formatting options.

<img src="https://raw.githubusercontent.com/davidbsouzaf-cloud/-MEDFlow-Interactive-Medical-Flowcharts-Cloze-Flashcards/7950bb0d3a145b5251460ae19bfb7093a2600f13/assets/como%20editar%20texto.gif" width="750">

### 6. 📤 Import and Export
- Export flowcharts as JSON files.
- Import previously exported diagrams.
- Back up, reuse, and modify existing algorithms.

### 7. 🧭 Navigation and Workspace
- Zoom in and out or fit the entire flowchart to the workspace.
- The text-format and zoom bars sit in the top bar (one scrolling row, or wrapping rows) or float over the canvas, as chosen in Settings.
- Pan across the canvas by dragging the background.
- Automatically align elements using visual guides.
- Supports Anki dark mode.
- Preserves zoom and canvas position between the front and back of cards and between cards within the same review session.

### 8. 🔒 Privacy and Storage
- No data is sent to external servers; everything is stored locally on your computer.
- Flowcharts are saved as JSON directly inside the Anki note, making backup, export, and deck sharing easier.
- Images are stored in Anki's media folder and referenced automatically, allowing them to be included in exports and shared decks.

### 9. ➕ Elaboration Lists
Every step and decision box has a small **▸** in a strip along its bottom edge; hovering shows "Elaboration" beside it, never over the box's text. Click it to open a translucent panel beside the box and type its details as `+` lines: **Enter** starts the next line, **Enter** on an empty line ends the list, and pasting several lines makes several items.
- Each line is its own cloze card, reviewed **in list order on one screen**, like Anki Papers list cards. When any item comes up, the review starts at the list's first due item, and after you rate one the next one follows. Items that aren't due are skipped but stay visible as context.
- **Save and generate cards** numbers everything 1, 2, 3… with no gaps, in reading order: rows from top to bottom, boxes from left to right, each box followed by its own list. When a number changes, the card's review history moves with its box or list item, so rewording, reordering, adding or deleting never mixes up your progress. Cards of deleted boxes or items are left empty; **Tools → Empty Cards** removes them.
- Panels open on the side that keeps them clear of the arrows: the top box to the right, boxes on the left half to the left, boxes on the right half to the right, and the bottom row below.
- New step and decision boxes get a cloze number automatically (set it to 0 to leave a box untested). The numbers shown while editing are provisional until cards are generated.

### 10. 💬 Cloze Hints
Hints work as they do in Anki's own clozes (`{{c1::answer::hint}}`): the hidden box or item shows `[hint]` on the front of its card in place of `[...]`.
- **List items:** type `answer::hint` on the `+` line, e.g. `Cefepime::4th-generation cephalosporin`. The first `::` starts the hint.
- **Boxes:** click the hint bubble in the box's top-left corner (it shows the hint, or **+ hint** when you hover over or select a box without one), type the hint and press **Enter**. **Esc** cancels; an empty hint removes it. You can also select a box and use **≡ → Hint** in the sidebar (or `Ctrl + Shift + H`).

### 11. 🏷️ Titles and Focused Cards
Give each flowchart a title in the editor's toolbar. It shows at the top of every card from that flowchart and leads the note in Anki's browser.
On review, a card shows only the boxes and arrows leading to the box being asked. For a list item, that box's list opens with the items above shown and the asked item hidden.

### 12. ⚙️ Settings
**Tools → MedFlow settings…** (or **Settings** under the editor):
- **Arrows:** straight (right angles only, the default) or curved.
- **Review cards show:** only the path to the asked box (default), or the whole flowchart.
- **Format and zoom bars:** float over the canvas (original), scroll in one row of the top bar (default), or wrap onto more rows.
- **Hint bubbles** and **Extra markers** on boxes in the editor: each can be turned on or off on its own. With them off, use **≡ → Hint / Extra** in the sidebar.

## ✦ HOW TO USE MEDFlow

**Step 1 – Install and Open the Editor**
Install the add-on and restart Anki. The **MedFlow** note type is created automatically. Create a new note using this type and click the **Alg** button to open the editor.

**Step 2 – Build Your Flowchart**
Add steps, decisions, and information elements. Double-click an element to edit its text.

**Step 3 – Connect the Elements**
Drag a blue connection point from one element to another to create an arrow. Alternatively, use **Link Mode** to select a parent element and then its children.

**Step 4 – Assign Cloze Numbers**
Select an element and enter a number in the CLOZE field. Click **Apply** to assign it or **+1** to increment and apply the next number. A number decides whether a box is tested (0 = not tested) and which boxes are asked together (same number); the final numbers follow reading order when cards are generated.

**Step 5 – Add Extra Content**
Select an element and use **≡ → Hint** or **≡ → Extra** in the sidebar to add a hint, notes or images. Click a step or decision box's **▸** to add its elaboration list.

**Step 6 – Save and Generate Cards**
Use the buttons below the editor:
- **Save to note:** Saves the flowchart data to the Anki note.
- **Save and generate cards:** Saves the flowchart and generates its Cloze cards, numbered in reading order.

Your cards are now ready for review!

## ✦ KEYBOARD SHORTCUTS

| Shortcut | Action |
|---|---|
| `Ctrl + A` | Add a Step / Box |
| `Ctrl + B` | Add a Decision |
| `Ctrl + C` | Add an Information element |
| `Ctrl + Shift + E` | Edit selected element text |
| `Ctrl + Shift + X` | Open Extra notes and images |
| `Ctrl + Shift + H` | Edit the selected box's hint |
| `Ctrl + L` | Toggle Link Mode |
| `Ctrl + Shift + C` | Increment and apply Cloze number |
| `Ctrl + Shift + Alt + C` | Apply current Cloze number |
| `Ctrl + S` | Save flowchart to Anki card |
| `Ctrl + +` / `Ctrl + -` | Zoom in / out |
| `Ctrl + 0` | Reset zoom to 100% |
| `Ctrl + 9` | Fit entire flowchart to screen |
| `Ctrl + Mouse Wheel` | Zoom around cursor |
| `Delete` | Delete selected element or arrow |
| `Ctrl + Shift + Delete` | Clear entire flowchart |
| `Enter / F2` | Edit selected arrow label |
| `Escape` | Cancel Link Mode |

**Text formatting:** `Ctrl + B` Bold · `Ctrl + I` Italic · `Ctrl + U` Underline.

**Additional interactions:**
- Double-click an element to edit its text or an arrow to edit its label.
- Drag elements to reposition them.
- Drag the empty background to pan the workspace.
- Drag blue connection points to connect elements.
- Use `Ctrl + V` to paste images while editing Extra content.

*On macOS, use Command (⌘) instead of Ctrl for shortcuts that support the Meta key.*

## ✦ WHO IS IT FOR?
Ideal for medical students, nursing students, and healthcare professionals studying:
- 🧠 Diagnostic algorithms and differential diagnoses.
- 💊 Therapeutic protocols and clinical guidelines.
- 🫀 Pathophysiology and disease progression.
- 🚑 Emergency medicine algorithms.
- ⚖️ Clinical decision-making.
- 📊 Any subject that benefits from visual organization.

## ✦ COMPATIBILITY
- Anki 2.1.x (PyQt5 and PyQt6).
- Windows, macOS, and Linux.
- Anki dark mode support.
- Compatible with AnkiWeb and shared decks.

## ✦ DEVELOPMENT, AI & ACKNOWLEDGMENTS
MEDFlow was independently developed with inspiration from the **ZeestMedical** project. We acknowledge and thank its original developers and contributors for their work.

**Artificial Intelligence (AI) tools** were used throughout development to assist with programming, code generation, debugging, error identification, feature implementation, and user experience improvements. These tools supported the development process, helping explore technical solutions and accelerate implementation.

The project's concept, direction, and development were independently guided, with AI technologies serving as supporting tools throughout its creation.
## 📥 Download & Installation

**Get MEDFlow directly from Anki!**

**Add-on Code:**

```text
21119510
```

### How to install

1. Open **Anki** on your computer.
2. Navigate to **Tools → Add-ons**.
3. Click **Get Add-ons**.
4. Enter the code `21119510`.
5. Click **OK** and restart Anki.

### Compatibility

- **Supported versions:** Anki 2.1.50–2.1.65+
- **Last updated:** November 17, 2026

---

⭐ Enjoying MEDFlow? Consider starring this repository and sharing it with other medical students!
