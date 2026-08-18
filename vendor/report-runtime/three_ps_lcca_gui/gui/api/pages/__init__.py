"""
gui/api/pages/

Each module here registers one page/chunk with the API (registry.py's
CHUNK_PAGE_MAP) as a side effect of being imported. Importing this package
imports every page module below, so the whole API surface is wired up by a
single `import three_ps_lcca_gui.gui.api.pages`.

To add a new page to the API:

  1. Create pages/<chunk_name>.py following bridge_data.py's pattern:
     import the page's widget class + its FieldDef list (+ warn rules if any)
     from gui/components/<page>/main.py, then call `register_chunk(...)`.
  2. Import that module below.

That's it - no changes needed in server.py, bridge.py, or registry.py. The
routes, schema endpoint, validation, and locked-field handling are all
already generic over whatever's in CHUNK_PAGE_MAP.
"""

from . import bridge_data  # noqa: F401
from . import general_info  # noqa: F401
from . import financial_data  # noqa: F401
from . import maintenance  # noqa: F401
from . import demolition  # noqa: F401
from . import structure  # noqa: F401
from . import carbon_emission  # noqa: F401
from . import machinery_emissions  # noqa: F401
