import os
import arcpy
import logging
import configparser


# Function Inputs:
# 1) Polyline boundary
# 2) index of the boundary, boundary of a polyline includes 2 points, Start point (index = 0) and End point (index = 1)
# 3) Buffer which gets from attribute tabel of the feature layer
# 4) wkid of the coordinate system
# Function Outputs:
# 1) Buffer of the polyline boundary
# 2) Boundary points of the polyline
def get_geo(data, ind, buffer, wkid):
    folder = "memory"
    # folder = "C:\Projects\LineExtention\PolyLine_Extension\ArcGIS\ArcGIS.gdb"
    # Create the point object
    pt: arcpy.Point = data[ind]
    # Define the Spatial reference
    sr = arcpy.SpatialReference(wkid)
    # Set the Spatial reference of the Point object
    pt_geometry = arcpy.PointGeometry(pt, spatial_reference=sr)
    buffer_fc = os.path.join(folder, "buffer_fc")
    # TODO if the parameters can be changed the parameters should be put in the config.ini file
    buffer_geometry = arcpy.analysis.Buffer(pt_geometry, buffer_fc, "{} NauticalMilesInt".format(buffer), "FULL",
                                            "FLAT", "NONE",
                                            None, "PLANAR")
    logging.info("Buffer of the polyline object is finished")
    return buffer_geometry, pt


# This Function finds the coordinates of the extension point with respect to the intersection point
def get_opposite_coordinates(center_coord, intersect_coord):
    return 2 * center_coord - intersect_coord


# Function Inputs:
# 1) Polyline Feature Class
# 2) Polyline boundary object
# 3) Index of the polyline boundaries
# 4) Buffer radius which gets from Feature layer attribute table
# 5) wkid of the coordinate system
# 6) i is the value of row's OBJECTID should be selected
# Function Outputs
# 1) Extension part of the polyline
def get_extension_line(fc, data, ind, buffer, wkid, i) -> arcpy.Polyline:
    folder = "memory"
    # folder = "C:\Projects\LineExtention\PolyLine_Extension\ArcGIS\ArcGIS.gdb"
    try:
        point_buffered, point_center = get_geo(data, ind, buffer, wkid)
    except Exception as e:
        logging.error("There is error {} in making buffer function".format(e))

    # Define the output feature class object's name in the memory
    point_fc = os.path.join(folder, "pointIntersection")
    try:
        # Make feature layer from feature class because of applying selection
        arcpy.MakeFeatureLayer_management(fc, "layer")
        # Gets the OBJECTID of the interested polyline
        object_id = [row[0] for row in arcpy.da.SearchCursor("layer", "OBJECTID")][i]
        # Apply selection to the polyline
        arcpy.management.SelectLayerByAttribute("layer", "NEW_SELECTION",
                                                "OBJECTID = {}".format(object_id))
        # Doing intersection between buffer polygon and selected polyline
        arcpy.analysis.Intersect(["layer", point_buffered], point_fc, output_type="POINT")
        # Clear the selection
        arcpy.management.SelectLayerByAttribute("layer", "CLEAR_SELECTION")
        logging.info("Intersection is finished")
    except Exception as e:
        logging.error("There is error {} in doing intersection".format(e))

    # Gets the Geometry of the intersection points
    geo = [row[0] for row in arcpy.da.SearchCursor(point_fc, "Shape")][0]
    logging.info("Geometry of the intersection points are extracted")
    try:
        point1 = arcpy.Point()
        # Finds the extention point coordinates
        point1.X = get_opposite_coordinates(point_center.X, geo[0])
        point1.Y = get_opposite_coordinates(point_center.Y, geo[1])
        array = arcpy.Array([point1, point_center])
        # Generate polyline from center of buffer and extension point
        features = arcpy.Polyline(array)
    except Exception as e:
        logging.error("There is error {} in making polyline".format(e))
    return features


# Function Inputs
# 1) Polyline Feature class
# 2) Output feature class
# 3) wkid of the coordinate system
def main(fc, output_fc, wkid):
    extended_line = []
    # counter is the number of the row of the interested polyline
    counter = 0

    with arcpy.da.SearchCursor(fc, ["SHAPE@", buffer_start, buffer_end, ID]) as cursor:
        for row in cursor:
            # Access the geometry object
            geom_line: arcpy.Polyline = row[0]
            data = geom_line.boundary()
            buffer_s = row[1]
            buffer_e = row[2]
            # Extensions
            first_line = get_extension_line(fc, data, 0, buffer_s, wkid, counter)
            last_line = get_extension_line(fc, data, 1, buffer_e, wkid, counter)
            # Merge line with the extensions
            geom_line = geom_line.union(first_line)
            geom_line = geom_line.union(last_line)
            extended_line.append((geom_line, row[3]))
            counter += 1
    try:
        # Create Polyline Featureclass
        arcpy.CreateFeatureclass_management(gdb_path, output_fc.split("\\")[-1], "POLYLINE")
        # Create ID field in the Polyline  featureclass
        arcpy.AddField_management(output_fc, ID, "Long", 9)
        # Insert the list of polylines into the Featureclass
        with arcpy.da.InsertCursor(output_fc, ["SHAPE@", ID]) as cursor:
            for polyline in extended_line:
                cursor.insertRow(polyline)

        fc_path = os.path.join(gdb_path, fc_name)
        arcpy.MakeFeatureLayer_management(output_fc, output_fc.split("\\")[-1])
        # AddJoin of two featureclasses
        arcpy.management.JoinField(
            in_data=output_fc.split("\\")[-1],
            in_field=ID,
            join_table=fc_path,
            join_field=ID,
            fields=None,
            fm_option="NOT_USE_FM",
            field_mapping=None
        )
        logging.info("Merging all the extensions are done")
    except Exception as e:
        logging.error("There is error {} in doing merge".format(e))


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    logging.basicConfig(filename="file.log",
                        level=logging.INFO,
                        format='%(levelname)s   %(asctime)s   %(message)s')
    logging.info("All setting of the logging is done")

    # Read Config file
    try:
        config = configparser.ConfigParser()
        config.read('config.ini')
        gdb_path = config.get('config', 'gdb_path')
        fc_name = config.get('config', 'fc_name')
        out_fc = config.get('config', 'output')
        buffer_start = config.get('config', 'buffer_start')
        buffer_end = config.get('config', 'buffer_end')
        wkid = config.getint('config', 'wkid')
        ID = config.get('config', 'unique_id')
        logging.info("All paths are defined")
    except Exception as ex:
        logging.error("There is an error {} in reading config.ini file".format(ex))

    try:
        # Set the workspace
        arcpy.env.workspace = gdb_path
        # Set the environment overwrite
        arcpy.env.overwriteOutput = True
        fc = r"{}\{}".format(gdb_path, fc_name)
        main(fc, out_fc, wkid)
        logging.info("The script finished successfully")
    except Exception as ex:
        logging.error("There is an error {} in main function".format(ex))
