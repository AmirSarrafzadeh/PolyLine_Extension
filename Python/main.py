import os
import arcpy
import logging
import configparser


def get_geo(data, ind, buffer, wkid):
    pt: arcpy.Point = data[ind]
    pt_geometry = arcpy.PointGeometry(pt, spatial_reference=wkid)
    buffer_geometry = pt_geometry.buffer(buffer)
    logging.info("Buffer of the line is finished")
    return buffer_geometry, pt


def get_opposite_coordinates(center_coord, interect_coord):
    return 2 * center_coord - interect_coord


def get_extension_line(fc, data, ind, buffer, wkid) -> arcpy.Polyline:
    folder = "memory"
    try:
        point_buffered, point_center = get_geo(data, ind, buffer, wkid)
    except Exception as ex:
        logging.error("There is error {} in making buffer function".format(ex))
    point_fc = os.path.join(folder, "pointIntersection")
    try:
        arcpy.analysis.Intersect([fc, point_buffered], point_fc, output_type="POINT")
        logging.info("Intersection is finished")
    except Exception as ex:
        logging.error("There is error {} in doing intersection".format(ex))
    geo = [row[0] for row in arcpy.da.SearchCursor(point_fc, "Shape")][0]
    logging.info("Geometry of the intersection points are extracted")
    try:
        point1 = arcpy.Point()
        point1.X = get_opposite_coordinates(point_center.X, geo[0])
        point1.Y = get_opposite_coordinates(point_center.Y, geo[1])
        array = arcpy.Array([point1, point_center])
        features = arcpy.Polyline(array)
    except Exception as ex:
        logging.error("There is error {} in making polyline".format(ex))
    return features


def main(fc, buffer_s, buffer_e, output_fc, wkid=3857):
    extended_line = []
    with arcpy.da.SearchCursor(fc, ["SHAPE@"]) as cursor:
        for row in cursor:
            # Access the geometry object and print its type and coordinates
            geom_line: arcpy.Polyline = row[0]
            data = geom_line.boundary()
            first_line = get_extension_line(fc, data, 0, buffer_s, wkid)
            last_line = get_extension_line(fc, data, 1, buffer_e, wkid)
            # merge line with the extension
            geom_line = geom_line.union(first_line)
            geom_line = geom_line.union(last_line)
            extended_line.append(geom_line)

    try:
        arcpy.management.Merge(extended_line, output_fc)
        logging.info("Merging all the extensions are done")
    except Exception as ex:
        logging.error("There is error {} in doing merge".format(ex))


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
        buffer_start = config.getint('config', 'buffer_start')
        buffer_end = config.getint('config', 'buffer_end')
        wkid = config.getint('config', 'wkid')
        logging.info("All paths are defined")
    except Exception as ex:
        logging.error("There is an error {} in reading config.ini file".format(ex))

    try:
        arcpy.env.workspace = gdb_path
        arcpy.env.overwriteOutput = True
        fc = r"{}\{}".format(gdb_path, fc_name)
        main(fc, buffer_start, buffer_end, out_fc, wkid)
        logging.info("The script finished successfully")
    except Exception as ex:
        logging.error("There is an error {} in reading config.ini file".format(ex))


