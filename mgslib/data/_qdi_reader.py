"""Read every row of QDI layers and save each as a CSV.  READ ONLY.

Run by ArcGIS Pro's Python, not by mgslib's own Python, because only arcpy
can open a ``.lyr``::

    python.exe _qdi_reader.py "<layer file>" "<output csv>" ["<layer file>" "<output csv>" ...]

What this script may do, and nothing more:
  - open the layer file with ``arcpy.mp.LayerFile``
  - change the layer's definition IN MEMORY ONLY (see below)
  - read rows with ``arcpy.da.SearchCursor``

It never calls ``LayerFile.save()``, never opens an edit session and never
uses an update or insert cursor.  The database and the layer file on disk are
left exactly as they were.

Why the definition is changed in memory: the published texture layer uses
``relateid`` as its object-ID field.  That is not unique (a borehole has many
samples), so ArcGIS quietly hides some rows.  Switching the in-memory copy to
``objectid``, which is unique, lets every row be read.
"""

import sys


def read_layer(layer_path, output_csv):
    import arcpy
    import pandas as pd

    layer = arcpy.mp.LayerFile(layer_path).listLayers()[0]
    # Both QDI layers have a unique objectid.  This must happen before anything
    # else reads the layer, or ArcGIS keeps using the published object-ID field.
    definition = layer.getDefinition("V3")
    connection = definition.featureTable.dataConnection
    if getattr(connection, "oIDFields", "objectid") != "objectid":
        connection.oIDFields = "objectid"
        layer.setDefinition(definition)          # in memory only; never saved

    fields = [f.name for f in arcpy.ListFields(layer)
              if f.type not in ("Geometry", "Blob") and f.name.upper() != "ESRI_OID"]
    with arcpy.da.SearchCursor(layer, fields + ["SHAPE@X", "SHAPE@Y"]) as cursor:
        rows = list(cursor)
    pd.DataFrame(rows, columns=fields + ["x", "y"]).to_csv(output_csv, index=False)
    print(len(rows))


if __name__ == "__main__":
    pairs = sys.argv[1:]
    for i in range(0, len(pairs), 2):
        read_layer(pairs[i], pairs[i + 1])
