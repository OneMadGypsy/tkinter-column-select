import tkinter as tk, tkinter.font as tkf
from collections import namedtuple
from typing      import Iterable, Any
from dataclasses import dataclass, asdict
import math, re, tempfile, os

#event.state flags
SHIFT    = 0x000001
CONTROL  = 0x000004 
BUTTON1  = 0x000100
ALT      = 0x020000
ARROWKEY = 0x040000
ALTSHIFT = ALT|SHIFT

#swatches
BG       = '#181818' #text background
ACT_BG   = '#1f1f28' #active line background
FG       = '#CFCFEF' #all foregrounds and caret color
SEL_BG   = '#383848' #select background
SDW_CT   = '#68689F' #shadow caret color

#vars
INSWIDTH = 1                      #caret width
INSPNT   = 'insertpoint'          #drop insertion point
ILWHITE  = re.compile(r'[ \t]+')  #inline whitespace regex

#arrows ~ for various key conditions
HARROWS  = ('Left','KP_Left','Right','KP_Right')
VARROWS  = ('Up','KP_Up','Down','KP_Down')
ARROWS   = HARROWS+VARROWS
ALTS     = ('Alt_L', 'Alt_R')
SHIFTS   = ('Shift_L', 'Shift_R')
ALTSHIFTS= ALTS+SHIFTS

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


#this adds some extra generic behavior to tk.Text, and automates it's config to our purposes
#it's turned into it's own thing so we can get generic scripts out of the box-select code
class Textra(tk.Text): 
    #CARET POSITIONING
    @property
    def caret(self) -> str: return self.index('insert')

    @caret.setter
    def caret(self, index:str) -> None: self.mark_set('insert', index)
    
    #TEXT    
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
        
    #LINE
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
           
    #move all instances of a tag to a new location
    #acts as `tag_remove()` when `b` and/or `e` are None
    def tag_move(self, tag:str, b:Iterable=None, e:Iterable=None) -> None:
        x, y = self.tag_bounds(tag)
        
        if x and y: self.tag_remove(tag, x, y)
        
        if b and e:
            x = b if isinstance(b, (list,tuple)) else (b,)
            y = e if isinstance(e, (list,tuple)) else (e,)
            for b, e in zip(x,y):
                self.tag_add(tag, b, e)
    
    #CONSTRUCTOR
    def __init__(self, master, *args, **kwargs):
        tk.Text.__init__(self, master, *args, **{**asdict(Text_t()), **kwargs})


#backbone of the entire operation
#begin col/row, end col/row, (width or len), height, down, right
SelectBounds = namedtuple('SelectBounds', 'bc br ec er w h dn rt')
    

