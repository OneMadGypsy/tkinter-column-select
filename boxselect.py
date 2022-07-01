#OneMadGypsy - box-selection features for tk.Text

import tkinter as tk, tkinter.font as tkf
from collections import namedtuple
from typing      import Iterable, Any
from dataclasses import dataclass, asdict
import math, re, tempfile, os

# event.state flags
SHIFT   = 0x000001
CONTROL = 0x000004 
BUTTON1 = 0x000100
ALT     = 0x020000

#caret width
INSWIDTH = 1

#drop insertion point
INSPNT = 'insertpoint'

#inline whitespace regex
ILWHITE = re.compile(r'[ \t]+')

# begin col/row, end col/row, (width or len), height
SelectBounds = namedtuple('SelectBounds', 'bc br ec er w h rv')

#default tk.Text **kwargs for this script
@dataclass 
class Text_t:
    font            :str  = '{Courier New} 14'
    selectforeground:str  = '#222222'
    selectbackground:str  = '#DDDDDD'
    insertwidth     :int  = INSWIDTH
    insertofftime   :int  = 300
    insertontime    :int  = 600
    insertbackground:str  = '#555555'
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
        #self.focus_set()
     
    #GEOMETRY
    #absolutely do NOT convert anything within this method to an `.index(...)`
    #some of the descriptions below may not exist yet
    def __bounds(self, b:str=None, e:str=None, ow:bool=False, rv:bool=None) -> SelectBounds:
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
            
        rv = rv if not (rv is None) else self.compare(self.__boxstart, '>', self.__boxend)
        
        #technically, `h` is always 1 less than the actual height
        #it's ok because everything starts by considering the first line
        #i.e. first_selected_line_number + `h` = the right number
        return SelectBounds(bc, br, ec, er, w, h, rv) 
    
    #this method could easily be renamed __drawrect
    #it tags __lbounds ranges and puts a multiline caret on whichever side makes sense
    def __bounds_range(self, tag, bo:int=0, eo:int=0, ao:bool=False):
        #hide real caret
        self['insertwidth'] = 0
                    
        if bnd:=self.__lbounds:
            b  , e   = [], []
            abo, aeo = int(bo*ao),int(eo*ao)
            for n in range(bnd.br, bnd.er+1):
                ch = (f'{n}.{bnd.ec+aeo}',f'{n}.{bnd.bc+abo}')
                #store beginning and end indexes
                b.append(f'{n}.{bnd.bc+bo}') #rv
                e.append(f'{n}.{bnd.ec+eo}') #1
                #yield row, begin column, end column
                yield n, bnd.bc+abo, bnd.ec+aeo
                #create caret
                self.__fauxcaret(ch[bnd.rv])
                
            #update real caret position
            self.caret = ch[bnd.rv]
            #config main faux-caret
            self.__fauxcaret(self.caret, main=True, cfg=True)
            #clear and draw tag
            self.tag_move(tag, b, e)
         
    #this is the "draw a caret only" version of __bounds_range
    #adv puts the caret at the next character
    def __typing_range(self, adv:bool=True):
        #hide real caret
        self['insertwidth'] = 0
        #stop blinking
        self.__blinkreset()
        #delete faux-carets
        for n in self.image_names(): self.delete(n)
        #destroy anything that is selected
        self.__cut()
        
        if b:=self.__lbounds:
            #type at multicaret
            for n in range(b.br, b.er+1): 
                #yield row, begin column
                yield n, b.bc
                #create caret
                self.__fauxcaret(f'{n}.{b.bc+adv}')
              
            #update bounds              
            self.__lbounds = self.__bounds(f'{b.br}.{b.bc+adv}', f'{b.er}.{b.bc+adv}', ow=True, rv=b.rv)
            #update real caret position
            self.caret = (self.__boxstart,self.__boxend)[b.rv]
            #config main faux-caret
            self.__fauxcaret(self.caret, main=True, cfg=True)
            #start blinking
            self.__blink()
              
    #virtual index
    def vindex(self, x:int, y:int) -> str:
        #what is the top visible row number
        r,_ = map(int, self.index('@0,0').split('.'))
        #figure out where we are from there
        r = round(y/self.__fh) + r
        c = math.ceil(x/self.__fw)
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
        self.config(font=font, tabs=self.__fw*4)
        self.__loadcarets()
          
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
        self.__blinkid     = None   #id of `.after`
        self.__blinksort   = None   #iterable of sorted faux-caret indexes
        self.__hotbox      = False  #shift and alt are pressed
        self.__hotboxfree  = True
        self.__hotboxinit  = False  #locks in box-select begin col and begin row bounds
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
        if ((self.__hotbox and self.__hotboxfree) or self.__selgrab) and (cmd=='tag') and args:
            if args[0] in ('add', 'remove'):
                if args[1]!='BOXSELECT':
                    return
         
        #proceed as normal
        try             : target = self.tk.call((self.__pxy, cmd) + args)#;print(cmd, args)
        except Exception: return
        
        return target   
    
    #FAUX-CARET
    def __loadcarets(self) -> None:
        #store insert on/off times for faux-caret `.after` calls
        self.__instime = (self['insertofftime'], self['insertontime'])
        
        fh = self.__fh    #font height from 'linespace'
        
        #make a temp xbm file
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.xbm', delete=False) as f:
            #create prettyprint xbm data
            xbmdata = ',\n\t'.join(','.join('0xFF' for _ in range(min(8, fh-(8*i)))) for i in range(math.ceil(fh/8)))
            #write xbm
            f.write((f"#define image_width {INSWIDTH}\n#define image_height {fh}\n"
                     "static unsigned char image_bits[] = {\n\t"
                     f'{xbmdata}}};').encode())
                     
        #load xbm files for faux-caret ~ they have to be in this order
        #this doesn't have a proper name because __fauxcaret entirely manages this
        self.__  = (tk.BitmapImage(file=f.name, foreground='#999999'),                   #shadow caret 
                    tk.BitmapImage(file=f.name, foreground=self['background']),          #off caret
                    tk.BitmapImage(file=f.name, foreground=self['insertbackground']))    #main caret  
        
        #delete file
        os.unlink(f.name)
    
    #faux-caret create or config
    def __fauxcaret(self, index:str, on:bool=True, main:bool=False, cfg:bool=False) -> None:
        (self.image_create, self.image_configure)[cfg](index, image=self.__[(main<<on)|(on^1)])
    
    
    #blink the faux-caret(s)
    def __blink(self, on:bool=True):
        #nothing to do
        if not self.__boxselect: return
        
        #so we only do this once per first blink
        if not self.__blinksort:
            #sort image indexes
            self.__blinksort = sorted((self.index(n) for n in self.image_names()), key=lambda i: float(i))
            
        if idx:=self.__blinksort:
            #flip `on`
            on = not on
            #consider direction in forward perspective
            fw = not self.__lbounds.rv
            #reconfigure all carets
            for i in idx: self.__fauxcaret(i, on=on, cfg=True)
            #reconfigure "active line" caret, if off it will assign off again
            self.__fauxcaret(idx[-fw], on=on, main=True, cfg=True)
            #schedule next call
            self.__blinkid = self.after(self.__instime[on], self.__blink, on)
            return
            
        raise ValueError('__blink: Nothing to sort!')
    
    #reset blink
    def __blinkreset(self) -> None:
        if not self.__blinkid is None:
            self['cursor'] = 'xterm'
            self.after_cancel(self.__blinkid)
            self.__blinksort = None
             
    #BOXSELECT
    #swap BOXSELECT for tk.SEL and config
    def __hotbox_release(self) -> None:         
        #reset state
        self.__hotboxinit = False 
        #unsuppresses all tags in .__proxy
        self.__hotbox     = False 
        self.__hotboxfree = False
        #replace BOXSELECT tags with tk.SEL
        self.tag_replace('BOXSELECT', tk.SEL)
        #start blink
        self.__blink()
    
    #reset box-select data    
    def __boxreset(self) -> None:
        #reset caret display width
        self['insertwidth'] = INSWIDTH
        #clean up box-select generated whitespace
        self.__boxclean()
        #turn off box-select
        self.__boxselect  = False
        #reset bounds
        self.__lbounds    = None
        #reset box start/end
        self.__boxstart   = None
        self.__boxend     = None
        #reset blink
        self.__blinkreset()
        self.__hotboxfree = True
        
    #remove any whitespace that box-select created  
    def __boxclean(self, bnd:SelectBounds=None) -> None:
        if bnd:=(bnd or self.__lbounds):
            #stop blinking
            self.__blinkreset()
            #delete faux-carets
            for n in self.image_names(): self.delete(n)
            #store current caret position
            p = self.caret
            for nr in range(bnd.br, bnd.er+1):
                b, e = f'{nr}.0', f'{nr}.end'
                #get entire row
                t  = self.get(b, e)
                #if the entire row is just space, get rid of the space
                #if box-select created it, we get rid of the whole row after we finish with space removal
                if not len(ILWHITE.sub('', t)): self.replace_text(b, e, '')
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
                #the one drawback to this is it automatically assumes there was never any empty lines at the end of the text
                #delete the last row until either it isn't blank or `nr` is exhausted
                while not (l:=len(self.get(f'{nr}.0', 'end-1c'))) and nr>=bnd.br:
                    self.delete(f'{nr-1}.end', 'end-1c')
                    nr-=1
                    self.caret = p 
     
    #update __lbounds (w)ith (g)rab (o)ffsets
    def __boxmove(self, wgo:bool=True) -> SelectBounds:
        if b:=self.__lbounds:
            r, c = map(int, self.caret.split('.'))
            #update bounds
            if self.__boxselect:
                r = r if not wgo else max(1, r+self.__hgrabofs)
                self.__lbounds = self.__bounds(f'{r}.{c}', f'{r+b.h}.{c+b.w}', ow=True, rv=b.rv)
            #normal select
            else:
                self.__lbounds = self.__bounds(f'{r}.{c}', self.index(f'{r}.{c}+{b.w}c'), ow=True, rv=b.rv)
                
        return self.__lbounds

    #CLIPBOARD
    #restore clipboard data to last clipboard
    def __restore_clipboard(self) -> None:
        if self.__lclipbd:
            self.clipboard_clear()
            self.clipboard_append(self.__lclipbd)

    #remove every selection-related thing 
    def __cut(self, p:str=None):
        #get selection ranges
        r = self.tag_ranges(tk.SEL)
        for i in range(0, len(r), 2):
            self.tag_remove(tk.SEL, *r[i:i+2])  #remove tk.SEL tag
            self.replace_text(*r[i:i+2], '')    #delete selected text
        self.caret = p or self.caret            #put the caret somewhere
        
    #move all selected text to clipboard
    #this is safe for regular selected text but designed for box-selected text
    def __copy(self) -> None:
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
    
    #EVENTS
    def __handler(self, event) -> None:
        if event.type == tk.EventType.KeyPress:
            if event.state & CONTROL:
                if event.keysym=='c':
                    #if not boxcopy, normal cut/copy/paste behaviors are used
                    self.__boxcopy = not self.__hotboxinit and self.__boxselect
                    
                    #BOXSELECT COPY(Cntl+c)
                    if self.__boxcopy:
                        self.__copy()
                        return 'break'
                        
                elif event.keysym=='x':
                    #if not boxcopy, normal cut/copy/paste behaviors are used
                    self.__boxcopy = not self.__hotboxinit and self.__boxselect
                    
                    #BOXSELECT CUT(Cntl+x)
                    if self.__boxcopy:
                        self.__copy()
                        self.__cut()
                        self.__boxreset()  
                        return 'break'
                          
                elif event.keysym=='v':
                    #BOXSELECT PASTE(Cntl+v)
                    if self.__boxcopy:
                        self.__cut() #if any
                        #set caret to begin position
                        if b:=self.__lbounds: self.caret = f'{b.br}.{b.bc}'
                        self.__paste()
                        self.__boxreset()    
                        return 'break'
                        
                return # get out of here before the next `if`
            
            elif event.keysym=='BackSpace':
                #BOXSELECT BackSpace
                if self.__boxselect:
                    #essentially, we are typing nothing
                    for _,_ in self.__typing_range(False): pass
                    return 'break'    
                return
                    
            #deselects and moves caret to the requested end of the box-selection
            #left places the caret at the start and right at the end
            elif event.keysym in ('Left','Right','KP_Left','KP_Right'):
                if bnd:=self.__lbounds:
                    #remove tk.SEL tag, if any
                    self.tag_move(tk.SEL)
                    #move caret in requested direction
                    b, e       = (self.__boxstart,self.__boxend)[::(-bnd.rv) or 1]
                    self.caret = e if 'Right' in event.keysym else b
                    #destroy bounds
                    self.__boxreset()
                    return 'break'
                return
            
            #Shift+Alt regardless of keypress order
            self.__hotbox = (event.keysym in ('Alt_L'  ,'Alt_R'  )) and (event.state & SHIFT) or \
                            (event.keysym in ('Shift_L','Shift_R')) and (event.state & ALT)
                               
            #BOXSELECT
            if self.__hotbox and self.__hotboxfree:
                if event.state & BUTTON1:
                    #box-select mousedown
                    if not self.__hotboxinit:
                        #turn on box-select switches
                        self.__boxselect  = True
                        self.__hotboxinit = True
                        #store last known 'insert' index (ie. NOT 'current')
                        self.__boxstart   = self.__linsert
                        return 'break'
                    
                    #box-select mousemove ~ via last keypress (shift or alt) constantly firing
                    #this index might not exist yet. passing it to `.index()` may destroy it
                    self.__boxend = self.vindex(event.x, event.y)
                    
                    #never use overwrite here, if you do you will lose the proper selection direction
                    if (nb:=self.__bounds(ow=False)) == (lb:=self.__lbounds): return
                        
                    #remove whitespace and carets, overwrite last bounds 
                    self.__boxclean()
                    self.__lbounds = nb
                    
                    for r, bc, ec in self.__bounds_range('BOXSELECT', bo=nb.rv, eo=1):
                        #true line end properties and difference from requested line end
                        le     = self.index(f'{r}.end')
                        lr, lc = map(int, le.split('.'))
                        h, w   = r-lr, ec-lc
                        #add lines/spaces, if necessary
                        if h>0: self.insert(f'{r-1}.end', '\n')
                        if w>0: self.insert(le, ' '*w)
                        
                    return 'break'
                        
                #box-select mouseup ~ deinit hotbox             
                if self.__hotboxinit: 
                    self.__hotbox_release()
                    return 'break'
                    
                #store 'insert' position before button1 press
                self.__linsert = self.caret
                return 'break'
            else:
                #BOX-TYPING
                if self.__boxselect and len(event.char):
                    #typing_range handles the faux-caret and bounds, we just need to insert
                    for r,c in self.__typing_range(): self.insert(f'{r}.{c}', event.char)  
                    return 'break'
                            
        elif event.type == tk.EventType.KeyRelease:
            if self.__hotboxinit: 
                self.__hotbox_release()
                return 'break'
            
        elif event.type == tk.EventType.ButtonPress:
            #get mouse index
            mse  = self.index('current') 
            
            #GRAB SELECTED
            #check if mouse index is within a selection
            if tk.SEL in self.tag_names(mse):
                #box-selection
                if b:=self.__lbounds:
                    #get mouse index row
                    r,_ = map(int, mse.split('.'))
                    #store horizontal grab offset
                    self.__hgrabofs = b.br-r
                #normal selection
                else:
                    #create bounds for the selection ~ overwrite boxstart/boxend with min/max indexes
                    self.__lbounds  = self.__bounds(*self.tag_bounds(tk.SEL), ow=True)
                    
                #flip tk.SEL to BOXSELECT
                self.tag_replace(tk.SEL, 'BOXSELECT')
                #turn off all tag add/remove except BOXSELECT in .__proxy
                self.__selgrab = True
                #store the grab position
                self.__linsert = mse
                #reset blink
                self.__blinkreset()
                    
            #if a selection is not under the mouse, reset
            elif self.__boxselect: 
                self.__boxreset()
        
        elif event.type == tk.EventType.Motion:
            #if a selection has been grabbed
            if self.__selgrab:
                #if you are where you started, then dragging is false
                self.__seldrag = self.caret != self.__linsert
                #cursor indicates state
                self['cursor'] = ('xterm', 'fleur')[self.__seldrag]
                self['insertwidth'] = INSWIDTH
                    
        elif event.type == tk.EventType.ButtonRelease:
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
                if bnd:=self.__boxmove(): # move bounds to current location
                    #COPY
                    self.__copy()
                    
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
                    
                    #remove box-select-generated whitespace and faux-caret(s) from __cut position
                    self.__boxclean(mc)
                    #PASTE COLUMN 
                    self.__paste()
                    #restore clipboard
                    self.__restore_clipboard()
                    #move bounds to caret
                    bnd  = self.__boxmove(False)
                    #we're just highlighting something that already exists and making carets
                    #bounds_range already does both of those things
                    for _,_,_ in self.__bounds_range(tk.SEL, eo=bnd.rv, ao=True): pass
                    ##start blink
                    self.__blink()
                            
  
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
    
    
