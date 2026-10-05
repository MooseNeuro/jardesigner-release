# -*- coding: utf-8 -*-
#from .jardesigner import JarDesigner

# Import numpy before anything in this package imports moose. The
# pymoose 5.0.0 macOS wheels bundle a libgsl whose cblas_* symbols are
# left for the process to provide; under conda's Python the extension is
# bound immediately, so 'import moose' fails with "symbol not found in
# flat namespace '_cblas_caxpy'" unless numpy has already loaded a BLAS.
import numpy  # noqa: F401
