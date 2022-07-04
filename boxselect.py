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

# begin col/row, end col/row, (width or len), height, reverse, up
SelectBounds = namedtuple('SelectBounds', 'bc br ec er w h dn rt')

#swatches
BG      = '#181818' #text background
FG      = '#DDDDEE' #all foregrounds and caret color
SEL_BG  = '#383838' #select background
SDW_CT  = '#999999' #shadow caret color


#default tk.Text **kwargs for this script
@dataclass 
class Text_t:
    font            :str  = '{Courier New} 14'
    background      :str  = BG
    foreground      :str  = FG
    selectforeground:str  = FG
    selectbackground:str  = SEL_BG
    insertwidth     :int  = INSWIDTH
    insertofftime   :int  = 300
    insertontime    :int  = 600
    insertbackground:str  = FG #caret color
    wrap            :str  = "none"
    exportselection :int  = 1
    takefocus       :int  = 1
    undo            :bool = True
    autoseparators  :bool = True
    maxundo         :int  = 32 #-1 for infinite


#EDITOR
class BoxSelectText(tk.Text):
    ''' NICETIES '''
    # CARET POSITIONING
    @property
    def caret(self) -> str: return self.index('insert')

    @caret.setter
    def caret(self, index:str) -> None: self.mark_set('insert', index)
    
    # TEXT    
    @property
    def text(self) -> str: return self.get('1.0', f'{tk.END}-1c')

    @text.setter
    def text(self, text:str) -> None: self.delete('1.0', tk.END); self.insert('1.0', text) 
      
    #replace text
    def replace_text(self, b:str, e:str, text:str) -> None:
        self.delete(b, e)
        self.insert(b, text)
        
    #append text
    def append_text(self, text:str) -> None:
        self.insert(f'{tk.END}-1c', text)
        
    # LINE
    def dlineinfo(self, index=tk.INSERT) -> tuple:
        self.update_idletasks()
        return super().dlineinfo(index)
    
    ''' ENGINE '''       
    #POSITIONING
    #absolutely do NOT convert anything within this method to an `.index(...)`
    #some of the descriptions below may not exist yet
    def __bounds(self, b:str=None, e:str=None, dn:bool=None, rt:bool=None, ow:bool=False) -> SelectBounds:
        b, e = (b or self.__boxstart), (e or self.__boxend)
        
        #parse row/col positions
        b_ = [*map(int, b.split('.'))]
        e_ = [*map(int, e.split('.'))]
        
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
         
        #selection direction
        dn = (b_[0]<e_[0]) if dn is None and (b_ and e_) else dn
        rt = (b_[1]<e_[1]) if rt is None and (b_ and e_) else rt
            
        #`h` is actually a count of how many lines come after the first one
        return SelectBounds(bc, br, ec, er, w, h, dn, rt) 
    
    #"DRAW_RECT" (essentially)
    #tags __lbounds ranges and puts a multiline caret on whichever side makes sense
    #`ao` determines if (b)egin(o)ffset and (e)nd(o)ffset get applied to everything(True) or just begin/end indexes(False)
    def __bounds_range(self, tag, bo:int=0, eo:int=0, ao:bool=False):
        #hide real caret
        self['insertwidth'] = 0
                    
        if bnd:=self.__lbounds:
            #precalculate begin/end offsets with (a)ll(o)ffsets 
            abo, aeo = int(bo*ao)     , int(eo*ao)
            #add offsets to begin/end indexes
            abc, aec = f'{bnd.bc+abo}', f'{bnd.ec+aeo}'
            #prime begin, end ranges
            b,e = [], []
            #get last row number
            r,_ = map(int, self.index(f'{tk.END}-1c').split('.'))
            
            for n in range(bnd.br, bnd.er+1):
                #if we are not trying to exceed the last usable row
                if n<=r:
                    #store beginning and end indexes
                    b.append(f'{n}.{bnd.bc+bo}')
                    e.append(f'{n}.{bnd.ec+eo}')
                    
                    yield n, bnd.bc+abo, bnd.ec+aeo                 #row, begin column, end column
                    #create caret
                    i = self.__index(f'{n}.{abc}',f'{n}.{aec}',bnd.dn, bnd.rt)
                    self.__fauxcaret(i)
                
            self.caret = self.__index(f'{bnd.br}.{abc}',f'{bnd.er}.{aec}', bnd.dn, bnd.rt)
            self.__fauxcaret(self.caret, main=True, cfg=True)       #config main faux-caret
            self.tag_move(tag, b, e)                                #clear and draw tag
         
    #this is the "draw a multiline-caret" version of __bounds_range (above)
    #adv puts the caret adv amount of characters from the current column. this can be negative, and will be for `BackSpace`
    def __typing_range(self, adv:int):
        self['insertwidth'] = 0                              #hide real caret
        self.__blinkreset()
        
        for n in self.image_names(): self.delete(n)          #delete faux-carets
        #if there was something to cut, and adv is negative, stop the caret from retreating
        if self.__cut() and adv<0: adv=0
        
        if bnd:=self.__lbounds:
            #type at multiline-caret
            for n in range(bnd.br, bnd.er+1): 
                yield n, bnd.bc, bnd.ec, adv                 #row, begin, column, adv
                self.__fauxcaret(f'{n}.{bnd.bc+adv}')        #create caret
              
            #begin/end indexes ~ we need this more than once
            i = (f'{bnd.br}.{bnd.bc+adv}', f'{bnd.er}.{bnd.bc+adv}')
            self.__lbounds = self.__bounds(*i, ow=True, dn=bnd.dn, rt=bnd.rt)
            self.caret = self.__index(*i, bnd.dn, bnd.rt)
            self.__fauxcaret(self.caret, main=True, cfg=True) #config main faux-caret
            self.__blink()
              
    #virtual index
    def vindex(self, x:int, y:int) -> str:
        #for determining how to snap x
        rt = bnd.rt if (bnd:=self.__lbounds) and not (None in bnd) else 1
        #what are the top-left visible row,col numbers
        r,c = map(int, self.index('@0,0').split('.'))
        
        #figure out where we are virtually
        r = round((y-(self.__fh/2))/self.__fh) + r
        c = (math.floor,math.ceil)[rt](x/self.__fw) + c
        
        #return where we would be if every possible index was valid
        return f'{max(r,1)}.{max(c,0)}'
    
    #box-select faux-caret attaches to mouse cursor side of selection, and main faux-caret follows mouse cursor
    def __index(self, start:str, end:str, dn:bool, rt:bool) -> str:
        r, c = zip(map(int, start.split('.')), map(int, end.split('.')))
        return f'{r[dn]}.{c[rt]}'
  
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
           
    #move all instances of a tag to a new location
    def tag_move(self, tag:str, b:Iterable=None, e:Iterable=None) -> None:
        x, y = self.tag_bounds(tag)
        
        if x and y: self.tag_remove(tag, x, y)
        
        if b and e:
            x = b if isinstance(b, (list,tuple)) else (b,)
            y = e if isinstance(e, (list,tuple)) else (e,)
            for b, e in zip(x,y):
                self.tag_add(tag, b, e)

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
        self.__p = self._w + "_orig"
        self.tk.call("rename", self._w, self.__p)
        self.tk.createcommand(self._w, self.__proxy)
         
    #PROXY
    def __proxy(self, cmd, *args) -> Any:
        #boxselect and dragging only allow the BOXSELECT tag from the moment the mouse is pressed
        if ((self.__hotbox and self.__hotboxfree) or self.__selgrab) and (cmd=='tag') and args:
            if args[0] in ('add', 'remove'):
                if args[1]!='BOXSELECT': return
        
        #the rest of the time
        try             : target = self.tk.call((self.__p, cmd) + args)#;print(cmd, args)
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
        #this doesn't have a proper name because __fauxcaret manages this entirely, and it's existance should otherwise be ignored
        self.__  = (tk.BitmapImage(file=f.name, foreground=SDW_CT),                      #shadow caret 
                    tk.BitmapImage(file=f.name, foreground=self['background']),          #off caret
                    tk.BitmapImage(file=f.name, foreground=self['insertbackground']))    #main caret  
        
        #delete file
        os.unlink(f.name)
    
    #faux-caret create or config
    def __fauxcaret(self, index:str, on:bool=True, main:bool=False, cfg:bool=False) -> None:
        (self.image_create, self.image_configure)[cfg](index, image=self.__[(main<<on)|(on^1)])
    
    #blink the faux-caret(s)
    def __blink(self, on:bool=True):
        if not self.__boxselect: return #nothing to do
        
        #so we only do this once per first blink
        if not self.__blinksort:
            self.__blinksort = sorted((self.index(n) for n in self.image_names()), key=lambda i: float(i))
            
        if idx:=self.__blinksort:
            if bnd:=self.__lbounds:
                on = not on
                #reconfigure all carets
                for i in idx: self.__fauxcaret(i, on=on, cfg=True)  
                #reconfigure "active line" caret, if off it will assign off again
                i = self.__index(idx[0], idx[-1], bnd.dn, bnd.rt)
                self.__fauxcaret(i, on=on, main=True, cfg=True)
                #schedule next call
                self.__blinkid = self.after(self.__instime[on], self.__blink, on)
                return
            
        raise ValueError('__blink: Nothing to sort!')
    
    #reset blink data
    def __blinkreset(self) -> None:
        if not (self.__blinkid is None):
            self.after_cancel(self.__blinkid)
            self.__blinksort = None
            self.__blinkid   = None
            self['cursor']   = 'xterm'
             
    #BOXSELECT
    #swap BOXSELECT for tk.SEL and config
    def __hotbox_release(self, state:int=0) -> None:
        self.__hotboxinit = False 
        self.__hotbox     = False #unsuppresses all tags in .__proxy
        self.__hotboxfree = False
        self.tag_replace('BOXSELECT', tk.SEL)
        self.__blink()
    
    #reset box-select data    
    def __boxreset(self) -> None:
        self['insertwidth'] = INSWIDTH #reset caret display width
        self.tag_move(tk.SEL)
        self.__boxclean()
        self.__blinkreset()
        self.__boxselect  = False
        self.__lbounds    = None
        self.__boxstart   = None
        self.__boxend     = None
        self.__hotboxfree = True       #allows box-select hotkeys
        
    #remove any whitespace that box-select created  
    def __boxclean(self, bnd:SelectBounds=None) -> None:
        if bnd:=(bnd or self.__lbounds):
            self.__blinkreset()
            for n in self.image_names(): self.delete(n) #delete faux-carets
            p = self.caret
            for nr in range(bnd.br, bnd.er+1):
                b, e = f'{nr}.0', f'{nr}.end'
                t  = self.get(b, e) #get entire row
                #if the entire row is just whitespace, get rid of the whitespace
                if not len(ILWHITE.sub('', t)): self.replace_text(b, e, '')
                else:
                    #strip only to the right of the column
                    self.replace_text(f'{nr}.{bnd.ec}', e, t[bnd.ec:].rstrip())
            self.caret = p  

    #update __lbounds (w)ith (g)rab (o)ffsets
    def __boxmove(self, wgo:bool=True) -> SelectBounds:
        if b:=self.__lbounds:
            r, c = map(int, self.caret.split('.'))
            #update bounds
            if self.__boxselect:
                r = r if not wgo else max(1, r+self.__hgrabofs)
                self.__lbounds = self.__bounds(f'{r}.{c}', f'{r+b.h}.{c+b.w}', ow=True, dn=b.dn, rt=b.rt)
            #normal select
            else:
                self.__lbounds = self.__bounds(f'{r}.{c}', self.index(f'{r}.{c}+{b.w}c'), dn=b.dn, rt=b.rt)
                
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
        return len(r)
        
    #move all selected text to clipboard
    #this is safe for regular selected text but designed for box-selected text
    def __copy(self) -> None:
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
    def __paste(self) -> None:
        l = self.clipboard_get().split('\n')    #get lines
        r,c = map(int, self.caret.split('.'))   #get caret row, col
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
        
        self.caret = f'{r}.{c}' #put the caret at the top-left of the paste
    
    #EVENTS
    def __handler(self, event) -> None:
        if event.type == tk.EventType.KeyPress:
            if event.state & CONTROL:
                if   event.keysym=='c':
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
                
                return
            
            elif event.keysym=='BackSpace':
                #BOXSELECT BackSpace
                if self.__boxselect:
                    for r,bc,ec,adv in self.__typing_range(-1):
                        if adv<0: self.delete(f'{r}.{bc-1}', f'{r}.{ec}')
                    return 'break'    
                return
                    
            #deselects and moves caret to the requested end of the box-selection
            #left places the caret at the start and right at the end
            elif event.keysym in ('Left','Right','KP_Left','KP_Right'):
                if bnd:=self.__lbounds:
                    self.tag_move(tk.SEL)
                    #move caret in requested direction
                    b, e       = (self.__boxstart,self.__boxend)[::(-bnd.rv) or 1]
                    self.caret = e if 'Right' in event.keysym else b
                    #destroy bounds
                    self.__boxreset()
                    return 'break'
                return
            
            #if event.keysym in ('Alt_L', 'Alt_R') and not (event.state&ALT): 
                # one alt press converts it's state to 0. that pauses the caret and turns off selecting 
                # That doesn't work at all for what we want, so we kill it before that point
                #return 'break'
            
            #Shift+Alt regardless of keypress order
            self.__hotbox = (event.keysym in ('Alt_L'  ,'Alt_R'  )) and (event.state & SHIFT) or \
                            (event.keysym in ('Shift_L','Shift_R')) and (event.state & ALT)
                               
            #BOXSELECT
            if self.__hotbox:
                if event.state & BUTTON1 and self.__hotboxfree:
                    #box-select mousedown
                    if not self.__hotboxinit:
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
                    
                    for r, bc, ec in self.__bounds_range('BOXSELECT', bo=not nb.rt, eo=1):
                        _, lc = map(int, self.index(f'{r}.end').split('.'))
                        #add columns if necessary
                        self.insert(f'{r}.{ec}', ' '*max(0, ec-lc))
                        
                    return 'break'
                        
                #box-select mouseup ~ deinit hotbox             
                if self.__hotboxinit: 
                    self.__hotbox_release(event.state)
                    return 'break'
                    
                #store 'insert' position before button1 press
                self.__linsert  = self.caret
                return 'break'
            else:
                #BOX-TYPING
                if self.__boxselect and len(event.char):
                    #typing_range handles the faux-caret and bounds, we just need to insert
                    for r,c,_,_ in self.__typing_range(1): self.insert(f'{r}.{c}', event.char)  
                    return 'break'
                            
        elif event.type == tk.EventType.KeyRelease:
            if self.__hotboxinit: 
                self.__hotbox_release(event.state)
                return 'break'
            #meh 
            if event.keysym in ('Alt_L', 'Alt_R') and not (event.state&ALT): 
                # one alt press converts it's state to 0. that pauses the caret and turns off selecting 
                # That doesn't work at all for what we want, so we kill it before that point
                return 'break'
            
        elif event.type == tk.EventType.ButtonPress:
            mse  = self.index('current') #get mouse index
            
            #GRAB SELECTED
            #check if mouse index is within a selection
            if tk.SEL in self.tag_names(mse):
                #box-selection
                if b:=self.__lbounds:
                    r,_ = map(int, mse.split('.')) #get mouse index row
                    self.__hgrabofs = b.br-r       #store horizontal grab offset
                #normal selection
                else:
                    #create bounds for the selection ~ overwrite boxstart/boxend with min/max indexes
                    self.__lbounds = self.__bounds(*self.tag_bounds(tk.SEL), ow=True)
                    
                self.tag_replace(tk.SEL, 'BOXSELECT')
                self.__selgrab = True    #only allow BOXSELECT tag in .__proxy
                self.__linsert = mse     #store the grab position
                self.__blinkreset()
                    
            #if a selection is not under the mouse, reset
            elif self.__boxselect: self.__boxreset()
        
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
                self['cursor'] = 'xterm'
                
                #nothing to drop ~ abort
                if not self.__seldrag:
                    self.tag_move('BOXSELECT')
                    self.__boxreset()
                    return
                    
                self.__seldrag = False
                self.tag_replace('BOXSELECT', tk.SEL)
                
                #make a "multiline caret" to represent every row the deleted text was on, but with no width
                #this is so __boxclean works down every row in the caret column instead of regarding bounds that no longer exist
                #we have to get this data before we actually delete
                mc = None
                if self.__boxselect:
                    mc = self.__bounds(*self.tag_bounds(tk.SEL), ow=False)
                    mc = self.__bounds(f'{mc.br}.{mc.bc}', f'{mc.er}.{mc.bc}', ow=False)
                
                #DROP SELECTED                                  
                if bnd:=self.__boxmove(): # move bounds to current location
                    #COPY
                    self.__copy()
                    
                    #CUT
                    #this tracks any effect a deletion has on where we are trying to drop this
                    self.mark_set(INSPNT, (self.caret, f'{bnd.br}.{bnd.bc}')[self.__boxselect])
                    self.__cut(INSPNT) #delete selection and move caret to insertion point
                    
                    #PASTE NORMAL
                    if not self.__boxselect:
                        ip = self.caret
                        self.event_generate('<<Paste>>')
                        #the caret is always at the end of a regular paste
                        self.__lbounds = self.__bounds(ip, self.caret, ow=True)
                        self.tag_move(tk.SEL, ip, self.caret) #clear and draw tk.SEL
                        return 
                    
                    self.__boxclean(mc)
                    #PASTE COLUMN 
                    self.__paste()
                    self.__restore_clipboard()
                    bnd  = self.__boxmove(False) #move bounds to caret
                    #we're just highlighting something that already exists and making carets
                    #bounds_range already does both of those things
                    for _,_,_ in self.__bounds_range(tk.SEL, eo=not bnd.rt, ao=True): pass
                    self.__blink()
                            

#example 
if __name__ == '__main__':
    ROWS = 20
    class App(tk.Tk):
        def __init__(self, *args, **kwargs):
            tk.Tk.__init__(self, *args, **kwargs)
            self.columnconfigure(0, weight=1)
            self.rowconfigure   (0, weight=1)
            #instantiate editor
            (bst := BoxSelectText(self)).grid(sticky='nswe')
            #columnar text
            cols = ''.join(f'| {chr(o)*3} |' for o in range(97,123))
            full = '\n'.join(cols for _ in range(ROWS))
            #create a playground to test column select features
            bst.text = f'{full}\n\n\n{full}'
    #run        
    App().mainloop()

