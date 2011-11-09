#!/usr/bin/env python
# coding: utf-8
'''
Standalone data cube viewer.
Uses GTK as a widget library

@author: Braden MacDonald
'''
import os
import sys
import StringIO
import gtk
import numpy
import matplotlib
import pyfits
from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg, NavigationToolbar2GTKAgg

from astrocube import DataCube
from astrocube.cubeview import CubeViewWidget




class PythonCommandWidget(gtk.VBox):
    safe_builtins = dict([ (k, locals().get(k, None)) for k in \
                          ['math','abs', 'all', 'any', 'acos', 'asin', 'atan', 'atan2', 'ceil', 'cos', 'cosh', 'degrees', 'e', 'enumerate', 'exp', 'fabs', 'float', 'floor', 'fmod', 'frexp', 'hypot', 'ldexp', 'log','log10', 'long', 'max', 'min', 'int', 'modf', 'pi', 'pow', 'print', 'radians', 'range', 'sin', 'sinh', 'sqrt', 'str', 'sum', 'tan', 'tanh', 'xrange'] ])
    
    def __init__(self, user_globals, user_locals):
        self._user_globals = user_globals
        self._user_locals = user_locals
        
        gtk.VBox.__init__(self)
        
        self.result_buffer = gtk.TextBuffer()
        self.cmd_output_window = gtk.ScrolledWindow()
        self.cmd_output_box = gtk.TextView()
        self.cmd_input_field = PlaceholderEntry("Enter Python command")
        
        self.cmd_output_window.set_size_request(-1,75)
        self.cmd_output_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        self.cmd_output_box.set_editable(False)
        self.cmd_output_box.set_wrap_mode(gtk.WRAP_WORD_CHAR)
        self.cmd_output_window.add(self.cmd_output_box)
        self.pack_start(self.cmd_output_window, expand=True, fill=True)
        
        self.cmd_input_field.connect("activate", self.pressed_enter)
        self.cmd_input_field.connect("key-press-event", self.pressed_key)
        self.pack_start(self.cmd_input_field, expand=False)
        
        self.text_tag_cmd = self.result_buffer.create_tag(weight=700) # format of commands previously entered
        self.text_tag_result = self.result_buffer.create_tag(foreground="navy") # format of command output
        self.text_tag_empty_result = self.result_buffer.create_tag(scale=0.2) # format for blank line between commands with no output
        self.text_tag_error_result = self.result_buffer.create_tag(foreground="red") # format of error messages
        
        self.first_error_line = None # Save line # where error messages begin, so we can clear them from the screen on subsequent successes
        
        self.command_history = [] # List of successfully executed commands. Most recent ones are at the end.
        self.command_history_pos = 0 # 0 means typing in a new command; -1 means viewing the previous command
        self.command_entered = ""

    def pressed_key(self, entry_widget, event):
        if event.keyval == 65362: # Up key pressed:
            if self.command_history_pos > (0 - len(self.command_history)):
                if self.command_history_pos == 0:
                    self.command_entered = entry_widget.get_text() # Save the current (never entered) command since it can't be retrieved otherwise
                self.command_history_pos -= 1 # Go back
                entry_widget.set_text(self.command_history[self.command_history_pos])
                entry_widget.emit('move-cursor', gtk.MOVEMENT_BUFFER_ENDS, 0, False) # Move cursor to the end
            return True # Don't do default action
        elif event.keyval == 65364: # Down key pressed:
            if self.command_history_pos < 0:
                self.command_history_pos += 1 # Go forward
                if self.command_history_pos == 0:
                    entry_widget.set_text(self.command_entered)
                else:
                    entry_widget.set_text(self.command_history[self.command_history_pos])
                entry_widget.emit('move-cursor', gtk.MOVEMENT_BUFFER_ENDS, 0, False) # Move cursor to the end
            return True

    def pressed_enter(self, entry_widget):
        cmd_str = entry_widget.get_text()
        
        if cmd_str is "":
            return
        
        try:
            temp_buffer = StringIO.StringIO()
            sys.stdout = temp_buffer # capture stdout so we can display the output
            cmd_code = compile(cmd_str+"\n", "<command input>", "single") # Change third parameter to "single" to get more output
            exec cmd_code in self._user_globals, self._user_locals
            sys.stdout = sys.__stdout__
            result_str = temp_buffer.getvalue()
            
            # the command was executed successfully:
            # Save it into the command history:
            if (not self.command_history) or self.command_history[-1] != cmd_str:
                self.command_history.append(cmd_str)
            self.command_history_pos = 0
            entry_widget.set_text("")
            
            # If there were error messages on the screen, clear them:
            if self.first_error_line != None:
                self.result_buffer.delete(self.result_buffer.get_iter_at_line(self.first_error_line), self.result_buffer.get_end_iter())
                self.first_error_line = None
            
            # add this text to the output view:
            buffer_end = self.result_buffer.get_end_iter()
            self.result_buffer.insert_with_tags(buffer_end, cmd_str+"\n", self.text_tag_cmd)
            buffer_end = self.result_buffer.get_end_iter()
            if len(result_str) == 0:
                self.result_buffer.insert_with_tags(buffer_end, result_str+"\n", self.text_tag_empty_result)
            else:
                self.result_buffer.insert_with_tags(buffer_end, result_str.rstrip()+"\n", self.text_tag_result)
            
        except:
            result_str = "Exception: {0}".format(sys.exc_info()[1].__str__())
            # Save our position so we can later clear the error message:
            if self.first_error_line == None:
                self.first_error_line = self.result_buffer.get_line_count() - 1
            # add this text to the output view:
            buffer_end = self.result_buffer.get_end_iter()
            self.result_buffer.insert_with_tags(buffer_end, cmd_str+"\n", self.text_tag_cmd)
            buffer_end = self.result_buffer.get_end_iter()
            self.result_buffer.insert_with_tags(buffer_end, result_str+"\n", self.text_tag_error_result)
        
        self.cmd_output_box.set_buffer(self.result_buffer)
        #self.cmd_output_box.scroll_to_iter(self.result_buffer.get_end_iter(), 0, use_align=True, yalign=1) # scroll to the end
        self.result_buffer.place_cursor(self.result_buffer.get_end_iter())
        self.cmd_output_box.scroll_to_mark(self.result_buffer.get_mark("insert"), 0)

