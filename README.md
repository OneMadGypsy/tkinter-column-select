# tkinter-column-select

box-(select, cut, copy, paste, type), anysel-(drag, drop), and multiline-caret for tk.Text

**hotkeys**

| feature     | hotkeys                                                         |
|-------------|-----------------------------------------------------------------|
| box-select  | place cursor at desired selection start then Shift+Alt+LMB+drag |
| box-cut     | Cntl+x                                                          |
| box-copy    | Cntl+c                                                          |
| box-paste   | Cntl+v                                                          |
| drag-drop   | LMB over selection + drag / release mouse to drop               |

--------------

**Info**
1) For the typing feature, make a box-selection (with or without width) and start typing. A box selection that has no width will produce a "multiline-caret".
2) Pressing `BackSpace` while in "multiline-caret mode" will perform a `BackSpace` on every active line
3) If you start to `drag` but change your mind, returning the cursor to where you started and releasing will abort `drop`. You can tell you are back where you started because the mouse cursor will return to `xterm`. You can also bring the cursor back to the selection, within the same row you grabbed it in, and drop. It will just drop it where it already was. The end results are the same, but you don't have to get the cursor on the exact column you grabbed at.
4) Pressing any `Left` or `Right` key while in any selection will deselect and set the caret at the beginning(left) or end(right) of the former selection. 
5) You actually don't have to drag. You could put the caret where you want the selection to start. Press `Shift`+`Alt`, and mousedown where you want the selection to end. If you don't release you can still drag to adjust the selection
6) In "boxselect mode" you can select in any direction.
7) boxselecting may create an unlimited amount of whitespace if it needs to highlight columns that don't actually exist on the "current" line. It also cleans up **all** of the whitespace it generates, every time.
8) There is a horizontal grab offset for boxselection. This means if you (ex) grabbed the second row of the selection you have to release where you would want the second row to drop.


--------------

**Issues:**

1) Sometimes releasing `Alt` to come out of the hotkey combo will pause the display. If this happens press `Alt` again. 

