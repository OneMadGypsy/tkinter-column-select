#OneMadGypsy - box-selection features for tk.Text

import tkinter as tk, tkinter.font as tkf
from collections import namedtuple
from typing      import Iterable, Any
from dataclasses import dataclass, asdict
import math, re

# event.state flags
SHIFT   = 0x000001
CONTROL = 0x000004 
BUTTON1 = 0x000100
ALT     = 0x020000

#drop insertion point
INSPNT = 'insertpoint'

#inline whitespace regex
ILWHITE = re.compile(r'[ \t]+')

# begin col/row, end col/row, (width or len), height
SelectBounds = namedtuple('SelectBounds', 'bc br ec er w h')

#default tk.Text **kwargs for this script
@dataclass 
class Text_t:
    font            :str  = '{Courier New} 14'
    selectforeground:str  = '#222222'
    selectbackground:str  = '#DDDDDD'
    wrap            :str  = "none"
    exportselection :int  = 1
    takefocus       :int  = 1
    undo            :bool = True
    autoseparators  :bool = True
    maxundo         :int  = 32 #-1 for infinite


#EDITOR
class EditorText(tk.Text):
    # CARET POSITIONING
    @property
    def caret(self) -> str:
        return self.index('insert')

    @caret.setter
    def caret(self, index:str) -> None:
        self.mark_set('insert', index)
        self.focus_set()
     
    #GEOMETRY
    #absolutely do NOT convert anything within this method to an `.index(...)`
    #some of the descriptions below may not exist yet
    def __bounds(self, b:str=None, e:str=None, ow:bool=False) -> SelectBounds:
        b, e = b or self.__boxstart, e or self.__boxend
        #parse row/col positions
        b_ = map(int, b.split('.')) 
        e_ = map(int, e.split('.')) 
        
        if self.__boxselect:
            #row and col positions ~ min/max each
            (br,er),(bc,ec) = (sorted(x) for x in zip(b_,e_))
            #width, height 
            w, h = ec-bc, er-br
        #regular selection
        else:
            #row and col positions ~ min/max row
            (br,bc),(er,ec) = b_, e_
            (br,er)         = sorted((br,er))
            #len, height 
            w, h = len(self.get(f'{br}.{bc}', f'{er}.{ec}')), er-br
            
        #overwrite    
        if ow:
            self.__boxstart = f'{br}.{bc}'
            self.__boxend   = f'{er}.{ec}'
        
        #technically, `h` is always 1 less than the actual height
        #it's ok because everything starts by considering the first line
        #i.e. first_selected_line_number + `h` = the right number
        return SelectBounds(bc, br, ec, er, w, h) 
     
    #virtual index
    def vindex(self, x:int, y:int) -> str:
        #what is the top visible row number
        r,_ = map(int, self.index('@0,0').split('.'))
        #figure out where we are from there
        r = round(y/self.__fh) + r
        c = round(x/self.__fw)
        #final index ~ MUST NOT be converted to `.index()` as it probably doesn't exist yet
        #that's the whole point ~ this is returning where we would be IF every possible index was valid
        return f'{r}.{c}'
      
    #convenient
    def dlineinfo(self, index=tk.INSERT) -> tuple:
        self.update_idletasks()
        return super().dlineinfo(index)
    
    #TAGS
    # No exception .start, .end
    def tag_bounds(self, tag:str) -> tuple:
        if (tr:=self.tag_ranges(tag)) and len(tr)>1: 
            return map(str,(tr[0],tr[-1]))
        return None, None
       
    #replace all instances of `tag_in` with `tag_out`
    def tag_replace(self, tag_in:str, tag_out:str) -> None:
        r = self.tag_ranges(tag_in)
        #swap the tags
        for i in range(0, len(r), 2):
            self.tag_remove(tag_in , *r[i:i+2])
            self.tag_add   (tag_out, *r[i:i+2])
        #ensure the widget's full attention ~ it can get froggy
        self.focus_set()
           
    #remove all instances of a tag, and reassign it by `b` and `e` accordingly
    def tag_move(self, tag:str, b:Iterable=None, e:Iterable=None) -> None:
        x, y = self.tag_bounds(tag)
        
        if x and y: self.tag_remove(tag, x, y)
        
        if b and e:
            x = b if isinstance(b, (list,tuple)) else (b,)
            y = e if isinstance(e, (list,tuple)) else (e,)
            for b, e in zip(x,y):
                self.tag_add(tag, b, e)

    #TEXT
    #replace text ~ convenient, maybe
    def replace_text(self, b:str, e:str, text:str) -> None:
        self.delete(b, e)
        self.insert(b, text)
        
    #FONT
    def update_font(self, font:Iterable) -> None:
        self.__font = tkf.Font(font=font)
        self.__fw   = self.__font.measure(' ')
        self.__fh   = self.__font.metrics('linespace')
        self.config(font=font, tabs=self.__font.measure(' '*4))
       
    #CONSTRUCTOR
    def __init__(self, master, *args, **kwargs):
        tk.Text.__init__(self, *args, **{**asdict(Text_t()), **kwargs})
        
        #box-select tag
        self.tag_configure('BOXSELECT' , background=self['selectbackground'])
        
        #capture character width and height, primarily
        self.update_font(self['font'])
        
        #selection insertion point
        self.mark_set(INSPNT, '1.0')
        self.mark_gravity(INSPNT, tk.LEFT)
        
        #add listeners
        for evt in ('KeyPress','KeyRelease','ButtonPress-1','ButtonRelease-1','Motion','<Paste>'): 
            self.bind(f'<{evt}>', self.__handler)
        
        #features
        self.__boxselect   = False  #select text within a rect
        self.__boxcopy     = False  #cut/copy/paste with column behavior
        self.__selgrab     = False  #grab any selected data
        self.__seldrag     = False  #drag any selected data
        #vars
        self.__hotbox      = False  #shift and alt are pressed
        self.__mouseinit   = False  #locks in box-select begin col and begin row bounds
        self.__boxstart    = None   #box bounds start position
        self.__boxend      = None   #box bounds end position
        self.__hgrabofs    = None   #horizontal offset from 'current' to sel.start
        self.__linsert     = None   #last known 'insert' position ~ used while __hotbox or __selgrab is True
        self.__lbounds     = None   #last bounds that were applied
        self.__lclipbd     = ''     #back-up of last clipboard data
        
        #hijack tcl commands stream so we can pinpoint various commands
        name = str(self)
        self.__pxy = name + "_orig"
        self.tk.call("rename", name, self.__pxy)
        self.tk.createcommand(name, self.__proxy)
    
    #PROXY
    def __proxy(self, cmd, *args) -> Any:
        #suppress ALL tags except BOXSELECT from the moment the mouse is pressed
        #for hotkeys and dragging
        if (self.__hotbox or self.__selgrab) and (cmd=='tag') and args:
            if args[0] in ('add', 'remove'):
                if args[1]!='BOXSELECT':
                    return
         
        #proceed as normal
        try             : target = self.tk.call((self.__pxy, cmd) + args)#;print(cmd, args)
        except Exception: return
        
        return target   
    
    #BOXSELECT
    #swap BOXSELECT for tk.SEL and config
    def __hotswap(self) -> None:
        #unsuppresses all tags in .__proxy
        self.__hotbox    = False          
        #reset state
        self.__mouseinit = False 
        #replace BOXSELECT tags with tk.SEL
        self.tag_replace('BOXSELECT', tk.SEL)
        
        self.focus_set()
    
    #reset    
    def __boxreset(self) -> None:
        #clean up box-select generated whitespace
        self.__boxclean()
        #turn off box-select
        self.__boxselect = False
        #reset bounds
        self.__lbounds   = None
        
    #remove any whitespace that box-select created  
    def __boxclean(self, bnd:SelectBounds=None) -> None:
        if bnd:=(bnd or self.__lbounds):
            #store current caret position
            p = self.caret
            for nr in range(bnd.br, bnd.er+1):
                b, e = f'{nr}.0', f'{nr}.end'
                #get entire line
                t  = self.get(b, e)
                #if the entire line is just space, get rid of the space
                #if box-select created it, we get rid of the whole row after we finish with space removal
                if not len(ILWHITE.sub('', t)):
                    self.replace_text(b, e, '')
                else:
                    #strip only to the right of the column
                    t = t[bnd.ec:].rstrip()
                    #replace the right side with the rstripped right side text
                    self.replace_text(f'{nr}.{bnd.ec}', e, t)
                #put the caret back where it was
                self.caret = p  
                
            #the end of the entire text is the only place where box-select will create new lines
            #last row of entire text  
            r,_ = map(int, self.index('end-1c').split('.'))
            #if we are on the last row
            if nr == r:
                #delete the last row until either it isn't blank or `nr` is exhausted
                while not (l:=len(self.get(f'{nr}.0', 'end-1c'))) and nr>=bnd.br:
                    self.delete(f'{nr-1}.end', 'end-1c')
                    nr-=1
                    self.caret = p 
            #so things don't get froggy
            self.focus_set()
     
    #update __lbounds (w)ith (g)rab (o)ffsets
    def __boxmove(self, wgo:bool=True) -> SelectBounds:
        if b:=self.__lbounds:
            r, c = map(int, self.caret.split('.'))
            #update bounds
            if self.__boxselect:
                r = r if not wgo else max(1, r+self.__hgrabofs)
                self.__lbounds = self.__bounds(f'{r}.{c}', f'{r+b.h}.{c+b.w}', ow=True)
            #normal select
            else:
                self.__lbounds = self.__bounds(f'{r}.{c}', self.index(f'{r}.{c}+{b.w}c'), ow=True)
                
        return self.__lbounds

    #CLIPBOARD
    #restore clipboard data to last clipboard
    def __restore_clipboard(self) -> None:
        if self.__lclipbd:
            self.clipboard_clear()
            self.clipboard_append(self.__lclipbd)

    #remove every selection-related thing 
    def __cut(self, p:str=None):
        #make sure the widget is paying attention
        self.focus_set()
        #get selection ranges
        r = self.tag_ranges(tk.SEL)
        for i in range(0, len(r), 2):
            self.tag_remove(tk.SEL, *r[i:i+2])  #remove tk.SEL tag
            self.replace_text(*r[i:i+2], '')    #remove selected text
        self.caret = p or self.caret            #put the caret somewhere
        
    #move all selected text to clipboard
    #this is safe for regular selected text but designed for box-selected text
    def __copy(self) -> None:
        #make sure the widget is paying attention
        self.focus_set()
        #get selection ranges
        r = self.tag_ranges(tk.SEL)
        #compile clipboard data from ranges
        t = '\n'.join(self.get(*r[i:i+2]) for i in range(0,len(r),2))
        if t:
            #bkup, clear and populate clipboard
            #bkup used with drag to restore the clipboard after drop
            try               : self.__lclipbd = self.clipboard_get()
            except tk.TclError: self.__lclipbd = ''
            self.clipboard_clear()
            self.clipboard_append(t)

    #insert clipboard text
    def __paste(self, side:str=tk.LEFT) -> None:
        #get lines
        l = self.clipboard_get().split('\n')
        #get caret row, col
        r,c = map(int, self.caret.split('.'))
        #we can't go by columns due to tabs being possibly included
        x,_,_,_ = self.bbox(self.caret)
        #true single space character count from beginning of line to caret
        pc = int(x//self.__fw)
        
        #insert each line at an incrementing row index
        for i,t in enumerate(l):
            p = f'{r+i}.{c}'
            
            #if the row doesn't exist, create it
            if self.compare(p, '>=', 'end'): self.insert(tk.END, f'\n')
                
            #if the column doesn't exist, create it
            q = f'{r+i}.end'
            if self.compare(p, '>=', q) and i:
                #what's the difference in available and desired columns
                n = pc-int(self.index(q).split('.')[-1])
                #add enough space to keep us in line, and add the text while we are at it
                self.insert(q, f'{" "*(n)}{t}')
                continue
                    
            #insert (t)ext at (p)osition
            self.insert(p, t)
        
        #put the caret at the beginning
        if side==tk.LEFT: self.caret = f'{r}.{c}'
        #make sure the widget is paying attention
        self.focus_set()
    
    #EVENTS
    def __handler(self, event) -> None:
        if event.type == tk.EventType.KeyPress:
            if event.state & CONTROL:
                if event.keysym=='c':
                    #if not boxcopy, normal cut/copy/paste behaviors are used
                    self.__boxcopy = not self.__mouseinit and self.__boxselect
                    
                    #BOXSELECT COPY(Cntl+c)
                    if self.__boxcopy:
                        self.__copy()
                        return 'break'
                        
                elif event.keysym=='x':
                    #if not boxcopy, normal cut/copy/paste behaviors are used
                    self.__boxcopy = not self.__mouseinit and self.__boxselect
                    
                    #BOXSELECT CUT(Cntl+x)
                    if self.__boxcopy:
                        self.__copy()
                        self.__cut()
                        self.__boxreset()  
                        return 'break'
                          
                elif event.keysym=='v':
                    #BOXSELECT PASTE(Cntl+v)
                    if self.__boxcopy:
                        self.__cut()
                        #set caret to begin position
                        if b:=self.__lbounds: self.caret = f'{b.br}.{b.bc}'
                        self.__paste()
                        self.__boxreset()    
                        return 'break'
                return # get out of here before the next `if`
            
            elif event.keysym=='BackSpace':
                #BOXSELECT BackSpace
                if self.__boxselect:
                    self.__cut()
                    self.__boxreset()    
                    return 'break'
                return # get out of here before the next `if`
                    
            #deselects and moves caret to the requested end of the previous selection
            #left places the caret at the start and right at the end
            elif event.keysym in ('Left','Right','KP_Left','KP_Right'):
                #get tag .start, .end, if any
                b, e = self.tag_bounds(tk.SEL)
                #remove tk.SEL tag, if any
                self.tag_move(tk.SEL)
                #if any
                self.__boxreset()
                #set caret to begin or end position based on relevant key
                if b and e: self.caret = e if 'Right' in event.keysym else b
                return 'break'
        
                    
            #Shift+Alt regardless of keypress order
            self.__hotbox = (event.keysym in ('Alt_L'  ,'Alt_R'  )) and (event.state & SHIFT) or \
                            (event.keysym in ('Shift_L','Shift_R')) and (event.state & ALT)
                               
            #BOXSELECT
            if self.__hotbox:
                if event.state & BUTTON1:
                    #box-select mousedown
                    if not self.__mouseinit:
                        #turn on box-select switches
                        self.__boxselect   = True
                        self.__mouseinit = True
                        #store last known 'insert' index (ie. NOT 'current')
                        self.__boxstart  = self.__linsert
                        return 'break'
                    
                    #box-select mousemove ~ via last keypress (shift or alt) constantly firing
                    #MOTION events don't fire while keys are pressed
                    #this index might not exist yet passing it to `.index()` may destroy it
                    self.__boxend = self.vindex(event.x, event.y)
                    
                    #if the new bounds differ from the last bounds
                    if (nb:=self.__bounds()) != (lb:=self.__lbounds):
                        #remove added whitespace from last call
                        self.__boxclean()
                        
                        #prime begin and end ranges
                        b, e = [], []
                        
                        #store new ranges (and adjust rows/columns with whitespace, if necessary)
                        for n in range(nb.br, nb.er+1):
                            #store beginning and end indexes
                            b.append(f'{n}.{nb.bc}')
                            e.append(f'{n}.{nb.ec}')
                            
                            #get difference in selection width/height and available space
                            h = n-int(self.index(f'{n}.end').split('.')[0])
                            w = nb.ec-int(self.index(f'{n}.end').split('.')[-1])
                            
                            #add lines if necessary
                            if h>0: self.insert(f'{n-1}.end', '\n')
                            #add spaces, if necessary
                            if w>0: self.insert(f'{n}.end', ' '*w)
                        
                        #we DEFINITELY need to put this back
                        #after all that arbitrary insertion who knows where the caret is
                        #also the true end of the box might have been non-existant til now
                        self.caret = self.__boxend
                        #clear and draw BOXSELECT
                        self.tag_move('BOXSELECT', b, e)
                        #store new bounds
                        self.__lbounds = nb
                    
                    #suppress built-in behavior
                    return 'break'
                        
                #bake-in 'BOXSELECT' as tk.SEL                
                if self.__mouseinit: self.__hotswap()
                
                #store 'insert' position before button1 press
                self.__linsert = self.caret
                
                #suppress built-in behavior
                return 'break'
                    
        elif event.type == tk.EventType.KeyRelease:
            #"bake in" selection
            if self.__hotbox and (event.keysym in ('Alt_L','Alt_R','Shift_L','Shift_R')): 
                #swap BOXSELECT for tk.SEL
                self.__hotswap()
                #suppress built-in behavior
                return 'break'
            
        elif event.type == tk.EventType.ButtonPress:
            #wake up
            self.focus_set()
            #get mouse index
            m  = self.index('current') 
            
            #GRAB SELECTED
            #check if mouse index is within a selection
            if tk.SEL in self.tag_names(m):
                #if this is a normal selection
                if not self.__lbounds:
                    #create bounds for the selection ~ overwrite boxstart/boxend with min/max indexes
                    self.__lbounds  = self.__bounds(*self.tag_bounds(tk.SEL), ow=True)
                    
                #flip tk.SEL to BOXSELECT
                self.tag_replace(tk.SEL, 'BOXSELECT')
                #turn off all tag add/remove except BOXSELECT in .__proxy
                self.__selgrab = True
                #store the drag start position
                self.__linsert = self.caret
                
                if b:=self.__lbounds:
                    #get mouse index row
                    r,_ = map(int, m.split('.'))
                    #store horizontal grab offset
                    self.__hgrabofs = b.br-r
                    
            #if a selection is not under the mouse, reset
            elif self.__boxselect: self.__boxreset()
        
        elif event.type == tk.EventType.Motion:
            #have we moved enough to consider it dragging?
            if (not self.__seldrag) and self.__selgrab:
                #if we moved enough
                if self.caret != self.__linsert: 
                    #4-way arrows
                    self['cursor'] = 'fleur'
                    #turn on dragging state
                    self.__seldrag = True
                    
        elif event.type == tk.EventType.ButtonRelease:
            #wake up
            self.focus_set()
            
            #GRABBED
            if self.__selgrab:
                #turn on all tag add/remove in __proxy
                self.__selgrab = False
                
                #nothing to drop ~ abort
                if not self.__seldrag:
                    #remove selection, reset, abort
                    self.tag_move('BOXSELECT')
                    self.__boxreset()
                    return
                    
                #reset state
                self.__seldrag = False
                #regular cursor
                self['cursor'] = 'xterm'
                #flip BOXSELECT back to tk.SEL
                self.tag_replace('BOXSELECT', tk.SEL)
                
                #make a "multiline caret" to represent every row the deleted text was on, but with no width
                #this is so __boxclean works down every row in the caret column instead of regarding bounds that no longer exist
                #we have to get this data before we actually delete
                mc = None
                if self.__boxselect:
                    #get selection bounds
                    mc = self.__bounds(*self.tag_bounds(tk.SEL), ow=False)
                    #turn it into a "multiline caret"
                    mc = self.__bounds(f'{mc.br}.{mc.bc}', f'{mc.er}.{mc.bc}', ow=False)
                
                #DROP SELECTED
                #copy
                self.__copy()
                
                #cut and paste in a new location
                if bnd:=self.__boxmove(): # move bounds to current location
                    #CUT
                    #this tracks any effect a deletion has on where we are trying to drop this
                    self.mark_set(INSPNT, (self.caret, f'{bnd.br}.{bnd.bc}')[self.__boxselect])
                    #delete selection and move caret to insertion point
                    self.__cut(INSPNT)
                    
                    #PASTE NORMAL
                    if not self.__boxselect:             
                        #insertion point
                        ip = self.caret
                        #trigger built-in paste
                        self.event_generate('<<Paste>>')
                        #the caret is always at the end of a regular paste
                        self.__lbounds = self.__bounds(ip, self.caret, ow=True)
                        #clear and draw tk.SEL   
                        self.tag_move(tk.SEL, ip, self.caret)
                        return 
                    
                    #remove box-select-generated whitespace from __cut position
                    self.__boxclean(mc)
                    
                    #PASTE COLUMN 
                    self.__paste()
                    #restore clipboard
                    self.__restore_clipboard()
                    #move bounds to caret ~ the caret is always at the beginning of a column-paste
                    bnd  = self.__boxmove(False)
                    #compile new ranges
                    b, e = [], []
                    for n in range(bnd.br, bnd.er+1):
                        b.append(f'{n}.{bnd.bc}')
                        e.append(f'{n}.{bnd.ec}')
                    #clear and draw tk.SEL  
                    self.tag_move(tk.SEL, b, e)
                            
  
#example  
ROWS = 4
if __name__ == '__main__':
    class App(tk.Tk):
        def __init__(self, *args, **kwargs):
            tk.Tk.__init__(self, *args, **kwargs)
            #config cell
            self.columnconfigure(0, weight=1)
            self.rowconfigure   (0, weight=1)
            #instantiate editor
            (ed := EditorText(self)).grid(sticky='nswe')
            #create a playground to test column select features ~ last column is empty on purpose
            ed.insert(tk.END, f'aaa | bbb | ccc | ddd | eee | fff | ggg | hhh ||\n'*ROWS)
    #run        
    App().mainloop()

