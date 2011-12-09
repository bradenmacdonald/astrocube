astrocube
======
Python Classes for Loading and Viewing Radio Astronomy Data Cubes

By Braden MacDonald

Copyright (c) 2011 Braden MacDonald. Released under a BSD License.


About
-----

This package provides a simple interface for loading radio astronomy data cubes 
from a FITS file. It was written primarily as an exercise for me to learn more
about working with data cubes. Thus it is **alpha quality** and not tested
thoroughly enough to be relied upon for other work.

Developed for use with Python 2.7

Features
--------

+ Uses [PyFITS](http://www.stsci.edu/resources/software_hardware/pyfits) to 
  load cube data from FITS files in a standardized way.
+ Uses [PyWCS](http://stsdas.stsci.edu/astrolib/pywcs/) to determine the
  sky coordinates of any data element in the cube in a very easy-to-use way
+ Includes a simple algorithm for determining the standard deviation of 
  noise in the cube as a function of position. 
+ Has a `CubeViewDialog` class that can be used from ipython or other
  applications to display a data cube, browse through its contents,  
  select points from within the cube (uses matplotlib and pygtk),
  and highlight regions of the cube with different colors
+ Installs a script called `astrocubeview.py`, which provides a simple
  ipython-like interface for quickly viewing a data cube and executing
  arbitrary commands using the data in the cube (uses matplotlib and pygtk)

Installation
-----
To install, simply run the following command:

```
pip install git+git://github.com/bradenmacdonald/astrocube.git#egg=astrocube 
```

(Requires that you have [pip](http://www.pip-installer.org) and 
[distribute](http://pypi.python.org/pypi/distribute) installed.)

To install it locally (not system-wide), add a `--user` argument after 
"install". To install an editable version, add a `-e` argument. 

Usage
-----
Using [IPython](http://ipython.org/) and pylab to view the spatial noise
deviation in a cube:

```python
# Enter these commands into ipython with pylab enabled:
import astrocube
cube = astrocube.DataCube("L1448.13co.fits") # Substitute with your own file
imshow(cube.noise_dev_xy) # n.b. by default the matplotlib y axis is upside-down
```

Visualizing and interacting with a cube using a simple GUI:

```python
import astrocube
import astrocube.cubeview
import numpy as np
cube = astrocube.DataCube("L1448.13co.fits")  # Substitute with your own file
dialog = astrocube.cubeview.CubeViewDialog(cube)
print("Select a point in the data cube, then close the dialog.")
dialog.run()
v = dialog.view # Shorten this for convenience
print("You selected the point ({x},{y},{z})".format(x=v.x,y=v.y,z=v.z))
print("The sky coordinates of that point are: {0}".format(", ".join(cube.point_coords_str(v.x,v.y,v.z))))
print("Now let's look at the most intense value in the data cube.")
(v.x, v.y, v.z) = np.unravel_index(np.nanargmax(cube.data), cube.data.shape)
dialog.run()
```

Gotchas
-------
Cube data is accessed through the `.data` attribute of the `DataCube` class.
However, the numpy ndarray indices accessible through the `DataCube` class
are standardized to follow Python conventions, not FITS/FORTRAN conventions. 
This means that the first index is the x axis (right ascension), the second 
index is the y axis (declination), and the third index is the z axis 
(spectral dimension).