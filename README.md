# Columnar Behavior and Caret Manipulations for tk.Text

## Controls:

- Box selection begins by putting the caret at the index where you want to start the selection, and pressing `Alt`+`Shift`. <br/><br/>From there you have 3 options:
    - `LMB`+`DRAG` to drag out a box-selection
    - `LMB` at the point you want the selection to end. If you don't release you can still drag to adjust.
    - press `Arrow` keys in the direction that you want the box to expand/contract. (NumPad Arrows NOT supported)

- Creating a box-selection of no width will produce a multiline-caret. 
    - You can type at the multiline-caret, and whatever you type will appear on every active line. 
    - Pressing `BackSpace` will perform a backspace operation on every active line.

- After Making a box-selection and while the selection is still active, if you hold the `Shift` key you can use the `Arrow` keys to move the entire selection. This counts for multiline-carets, as well.

- Any selection can be drag-dropped. 
    - Press and hold `LMB` over a selection to grab, then drag and drop in a new location. 
    - In the case of box-selections there is a vertical offset applied to grab and drop. If you grabbed at (ex) the third row of a column, you would have to drop where you want the third row to be.

- With any selection active, pressing `Left` or `Right` will deselect and move the caret to the beginning (left) or end (right) of the former selection

- Cut, Copy and Paste work the same as you would expect and the hotkeys are no different. In or from box-select mode these are performed with column behavior.

- Any method of box-selection can be performed in any direction

## Features:

- A faint highlight is applied to the background of the line the caret is on ~ the "active line"

- Multiline-carets always have a brighter portion that reflects where the real caret is

- While you are in the process of draggin a selection the real caret is revealed and joins the active line highlight in following your cursor.

## Glitches:

- On very rare occassions, releasing `Alt` from the hotkey combo will result in the window gaining focus, and the text area seeming to freeze. If this happens just press `Alt` again.
