# tkinter-column-select

box-(select, cut, copy, paste, type), anysel-(drag, drop), and multiline-caret for tk.Text

**hotkeys**

| feature     | hotkeys                                                         |
|-------------|-----------------------------------------------------------------|
| box-select  | place caret at desired selection start then Shift+Alt+LMB+drag  |
| box-cut     | Cntl+x                                                          |
| box-copy    | Cntl+c                                                          |
| box-paste   | Cntl+v                                                          |
| drag-drop   | LMB over (any) selection + drag / release mouse to drop         |

--------------

**Info**
- For the typing feature, make a box-selection (with or without width) and start typing. A box selection that has no width will produce a "multiline-caret".
- Pressing `BackSpace` while in "multiline-caret mode" will perform a `BackSpace` on every active line
- Pressing any `Left` or `Right` key while in any selection will deselect and set the caret at the beginning(left) or end(right) of the former selection. 
- You can put the caret where you want the selection to start. Press `Shift`+`Alt`, and mousedown where you want the selection to end. If you don't release you can still drag to adjust the selection
- You can put the caret where you want the selection to start. Press `Shift`+`Alt`, and use the regular arrow keys to expand the selection. NumPad arrow keys are not supported.
- In "box-select mode" you can select in any direction with mouse or arrow keys.
- Box-selecting may create an unlimited amount of whitespace if it needs to highlight columns that don't actually exist on the "current" line. It also cleans up all of the whitespace it generates, every time.
- There is a vertical grab offset for box-selection. This means, if you grab/drag from the (ex:) second row of the selection, you have to release where you would want the second row to drop.


--------------

**Glitches:**

- Very rarely, releasing `Alt` to come out of the hotkey combo will pause the display. If this happens press `Alt` again. 

