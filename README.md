# tkinter-column-select

box-(select, cut, copy, paste, redo, type) and sel-(drag, drop) for tk.Text

**hotkeys**

| feature     | hotkeys                                                         |
|-------------|-----------------------------------------------------------------|
| box-select  | place cursor at desired selection start then Shift+Alt+LMB+drag |
| box-cut     | Cntl+x                                                          |
| box-copy    | Cntl+c                                                          |
| box-paste   | Cntl+v                                                          |
| drag-drop   | LMB over selection + drag / release mouse to drop               |


For the typing feature make a box-selection (with or without width) and start typing.</br>
A box selection that has no width will produce a multiline caret.</br>
Pressing `BackSpace` while in "multiline-caret mode" will perform a `BackSpace` on every active line

**Glitches:**

1) sometimes releasing `Alt` to come out of the hotkey combo will pause the display. If this happens press `Alt` again. There are commented out spots in the code where you can see I am trying to suppress this behavior, and I'm all over the target. I haven't found the proper combo to kill the issue.
2) sometimes releasing `Alt` to come out of the hotkey combo will turn off your ability to select. If this happens press `Alt` again.

