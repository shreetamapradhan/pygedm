"""
Python wrapper for NE2001 FORTRAN code

References:

    [1] `Cordes, J. M., & Lazio, T. J. W. (2002), <https://ui.adsabs.harvard.edu/abs/2002astro.ph..7156C/abstract>`_
    *NE2001.I. A New Model for the Galactic Distribution of Free Electrons and its Fluctuations*,
    arXiv e-prints, astro-ph/0207156.

    [2] `Cordes, J. M., & Lazio, T. J. W. (2003), <https://ui.adsabs.harvard.edu/abs/2003astro.ph..1598C/abstract>`_
    *NE2001. II. Using Radio Propagation Data to Construct a Model for the Galactic Distribution of Free Electrons*,
    arXiv e-prints, astro-ph/0301598.

FORTRAN f2py objects
********************

Upon installation, ``pygedm`` will compile the fortran code to create f2py objects that can be accessed from
python.

**dmdsm f2py object**::

    Call signature: dmdsm.dmdsm(*args, **kwargs)
    Type:           fortran
    String form:    <fortran object>
    Docstring:
    limit,sm,smtau,smtheta,smiso = dmdsm(l,b,ndir,dmpsr,dist)

Wrapper for ``dmdsm``::

    Parameters:
        l : input float
        b : input float
        ndir : input int
        dmpsr : in/output rank-0 array(float,'f')
        dist : in/output rank-0 array(float,'f')

    Returns:
        limit : string(len=1)
        sm : float  (scattering measure, uniform weighting) (kpc/m^{20/3})
        smtau : float  (scattering measure, weighting for pulse broadening)
        smtheta : float  (scattering measure, weighting for angular broadening of galactic sources)
        smiso : float (scattering measure appropriate for calculating the isoplanatic angle at the source's location)


**density f2py object**::

    Call signature: density.density_2001(*args, **kwargs)
    Type:           fortran
    String form:    <fortran object>
    Docstring:
    ne1,ne2,nea,negc,nelism,necn,nevn,f1,f2,fa,fgc,flism,fcn,fvn,whicharm,wlism,wldr,
    wlhb,wlsb,wloopi,hitclump,hitvoid,wvoid = density_2001(x,y,z)

Wrapper for ``density_2001``::

    Args:
        x : input float
        y : input float
        z : input float

    Returns:
        ne1 : float
        ne2 : float
        nea : float
        negc : float
        nelism : float
        necn : float
        nevn : float
        f1 : float
        f2 : float
        fa : float
        fgc : float
        flism : float
        fcn : float
        fvn : float
        whicharm : int
        wlism : int
        wldr : int
        wlhb : int
        wlsb : int
        wloopi : int
        hitclump : int
        hitvoid : int
        wvoid : int
"""

import numpy as np
import os
from functools import wraps
from astropy import units as u

# RTD has issues with compilation of Fortran shared objects. This allows code import in RTD env
on_rtd = os.environ.get('READTHEDOCS') == 'True'
if not on_rtd:
    from . import dmdsm     # f2py FORTRAN object
    from . import density   # f2py FORTRAN object
else: # pragma: no cover
    class Mock(object):
        def dmdsm(self, *args, **kwargs):
            return 0, 0, 0, 0, 0
        def density_2001(self, *args, **kwargs):
            return 0
    density = Mock()
    dmdsm   = Mock()

DATA_PATH = os.path.dirname(os.path.abspath(__file__))

