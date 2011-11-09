'''
astrocube.DataCube: A python class to represent a radio astronomy data cube

@author: Braden MacDonald
'''
import numpy as np
import pywcs
import scipy.stats


class DataCube:
    """ Represents a radio astronomy data cube. Standardizes the array indices
        (this is python, not FORTRAN, so the first pixel shall be [0,0,0], 
        and the index order [x,y,z] is always mapped to [RA, DEC, VEL]). 
        Uses pywcs to perform coordinate conversions, so you can easily
        get the sky coordinates of any data pixel.
        Also can calculate the standard deviation of the noise for any
        data pixel coordinate. """
 
    def __init__(self, fits_filename_or_hdu, hdu_index = 0, calc_noise_dev = True):
        '''
        fits_filename_or_hdu: Either the path to a FITS file, or an HDU
        object loaded using PyFITS
        
        hdu_index: if a filename is given, this is which HDU to use
        '''
        if type(fits_filename_or_hdu) == str:
            import pyfits
            hdulist = pyfits.open(fits_filename_or_hdu)
            hdu = hdulist[hdu_index]
        else:
            # Assume the argument given is a HDU object
            hdu = fits_filename_or_hdu
        
        self._header = hdu.header
        
        if not (set(("OBJECT", "LINENAME", "NAXIS")) <= set(self._header.keys()) and self._header["NAXIS"] == 3):
            raise Exception("This does not seem to be a valid data cube. It should be a 3-axis FITS file that defines LINENAME and OBJECT.")
        self.object_name = self._header["OBJECT"]
        self.line_name = self._header["LINENAME"]
        
        # Now use pywcs to interpret the coordinates and re-index the array to a standardized (RA, DEC, VEL) zero-based index
        self._wcs = pywcs.WCS(self._header)
        assert(self._wcs.wcs.lngtyp == 'RA') # the "longitude" axis should be the right ascension
        assert(self._wcs.wcs.lattyp == 'DEC')# the "latitude" axis should be the declination
        # Record the axis indices according to pywcs, needed when doing pixel-to-sky-coord conversions:
        self._index_ra = self._wcs.wcs.lng
        self._index_dec = self._wcs.wcs.lat
        self._index_vel = self._wcs.wcs.spec
        
        
        last_axis = 2 # index of the third axis is 2 - we need this in order to reverse the FITS axis order
        self.data = hdu.data.transpose((last_axis-self._wcs.wcs.lng, last_axis-self._wcs.wcs.lat, last_axis-self._wcs.wcs.spec)) # longitude index = right ascension; latitude index = declination, then spectral
        
        if calc_noise_dev:
            self.calc_noise_dev() # You can always call this again later with different parameters
        else:
            self.noise_dev, self.noise_dev_xy = None, None
    
    def calc_noise_dev(self, iterations = 3, signal_threshold = 4, noise_slice_z = None, compute_spectral_variation = False):
        
        '''
        Compute an estimate of the standard deviation of noise in the cube as a
        function of 3-D data coordinate. After calling this method, you can use
        e.g. cube.noise_dev[40,50,60] to get the noise at the coordinate x=40,
        y=50,z=60.
        
        This uses median absolute deviation to do the computation, and in each 
        iteration, it will ignore any data points with intensity value greater
        than signal_threshold*sigma. 
        
        If you provide an optional noise_slice_z array, the first preliminary
        estimate of spatial sigma will use only the data in the given slice. 
        
        Puts the resulting data into self.noise_dev, along with the spatial 
        and spectral data in self.noise_dev_xy and self.noise_dev_z.
        
        The self.noise_dev_z array will be set if you use more than one
        iteration AND have set compute_spectral_variation = True. 
        '''
        
        if noise_slice_z is None:
            data_cropped = self.data
        else:
            if noise_slice_z.shape[0] != self.data.shape[0] or noise_slice_z.shape[1] != self.data.shape[1]:
                raise Exception("Invalid argument - noise_slice_z should be a slice of data with same spatial shape as cube.data, e.g. cube.data[:,:,400:]")
            data_cropped = noise_slice_z.copy()
        
        # Calculate the distribution of noise in the cube:
        self.noise_dev_xy = _mad(data_cropped, axis=2) # Use median absolute deviation to estimate sigma
        
        if iterations > 1:
            # Now iterate to refine this noise sigma estimate:
            self.noise_dev = np.expand_dims(self.noise_dev_xy, 2) # Add another dimension so we can multiply 3 lines below with broadcasting
            data_cropped = self.data.copy() # We don't want to use masked arrays (feature-poor) or modify self.data directly so make a copy
            for _ in range(1, iterations):
                data_cropped[data_cropped > signal_threshold*self.noise_dev] = np.nan # Ignore this data point
                
                self.noise_dev_xy = _mad(data_cropped, axis=2) # Use median absolute deviation to estimate sigma
                
                if compute_spectral_variation:
                    self.noise_dev_z = _mad(data_cropped.reshape(-1, data_cropped.shape[2]), axis=0)
                
                    # At this point, one would fit noise_dev_z to a simple quadratic model, in order to
                    # avoid influence from signal while still being able to model systematic effects.
                    # However, most of the data cubes I'm using in this project have no spectral noise
                    # variation, so I haven't written the necessary code.
                    raise Exception("Spectrally varying noise has not been implemented.")
                    
                    self.noise_dev = np.expand_dims(self.noise_dev_xy, 2) * self.noise_dev_z
                    self.noise_dev /= scipy.stats.nanmean(self.noise_dev_z)
                else:
                    self.noise_dev = np.expand_dims(self.noise_dev_xy, 2) * np.ones(self.data.shape[2], dtype=self.data.dtype)
        else:
            self.noise_dev = np.expand_dims(self.noise_dev_xy, 2) * np.ones(self.data.shape[2], dtype=self.data.dtype)
    
    def __str__(self):
        if self.noise_dev == None:
            sigma = "not computed"
        else:
            sigma = scipy.stats.nanmean(self.noise_dev.ravel())
        dmin,dmax = np.nanmin(self.data), np.nanmax(self.data)
        return ("DataCube {ln} spectral line map of {o}. "
               "Data shape is {shape} with intensity on the range {dmin} to {dmax}. "
               "Mean noise deviation is is {sigma}.").format(o=self.object_name,ln=self.line_name,dmin=dmin,dmax=dmax,shape=self.shape(), sigma=sigma)
    
    def shape(self):
        """ Returns a tuple giving the sizes of each axis """
        return self.data.shape
    def point_coords(self,x,y,z):
        """
        Given the 0-based coordinate of a point in the data cube, this will return a tuple 
        (ra,dec,vel) where ra,dec are in degrees, and vel is in km/s. The units get automatically 
        standardized thanks to pywcs.
        """
        raw_coord = [0,0,0]
        raw_coord[self._index_ra] = x
        raw_coord[self._index_dec] = y
        raw_coord[self._index_vel] = z
        sky = self._wcs.all_pix2sky(np.array([raw_coord], np.float_), 0)
        #sky = self._wcs.all_pix2sky(np.array([[x+1,y+1,z+1]], np.float_), 1) # second argument indicates the array's coordinates are 1-based (i.e. origin is (1,1))
        return (sky[0][self._index_ra], sky[0][self._index_dec], sky[0][self._index_vel]/1000)
    def point_coords_str(self,x,y,z, ra_fmt = "hms", dec_fmt = "dms", decimals = 2):
        """
        Given the 0-based coordinate of a point in the data cube, this will 
        return a tuple of strings (ra,dec,vel) in the formats specified.
        
        Valid formats for right ascension (ra_fmt) and declination (dec_fmt)
        are: deg, dms, hms
        
        Velocity is always in km/s
        
        Decimals is the number of decimal places returned within each string.
        """
        valid_formats = ["deg", "hms", "dms"]
        assert(ra_fmt in valid_formats and dec_fmt in valid_formats)
        coords = self.point_coords(x, y, z)
        # Format right ascension:
        ra_deg = coords[0]
        if ra_fmt == "deg":
            ra_str = u"{0:.{decimals}f}\u00b0".format(ra_deg, decimals=decimals) # \u00b0 is the degree symbol
        elif ra_fmt == "hms":
            h,m,s = _deg2hms(ra_deg)
            ra_str = "{h}h {m}m {s:.{decimals}f}s".format(h=h,m=m,s=s,decimals=decimals)
        elif ra_fmt == "dms":
            d,m,s = _deg2dms(ra_deg)
            ra_str = u"{d}\u00b0 {m}' {s:.{decimals}f}''".format(d=d,m=m,s=s, decimals=decimals)
        # Format declination:
        dec_deg = coords[1]
        if dec_fmt == "deg":
            dec_str = u"{0:.{decimals}f}\u00b0".format(dec_deg, decimals=decimals) # \u00b0 is the degree symbol
        elif dec_fmt == "hms":
            h,m,s = _deg2hms(dec_deg)
            dec_str = "{h}h {m}m {s:.{decimals}f}s".format(h=h,m=m,s=s, decimals=decimals)
        elif dec_fmt == "dms":
            d,m,s = _deg2dms(dec_deg)
            dec_str = u"{d}\u00b0 {m}' {s:.{decimals}f}''".format(d=d,m=m,s=s, decimals=decimals)
        # Format the velocity:
        vel_str = "{0:.{decimals}f} km/s".format(coords[2], decimals=decimals)
        return ra_str, dec_str, vel_str
    def velocity_at(self, z, decimals=-1):
        """
        A helper method to return the velocity for a given z coordinate in km/s
        decimals = # of digits to include after the decimal point; -1 for highest precision
        """
        result = self.point_coords(0, 0, z)[2]
        if decimals >= 0:
            return round(result, decimals)
        else:
            return result

