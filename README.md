# tkinter-column-select

box-(select, cut, copy, paste, type) and sel-(drag, drop) for tk.Text

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
3) If you start to `drag` but change your mind, returning the cursor to where you started and releasing will abort `drop`. You can tell you are back where you started because the mouse cursor will return to `xterm`. This feature is a little bit useless. If you bring the cursor back to the selection, within the same row you grabbed it in, it will just drop it where it already was. The end results are the same, but you don't have to get the cursor on the exact column you grabbed at.
4) Pressing any `Left` or `Right` key while in "boxselect mode" will deselect and set the caret at the beginning(left) or end(right) of the former selection. This may not work for regular selections yet. I can't remember if I enabled it.

--------------

**Issues:**

1) Sometimes releasing `Alt` to come out of the hotkey combo will pause the display. If this happens press `Alt` again. There are commented out spots in the code where you can see I am trying to suppress this behavior, and I'm all over the target. I haven't found the proper combo to kill the issue. However, if you release the hotkeys in the same order you pressed them it tends to be fine.
2) Sometimes releasing `Alt` to come out of the hotkey combo will turn off your ability to select. If this happens press `Alt` again.
3) Releasing `Shift` and `Alt` before releasing the mouse is a mess. Release the mouse first.

