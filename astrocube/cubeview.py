# coding: utf-8
'''
GTK widget for viewing and navigating within a DataCube
Uses GTK as a widget library

@author: Braden MacDonald
'''

import gtk
import matplotlib
import numpy
from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg, NavigationToolbar2GTKAgg

class CubeViewWidget(gtk.VBox):

    def __init__(self, cube, parent_window):
        gtk.VBox.__init__(self, False)
        
        self.cube = cube
        self._x, self._y, self._z = 0,0,0 # Coordinates of our current view in the cube. Read/write via the .x .y and .z properties
        self.last_drawn_x,self.last_drawn_y, self.last_drawn_z = 0,0,0 # what the coordinates were last time we drew   
        
        fig = matplotlib.figure.Figure()
        self.fig = fig # Save a reference to the figure
        axes = fig.add_subplot(111)
        self.imgplot = axes.imshow(cube.data[:,:,self._z].transpose(1,0), cmap="spectral",vmin=0, vmax=numpy.nanmax(cube.data))
        fig.colorbar(self.imgplot) # Add a color scale at the right-hand side
        axes.set_xlabel(u"Right Ascension \u03b1")
        axes.xaxis.set_major_formatter(self._AxisFormatter(self.cube))
        axes.set_ylabel(u"Declination \u03b4")
        axes.yaxis.set_major_formatter(self._AxisFormatter(self.cube))
        axes.set_ylim(0,cube.data.shape[1])
        
        self.xline = axes.axvline(x=self._x, linewidth=4, color="white", alpha=0.5)
        self.yline = axes.axhline(y=self._y, linewidth=4, color="white", alpha=0.5)
        
        canvas = FigureCanvasGTKAgg(fig)  # a gtk.DrawingArea
        self.pack_start(canvas)
        self.toolbar = self._NavigationToolbar(cube, canvas, parent_window) # parent_window is needed for the "Save image..." file chooser dialog
        self.toolbar.remove(self.toolbar.get_nth_item(6)) # Remove the "Configure subplots" button which causes rendering issues if used
        self.pack_start(self.toolbar, False, False)
        
        canvas.mpl_connect('button_press_event', self._figure_mousedown)
        canvas.mpl_connect('button_release_event', self._figure_mouseup)
        canvas.mpl_connect('motion_notify_event', self._figure_mousemoved)
        self._is_mouse_down = False # is the mouse button currently pressed?
        
        scale = gtk.HScale()
        self.scale = scale
        scale.set_range(0, cube.data.shape[2]-1)
        scale.set_digits(0)
        scale.set_value(self._z)
        scale.set_draw_value(False)# Hide the built in display of the current value since it's not in real units (not in km/s)
        vel_middle = int(cube.data.shape[2]/2)
        scale.add_mark(0, gtk.POS_BOTTOM, "{vel} {units}".format(vel=cube.velocity_at(z=0,decimals=0), units="km/s"))
        scale.add_mark(vel_middle, gtk.POS_BOTTOM, "{vel} {units}".format(vel=cube.velocity_at(z=vel_middle,decimals=0), units="km/s"))
        scale.add_mark(cube.data.shape[2]-1, gtk.POS_BOTTOM, "{vel} {units}".format(vel=cube.velocity_at(z=cube.data.shape[2]-1,decimals=0), units="km/s"))
        self.pack_start(scale, False, False)
        scale.connect("value-changed", self._update_velocity)
        
        self.needs_redraw = False # Set this to True if you want the canvas to be repainted
        gtk.idle_add(CubeViewWidget._check_redraw, self) # we only want to re re-drawing when the GUI is idle, for maximum interactivity
        
        self.toolbar.update_mouseout_message()
    @property
    def x(self): return self._x
    @x.setter
    def x(self, value):
        if type(value) is float and value >= 0 and value <= 1:
            # Allow people to enter a float like 0.5 to set x to the exact midpoint value:
            self._x = round((self.cube.data.shape[0]-1) * value) 
        else:
            try:
                self._x = int(value) % self.cube.data.shape[0]
            except:
                raise ValueError("Invalid x value given") 
        self.needs_redraw = True # We have changed the current coordinates, so will need to redraw
        self.toolbar.update_mouseout_message()
    
    @property
    def y(self): return self._y
    @y.setter
    def y(self, value): 
        if type(value) is float and value >= 0 and value <= 1:
            # Allow people to enter a float like 0.5 to set x to the exact midpoint value:
            self._y = round((self.cube.data.shape[1]-1) * value) 
        else:
            try:
                self._y = int(value) % self.cube.data.shape[1]
            except:
                raise ValueError("Invalid y value given")
        self.needs_redraw = True # We have changed the current coordinates, so will need to redraw
        self.toolbar.update_mouseout_message()
    
    @property
    def z(self): return self._z
    @z.setter
    def z(self, value):
        if type(value) is float and value >= 0 and value <= 1:
            # Allow people to enter a float like 0.5 to set x to the exact midpoint value:
            self._z = round((self.cube.data.shape[2]-1) * value) 
        else:
            try:
                self._z = int(value) % self.cube.data.shape[2]
            except:
                raise ValueError("Invalid z value given")
        self.needs_redraw = True # We have changed the current coordinates, so will need to redraw
        if self.scale.get_value() != self._z:
            self.scale.set_value(self._z)

    def _update_velocity(self, scale_widget):
        self.z = int(scale_widget.get_value())
        self.toolbar.update_mouseout_message() # the current velocity shown in the status message must be updated.
    
    def _figure_mousedown(self, event):
        if event.xdata != None and event.ydata != None: # If we're in the canvas:
            self.x = int(event.xdata)
            self.y = int(event.ydata)
            self._is_mouse_down = True
    def _figure_mouseup(self, event):
        if event.xdata != None and event.ydata != None: # If we're in the canvas:
            self.x = int(event.xdata)
            self.y = int(event.ydata)
        self._is_mouse_down = False
    def _figure_mousemoved(self, event):
        if self._is_mouse_down and (event.xdata != None and event.ydata != None): # If we're in the canvas:
            self.x = int(event.xdata)
            self.y = int(event.ydata)
        # Note other mouse motion updates get processed below in _NavigationToolbar.mouse_move

    def _check_redraw(self):
        ''' Update this widget's display if needed. Called only when the main event loop is idle '''
        if self.needs_redraw:
            if self._x != self.last_drawn_x:
                self.xline.set_xdata([self._x, self._x])
                self.last_drawn_x = self._x
            if self._y != self.last_drawn_y:
                self.yline.set_ydata([self._y, self._y])
                self.last_drawn_y = self._y
            if self._z != self.last_drawn_z: # If z has changed since we last drew:
                self.imgplot.set_data(self.cube.data[:,:,self._z].transpose(1,0))
                self.last_drawn_z = self._z
            self.fig.canvas.draw()
            self.needs_redraw = False
        return True
    
    class _AxisFormatter(matplotlib.ticker.Formatter):
        '''
        An axis formatter object suitable for use with matplotlib.
        Will put declination into degrees and right ascension in hours
        NOTE: this is handy for a quick reference, but is not accurate,
        as these coordinates are not linear!
        '''
        def __init__(self, cube):
            self.cube = cube
        def __call__(self, coord, pos=None):
            a = self.axis.axis_name
            if a == "x":
                #return u"{0:.2f}\u00b0".format( self.cube.point_coords(coord,0,0)[0] ) # \u00b0 : degree symbol
                return self.cube.point_coords_str(coord,0,0,ra_fmt="hms",decimals=0)[0]
            elif a == "y":
                # Note that this is not accurate, since the real-world coordinates of x actually vary with y
                # This just returns the coordinate of x for y=0, and returns a result in degrees
                return u"{0:.2f}\u00b0".format( self.cube.point_coords(0,coord,0)[1] ) # \u00b0 : degree symbol
            else:
                # Probably won't ever be used, but if we get asked for any other axes, just return them
                # with the units that point_coords gives
                val = self.cube.point_coords(0,0,coord)[2]
                return u"{0:.1f}".format(val) # No units labeled directly on the axis. Z is in km/s

    class _NavigationToolbar(NavigationToolbar2GTKAgg):
        def __init__(self, cube, canvas, parent_window):
            self.cube = cube
            NavigationToolbar2GTKAgg.__init__(self, canvas, parent_window)
        def mouse_move(self, event):
            #print 'mouse_move', event.button
    
            cursors = matplotlib.backend_bases.cursors
            if not event.inaxes or not self._active:
                if self._lastCursor != cursors.POINTER:
                    self.set_cursor(cursors.POINTER)
                    self._lastCursor = cursors.POINTER
            else:
                if self._active=='ZOOM':
                    if self._lastCursor != cursors.SELECT_REGION:
                        self.set_cursor(cursors.SELECT_REGION)
                        self._lastCursor = cursors.SELECT_REGION
                elif (self._active=='PAN' and self._lastCursor != cursors.MOVE):
                    self.set_cursor(cursors.MOVE)
                    self._lastCursor = cursors.MOVE
    
            if event.inaxes and event.inaxes.get_navigate():
                # We are hovering over the cube plot, so display the data coordinates and real coordinates:
                x,y,z = event.xdata, event.ydata, self.get_parent().z
                ra, dec, vel = self.cube.point_coords_str(x,y,z)
                self.set_message(u"{val}  α: {ra},  δ: {dec},  v: {vel}  ({x}, {y}, {z})".format(val=self.cube.data[x,y,z], ra=ra,dec=dec,vel=vel, x=int(x), y=int(y), z=z))
            else: #self.set_message(self.mode)
                self.update_mouseout_message()
        def update_mouseout_message(self):
            ''' Set the message shown when the user's cursor is not over the cube image '''
            z = self.get_parent().z
            #vel = self.cube.point_coords_str(0,0,z)[2]
            #self.set_message("v: {vel}  (__, __, {z})".format(vel=vel, z=z))
            x,y,z = self.get_parent().x, self.get_parent().y, self.get_parent().z
            ra, dec, vel = self.cube.point_coords_str(x,y,z)
            self.set_message(u"{val}  \u03b1: {ra},  \u03b4: {dec},  v: {vel}  ({x}, {y}, {z})".format(val=self.cube.data[x,y,z], ra=ra,dec=dec,vel=vel, x=int(x), y=int(y), z=z))


class CubeViewDialog(gtk.Dialog):

    def __init__(self, cube):
        gtk.Dialog.__init__(self)
        self.cube = cube
        self.view = CubeViewWidget(cube, self)
        self.set_title("{ln} spectral line map of {o}".format(o=cube.object_name,ln=cube.line_name))
        self.set_default_size(600,400)
        #self.add(self.view)
        self.vbox.pack_start(self.view)
    def run(self):        
        self.show_all()
        gtk.Dialog.run(self)
        print("Got here, so hiding...")
        # In case there is no existing main gtk loop, run three iterations
        # so that the dialog actually gets hidden properly:
        self.hide()
        for _ in range(3):
            gtk.main_iteration()
        
        