def run_from_pkgdir(f):
    """ Decorator function to chdir() into package directory when running

    Fortran code doesn't know the relative path to its data files.
    This wraps the function call, changing into the right directory
    first, calling it, then changing back to original directory.
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        cwdpath = os.getcwd()
        try:
            os.chdir(DATA_PATH)
            r = f(*args, **kwargs)
            return r
        except:   # pragma: no cover
            raise
        finally:
            os.chdir(cwdpath)
    return wrapped


def TAUISS(d, sm, nu):
    """ Convert a scattering measure (SM) to scattering timescale at given frequency.

    Direct port from FORTRAN code scattering98.f

    Args:
        d (float): Distance in kpc
        sm (float): Scattering measure (kpc m^{-20/3})
        nu (float): Radio frequency in GHz

    Returns:
        tauiss (float): pulse broadening time (ms)

    Fortran equiv::

              REAL FUNCTION TAUISS(d, sm, nu)
        c
        c calculates the pulse broadening time in ms
        c from distance, scattering measure, and radio frequency
        c
        c input:      d = pulsar distance       (kpc)
        c            sm = scattering measure    (kpc m^{-20/3})
        c            nu = radio frequency       (GHz)
        c output: tausis = pulse broadening time (ms)
        c
              implicit none
              real d, sm,  nu
              tauiss = 1000. * (sm / 292.)**1.2 * d * nu**(-4.4)
              end
    """
    tauiss = 1. * (sm / 292.)**1.2 * d * nu**(-4.4)
    return tauiss


@run_from_pkgdir
def dm_to_dist(l, b, dm):
    """ Convert DM to distance and compute scattering timescale
    
    Args:
        l (float): galactic latitude in degrees
        b (float): galactic longitude in degrees
        dm (floa): Dispersion measure

    Returns:
        dist (astropy.Quantity), tau_sc (astropy.Quantity): Distance (pc), scattering timescale at 1 GHz (s)
    """
    dm    = np.array(dm, dtype='float32')
    dist  = np.zeros_like(dm)
    l_rad = np.deg2rad(l)
    b_rad = np.deg2rad(b)
    ndir = 1
    if np.isclose(dm, 0):  # Catch infinite timeout bug
        return 0.0 * u.pc, 0.0 * u.s
    else:
        limit, sm, smtau, smtheta, smiso = dmdsm.dmdsm(l_rad, b_rad, ndir, dm, dist)

    tau_sc =TAUISS(float(dist), smtau, nu=1.0)
    return (float(dist) * u.kpc).to('pc'), tau_sc * u.s


@run_from_pkgdir
def dist_to_dm(l, b, dist):
    """ Convert distance to DM and compute scattering timescale
    
    Args:
        l (float): galactic latitude in degrees
        b (float): galactic longitude in degrees
        dist (float): Distance in kpc

    Returns:
        dm (astropy.Quantity), tau_sc (astropy.Quantity): Dispersion measure (pc / cm3), scattering timescale at 1 GHz (s)
    """
    dist  = np.array(dist, dtype='float32')
    dm    = np.zeros_like(dist)
    l_rad = np.deg2rad(l)
    b_rad = np.deg2rad(b)
    ndir = -1

    if np.isclose(dist, 0):       # Catch infinite timeout bug
        return 0.0 * u.pc / u.cm**3, 0.0 * u.s
    else:
        limit, sm, smtau, smtheta, smiso = dmdsm.dmdsm(l_rad, b_rad, ndir, dm, dist)

    tau_sc = TAUISS(float(dist), smtau, nu=1.0)
    return float(dm) * u.pc / u.cm**3, tau_sc * u.s


@run_from_pkgdir
def calculate_electron_density_xyz(x, y, z):
    """ Compute electron density at Galactocentric X, Y, Z coordinates 

    x,y,z are Galactocentric Cartesian coordinates, measured in kpc (NOT pc!)
    with the axes parallel to (l, b) = (90, 0), (180, 0), and (0, 90) degrees

    Args:
        x (float): Galactocentric coordinates in kpc
        y (float): Galactocentric coordinates in kpc
        z (float): Galactocentric coordinates in kpc

    Returns:
        ne_out (astropy.Quantity): Electron density in cm-3
    """
    ne_out = density.density_2001(x, y, z)
    return np.sum(ne_out[:7]) / u.cm**3