class PlaceholderEntry(gtk.Entry):
    # This code from http://stackoverflow.com/questions/2503562/pygtk-entry-placeholder
    _default = True
    placeholder_color = gtk.gdk.color_parse('gray')
    regular_color = gtk.gdk.color_parse('black')

    def __init__(self, placeholder_text, *args, **kwds):
        gtk.Entry.__init__(self, *args, **kwds)
        self.connect('focus-in-event', self._focus_in_event)
        self.connect('focus-out-event', self._focus_out_event)
        self.placeholder = placeholder_text
        self.set_text(self.placeholder)
        self.modify_text(gtk.STATE_NORMAL, self.placeholder_color)
        self._default = True

    def _focus_in_event(self, widget, event):
        if self._default:
            self.set_text('')
            self.modify_text(gtk.STATE_NORMAL, self.regular_color)
            self._default = False

    def _focus_out_event(self, widget, event):
        if gtk.Entry.get_text(self) == '':
            self.set_text(self.placeholder)
            self.modify_text(gtk.STATE_NORMAL, self.placeholder_color)
            self._default = True
        else:
            self._default = False

    def get_text(self):
        if self._default:
            return ''
        return gtk.Entry.get_text(self)




if __name__ == "__main__":
    
    filename = False
    if len(sys.argv) == 2:
        filename = sys.argv[1]
    else:
        fits_files = [filename for filename in os.listdir('.') if (filename.endswith(".fits") and os.path.isfile(filename))]
        if len(fits_files)==0:
            print("No FITS files found in the current directory")
            sys.exit(1)
        print("Found {num} FITS files in the current directory:".format(num=len(fits_files)))
        i=0
        for f in fits_files:
            print(" {id}:  {filename}".format(id=i,filename=f))
            i+=1
        choice = -1
        while (choice < 0 or choice >= len(fits_files)):
            choice = int(raw_input("\nWhich would you like to open? "))
        filename = fits_files[choice]
    
    
    # Now open the requested FITS file
    try:
        hdulist = pyfits.open(filename)
    except Exception as e:
        print("Invalid FITS file ({f}): {err}".format(f=filename, err=e))
        sys.exit(1)
    
    print("Using FITS file {f}".format(f=filename))
    # TODO: Select which HDU, instead of just using the primary one?
    
    cube = DataCube(hdulist[0])
    
    win = gtk.Window()
    win.connect("destroy", lambda x: gtk.main_quit())
    win.set_default_size(800,600)
    win.set_title("{ln} spectral line map of {o}".format(o=cube.object_name,ln=cube.line_name))
    
    cube_view = CubeViewWidget(cube, win)
    
    
    
    all_sub_figures = []
    
    redraw_sub_figures = False # Set true whenever subfigures should be redrawn
    
    
    
    def make_fig(title = None):
        '''
        Create a figure window with a single set of axes and a single main subplot.
        Returns the axes of the main subplot
        '''
        global all_sub_figures
        if title == None:
            title = "Untitled Figure {0}".format(len(all_sub_figures)+1)
        dialog = gtk.Dialog(title, win, gtk.DIALOG_DESTROY_WITH_PARENT)
        dialog.set_default_size(500,400)
        fig = matplotlib.figure.Figure()
        axes = fig.add_subplot(111)
        #axes.invert_yaxis()
        #axes.autoscale()
        canvas = FigureCanvasGTKAgg(fig)  # a gtk.DrawingArea
        canvas.set_size_request(300,300)
        dialog.vbox.pack_start(canvas, expand=True)
        toolbar = NavigationToolbar2GTKAgg(canvas, dialog)
        dialog.vbox.pack_start(toolbar, False, False)
        dialog.show_all()
        canvas.draw()
        fig.prev_child_count = 0
        all_sub_figures.append(fig)
        return axes
    
    def check_figures():
        '''
        When we're idle, this will re-draw any figures that need to be re-drawn.
        All visible subfigures should be redrawn whenever: 
            cube changed, view changed, OR any command is run
        '''
        global redraw_sub_figures
        
        if redraw_sub_figures:
            for f in all_sub_figures:
                f.canvas.redraw()
            redraw_sub_figures = False
    
        return True # Keep calling this method
    
    gtk.idle_add(check_figures)
    
    cmd_widget = PythonCommandWidget(user_globals = { 'numpy': numpy, 'matplotlib': matplotlib, 'make_fig': make_fig  }, 
                                     user_locals = { 'cube': cube, 'cube_view': cube_view })
    
    main_pane = gtk.VPaned()
    main_pane.pack1(cube_view, resize=True, shrink=True)
    main_pane.pack2(cmd_widget, resize=True, shrink=False)
    main_pane.set_position(9000) # Expand the figure to be as big as possible
    
    win.add(main_pane)
    
    win.show_all()
    gtk.main()
    
    hdulist.close()