#BOX-SELECT
class BoxSelectText(Textra):
    #POSITIONING
    #create bounds
    def __bounds(self, b:str=None, e:str=None, dn:bool=None, rt:bool=None, ow:bool=False) -> SelectBounds:
        if (b:=(b or self.__boxstart)) and (e:=(e or self.__boxend)):
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
        return None
    
    #selection bounds manager
    def __bounds_range(self, tag, bo:int=0, eo:int=0, ao:bool=False):
        self['insertwidth'] = 0
                    
        if bnd:=self.__lbounds:
            bc, ec = bnd.bc+int(bo*ao), bnd.ec+int(eo*ao)            #add offsets to begin/end column indexes if 'ao'
            lr, _  = map(int, self.index(f'{tk.END}-1c').split('.')) #get last row number
            
            b,e = [], []                                            
            for r in range(bnd.br, bnd.er+1):
                #if we are not trying to exceed the last usable row
                if r<=lr:  
                    b.append(f'{r}.{bnd.bc+bo}') #store begin/end indexes
                    e.append(f'{r}.{bnd.ec+eo}')
                    
                    #row, begin column, end column
                    yield r, bc, ec              
                        
                    #create caret
                    self.__fauxcaret(self.__sindex(f'{r}.{bc}',f'{r}.{ec}', bnd.dn, bnd.rt))
                
            self.caret = self.__sindex(f'{bnd.br}.{bc}',f'{bnd.er}.{ec}', bnd.dn, bnd.rt)
            self.__fauxcaret(self.caret, main=True, cfg=True)
            self.set_activeline()
            self.tag_move(tag, b, e)
         
    #multiline-caret bounds manager
    def __typing_range(self, adv:int):
        self['insertwidth'] = 0
        
        #delete faux-carets
        self.__blinkreset()
        for n in self.image_names(): self.delete(n)                 
        
        #if there was something to cut, and adv is negative, stop the caret from retreating
        if self.__cut() and adv<0: adv=0
        
        if bnd:=self.__lbounds:
            bc = bnd.bc+adv
            
            #type at multiline-caret
            for r in range(bnd.br, bnd.er+1): 
                #row, begin column, advance
                yield r, bc, adv                       
                self.__fauxcaret(f'{r}.{bc}')
              
            #begin/end indexes
            i = (f'{bnd.br}.{bc}', f'{bnd.er}.{bc}')
            self.__lbounds = self.__bounds(*i, bnd.dn, bnd.rt, ow=True)
            self.caret     = self.__sindex (*i, bnd.dn, bnd.rt)
            self.__fauxcaret(self.caret, main=True, cfg=True)
            self.set_activeline()
            self.__blink()
          
    #arrow index
    def __aindex(self, sym:str) -> str:
        r, c = map(int, self.caret.split('.'))
        for k,(r2,c2) in self.__arrows.items():
            if k in sym:
                r += r2; c += c2
                self.caret = f'{max(1,r)}.{max(0,c)}'
                return self.caret
        return None
    
    #virtual index
    def __vindex(self, x:int, y:int) -> str:
        #for determining how to horizontally snap caret
        rt = bnd.rt if (bnd:=self.__lbounds) and not (None in bnd) else 1
        #the top-left visible row,col numbers
        r,c = map(int, self.index('@0,0').split('.'))
        
        #figure out where we are virtually
        r = round(y/self.__fh-0.50) + r
        c = (math.floor,math.ceil)[rt](x/self.__fw) + c
        
        #where we would be if every possible index was valid
        return f'{max(r,1)}.{max(c,0)}'
    
    #snap index
    def __sindex(self, start:str, end:str, dn:bool, rt:bool) -> str:
        r, c = zip(map(int, start.split('.')), map(int, end.split('.')))
        return f'{r[dn]}.{c[rt]}'
       
    #CONSTRUCTOR
    def __init__(self, master, *args, **kwargs):
        Textra.__init__(self, master, *args, **kwargs)
        
        #box-select tag
        self.tag_configure('BOXSELECT'  , background=self['selectbackground'])
        self.tag_configure('ACTIVELINE' , background=ACT_BG)
        
        #capture character width and height, make faux-carets for this font height
        self.update_font(self['font'])
        
        #selection insertion point
        self.mark_set(INSPNT, '1.0')
        self.mark_gravity(INSPNT, tk.LEFT)
        
        #add listeners
        for evt in ('KeyPress','KeyRelease','ButtonPress-1','ButtonRelease-1','Motion'):
            self.bind(f'<{evt}>', self.__handler)
        
        #features
        self.__boxselect   = False  #select text within a rect
        self.__boxcopy     = False  #cut/copy/paste with column behavior
        self.__selgrab     = False  #grab any selected data
        self.__seldrag     = False  #drag any selected data
        #vars
        self.__boxstart    = None   #box bounds start position
        self.__boxend      = None   #box bounds end position
        self.__vgrabofs    = None   #vertical offset from 'current' to sel.start
        self.__linsert     = None   #last known 'insert' position ~ used while __as or __selgrab is True
        self.__lbounds     = None   #last bounds that were applied
        self.__lclipbd     = ''     #back-up of last clipboard data
        
        self.__as_reset()           #prime ALT+SHIFT properties
        self.__blinkreset()         #prime blink properties
        
        #arrow key movement for arrow-key-box-select
        self.__arrows = {'Down':( 1,0),'Right':(0, 1),
                         'Up'  :(-1,0),'Left' :(0,-1)}
        
        #hijack tcl commands stream so we can pinpoint various commands
        self.__p = self._w + "_orig"
        self.tk.call("rename", self._w, self.__p)
        self.tk.createcommand(self._w, self.__proxy)
         
    #PROXY
    def __proxy(self, cmd, *args) -> Any:
        #boxselect and dragging only allow the BOXSELECT and ACTIVELINE tags from the moment the mouse is pressed
        if ((self.__as and self.__as_free) or self.__selgrab) and (cmd=='tag') and args:
            if args[0] in ('add', 'remove'):
                if not args[1] in ('BOXSELECT','ACTIVELINE'): 
                    return
        
        #the rest of the time
        try             : target = self.tk.call((self.__p, cmd) + args)#;print(cmd, args)
        except Exception: return
        
        return target   
        
    def set_activeline(self):
        r,_ = map(int, self.caret.split('.'))
        self.tag_move('ACTIVELINE', f'{r}.0', f'{r+1}.0')
        self.tag_lower('ACTIVELINE')
            
    
    #FONT
    def update_font(self, font:Iterable) -> None:
        self.__font = tkf.Font(font=font)
        self.__fw   = self.__font.measure(' ')
        self.__fh   = self.__font.metrics('linespace')
        self.config(font=font, tabs=self.__fw*4)
        #create faux-carets for this font height
        self.__loadcarets()
     
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
                i = self.__sindex(idx[0], idx[-1], bnd.dn, bnd.rt)
                self.__fauxcaret(i, on=on, main=True, cfg=True)
                #schedule next call
                self.__blinkid = self.after(self.__instime[on], self.__blink, on)
                return
            
        #raise ValueError('__blink: Nothing to sort!')
    
    #reset blink data
    def __blinkreset(self) -> None:
        try             : self.after_cancel(self.__blinkid) if not (self.__blinkid is None) else None
        except Exception: pass
        
        self.__blinkid   = None
        self.__blinksort = None
        self['cursor']   = 'xterm'
       
    #ALT+SHIFT
    def __as_reset(self) -> None:
        self.__as        = False #unsuppresses all tags in .__proxy
        self.__as_free   = True  #allows ALT+SHIFT hotkey 
        self.__as_commit = False
        self.__as_arrow  = False
        self.__as_mouse  = False
          
    def __as_release(self, state:int=0) -> None:
        self.__as_reset()
        self.__as_free = not self.__boxselect #adjust
        self.tag_replace('BOXSELECT', tk.SEL)
        self.__blink()
        
    #BOXSELECT
    #reset box-select data    
    def __boxreset(self) -> None:
        self['insertwidth'] = INSWIDTH #reset caret display width
        self.tag_move(tk.SEL)          #delete tk.SEL tags
        self.__as_reset()
        self.__boxclean()
        self.__blinkreset()
        self.__boxselect = False
        self.__boxstart  = None
        self.__boxend    = None
        self.__lbounds   = None
        
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
            
            #the end of the entire text is the only place where box-select will create new lines
            r,_ = map(int, self.index('end-1c').split('.'))
            #if we are on the last row
            if nr == r:
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
                r = r if not wgo else max(1, r+self.__vgrabofs)
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
    def __cut(self, p:str=None) -> bool:
        #get selection ranges
        r = self.tag_ranges(tk.SEL)
        for i in range(0, len(r), 2):
            self.tag_remove(tk.SEL, *r[i:i+2])  #remove tk.SEL tag
            self.replace_text(*r[i:i+2], '')    #delete selected text
        self.caret = p or self.caret            #put the caret somewhere
        return bool(r)
        
    #move all selected text to clipboard
    #this is safe for regular selected text but designed for box-selected text
    def __copy(self) -> bool:
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
        return bool(r)

    #insert clipboard text
    def __paste(self) -> bool:
        try:
            l = self.clipboard_get().split('\n')    #get lines
        except tk.TclError: return False
        
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
        return True
    
    #EVENTS
    def __handler(self, event) -> None:
        #Shift and Alt facts
        shift = (event.keysym in SHIFTS) or (event.state & SHIFT)
        alt   = (event.keysym in ALTS  ) or (event.state & ALT  )
        shiftonly, altonly = (shift and not alt), (alt and not shift)
        
        self.set_activeline()
        
        if event.type == tk.EventType.KeyPress:
            self.__as = alt and shift
                            
            if event.state & CONTROL:
                if   event.keysym=='c':
                    #if not boxcopy, normal cut/copy/paste behaviors are used
                    self.__boxcopy = not self.__as_commit and self.__boxselect
                    
                    #BOXSELECT COPY(Cntl+c)
                    if self.__boxcopy:
                        self.__copy()
                        return 'break'
                        
                elif event.keysym=='x':
                    #if not boxcopy, normal cut/copy/paste behaviors are used
                    self.__boxcopy = not self.__as_commit and self.__boxselect
                    
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
            
            elif event.keysym=='BackSpace':
                #BOXSELECT BackSpace
                if self.__boxselect:
                    for r,c,adv in self.__typing_range(-1):
                        if adv<0: self.delete(f'{r}.{c}', f'{r}.{c+abs(adv)}')
                    return 'break'    
                return
            
            elif event.keysym=='Return':
                #BOXSELECT Return ~ deselects leaving the multiline-caret behind wherever it already was
                if self.__boxselect:
                    if bnd:=self.__lbounds:
                        self.tag_move(tk.SEL)
                        r,c = map(int, self.caret.split('.'))
                        self.__lbounds = self.__bounds(f'{bnd.br}.{c}', f'{bnd.er}.{c}', bnd.dn, bnd.rt, ow=True)
                    return 'break'
            
            #Shift+Arrow while in box-select mode moves entire selection in Arrow direction
            elif event.keysym in ARROWS and shiftonly and self.__boxselect:
                if not (bnd:=self.__lbounds): return
                
                self.__blinkreset()
                #multiline-caret
                mc = self.__bounds(f'{bnd.br}.{bnd.bc}', f'{bnd.er}.{bnd.bc}', ow=False)
                #track any effect a deletion has on our drop index
                self.mark_set(INSPNT, f'{bnd.br}.{bnd.bc}')
                
                self.__copy()
                self.__cut(INSPNT)     
                self.__boxclean(mc)
                
                self.__aindex(event.keysym) #move caret according to keysym
                self.__paste()
                self.__restore_clipboard()
                bnd = self.__boxmove(False)
                for _,_,_ in self.__bounds_range(tk.SEL, eo=not bnd.rt, ao=True): pass
                self.__blink()
                
                return 'break'
                    
            #deselects and moves caret to the start(left) or end(right) of the former selection
            #works for any type of selection
            elif (event.keysym in HARROWS) and (not self.__as):
                if b:= self.__bounds(*self.tag_bounds(tk.SEL)):
                    self.__boxreset()
                    self.caret = f'{b.er}.{b.ec}' if 'Right' in event.keysym else f'{b.br}.{b.bc}'
                    return 'break'
                return
            
            #BOXSELECT
            if self.__as:   
                #if this keysym isn't Shift, Alt or an Arrow, ignore and act like it never happened
                ar, ks = (event.keysym in ARROWS), (event.keysym in ALTSHIFTS)
                if (ar and not (event.state&ARROWKEY)) or not (ar or ks):
                    return 'break'
                
                #capture selection method
                self.__as_mouse = (self.__as_mouse or bool(event.state&BUTTON1)) and (not self.__as_arrow)
                self.__as_arrow = (self.__as_arrow or (event.keysym in ARROWS )) and (not self.__as_mouse)
                
                if (self.__as_mouse or self.__as_arrow) and self.__as_free:
                    #box-select mousedown
                    if not self.__as_commit:
                        self.__boxselect = True
                        self.__as_commit = True
                        #store last known 'insert' index
                        self.__boxstart  = self.__linsert
                        if self.__as_mouse: return 'break'
                    
                    #if we committed to arrow-selecting, and we aren't pressing an arrow, return
                    if self.__as_arrow and (event.keysym in ALTSHIFTS): return 'break'
                    
                    #box-select mousemove ~ via last keypress (shift, alt, arrow) constantly firing
                    #vindex might not exist yet.
                    self.__boxend = (self.__aindex(event.keysym), self.__vindex(event.x, event.y))[self.__as_mouse]
                    
                    #never use overwrite here, if you do you will lose the proper selection direction
                    if (bnd:=self.__bounds(ow=False)) == self.__lbounds: return
                        
                    #remove whitespace and carets from last bounds, overwrite last bounds 
                    self.__boxclean()
                    self.__lbounds = bnd
                    
                    #draw rect
                    for r, bc, ec in self.__bounds_range('BOXSELECT', bo=not bnd.rt, eo=1):
                        _, lc = map(int, self.index(f'{r}.end').split('.'))
                        self.insert(f'{r}.{ec}', ' '*max(0, ec-lc)) #add columns if necessary
                        
                    return 'break'
                        
                #box-select mouseup ~ deinit hotbox 
                if self.__as_commit and self.__as_mouse: 
                    self.__as_release(event.state)
                    return 'break'
                
                #store 'insert' position before BUTTON1 press
                self.__linsert  = self.caret
                return 'break'
            else:
                #BOX-TYPING
                if self.__boxselect and len(event.char):
                    #typing_range handles the faux-caret and bounds management, we just need to insert
                    for r,c,adv in self.__typing_range(1): self.insert(f'{r}.{c-adv}', event.char)  
                    return 'break'
                            
        elif event.type == tk.EventType.KeyRelease:
            if self.__as_commit and (event.keysym in ALTSHIFTS): 
                self.__as_release(event.state)
                #fixes refocus problem when releasing the Alt hotkey
                self.focus_force()
                return 'break'
                
            if altonly and not self.__as_free:
                #fixes refocus problem when releasing the Alt hotkey
                self.focus_force()
                return 'break'
                
            #this catches pressing and releasing hotbox without ever clicking the mouse
            self.__as = False
            
        elif event.type == tk.EventType.ButtonPress:
            mse  = self.index('current') #get mouse index
            
            #GRAB SELECTED
            #check if mouse index is within a selection
            if tk.SEL in self.tag_names(mse):
                #box-selection
                if b:=self.__lbounds:
                    r,_ = map(int, mse.split('.')) #get mouse index row
                    self.__vgrabofs = b.br-r       #store vertical grab offset
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
            if not self.__selgrab: return
            
            #if you are where you started, then dragging is false
            self.__seldrag = self.caret != self.__linsert
            #cursor indicates state
            self['cursor'] = ('xterm', 'fleur')[self.__seldrag]
            self['insertwidth'] = INSWIDTH #show real caret to help you track your drop
                    
        elif event.type == tk.EventType.ButtonRelease:
            if not self.__selgrab: return
            
            #GRABBED
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
            
            #make a "multiline caret" so __boxclean works down every row... 
            #in what will be the only remaining column, after deletion
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
                self.__cut(INSPNT)     #delete selection and move caret to insertion point
                
                #PASTE NORMAL
                if not self.__boxselect:
                    ip = self.caret
                    self.event_generate('<<Paste>>')
                    self.__lbounds = self.__bounds(ip, self.caret, ow=True)
                    self.set_activeline()
                    self.tag_move(tk.SEL, ip, self.caret) #clear and draw tk.SEL
                    return 
                
                #PASTE COLUMN 
                self.__boxclean(mc)
                self.__paste()
                self.__restore_clipboard()
                bnd = self.__boxmove(False) #move bounds to caret
                #draw rect
                for _,_,_ in self.__bounds_range(tk.SEL, eo=not bnd.rt, ao=True): pass
                self.__blink()
                            

#example 
if __name__ == '__main__':
    ROWS = 6
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
            bst.text = '\n\n\n'.join([full]*ROWS)
    #run        
    App().mainloop()