# Helper methods:
def _deg2hms(deg):
    ''' Get a tuple of (hours, arcminutes, arcseconds) from the provided decimal degrees '''
    hours = deg/360*24 # floating point result
    arcmin = (hours%1)*60 # floating point result
    arcsec = (arcmin%1)*60
    return int(hours), int(arcmin), arcsec

def _deg2dms(deg):
    ''' Get a tuple of (degrees, arcminutes, arcseconds) from the provided decimal degrees '''
    arcmin = (deg%1)*60 # floating point result
    arcsec = (arcmin%1)*60
    return int(deg), int(arcmin), arcsec

def _mad(data, axis=0, scale = (1 / 0.6745)):
    '''
    Returns the median absolute deviation (MAD) of the given data along the 
    given axis. 
    
    The scale factor allows one to use the MAD as a consistent estimator of the
    standard deviation. For normally distributed data, the scale factor should
    be 1 / 0.6745 = 1.4826
    
    median(abs(a - median(a))) * scale
    '''
    # Compute initial medians. nanmedian reduces the dimensionality of data, so
    # expand_dims is needed so that the result can be broadcast across the 
    # original data cube during subtraction.
    medians = np.expand_dims(scipy.stats.nanmedian(data, axis), axis)
    return scipy.stats.nanmedian(np.fabs(data - medians), axis) * scale
