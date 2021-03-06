#!/usr/bin/python
import os,sys
import shutil
import time
import tempfile
import osgeo.gdal, gdal
import osgeo.ogr, ogr
from osgeo.gdalconst import *
import numpy as np
import math
import argparse
from sensum_library.preprocess import *
from sensum_library.classification import *
from sensum_library.segmentation import *
from sensum_library.conversion import *
from sensum_library.segmentation_opt import *
from sensum_library.features import *
from sensum_library.secondary_indicators import *

def height(shadowShape,pixelWidth,pixelHeight,outShape='',ui_progress=None):
    
    '''Function for calculate and assign to shadows shapefile the height of building and length of shadow.            \
    Build new dataset (or shapefile if outputShape argument declared) with field Shadow_Len and Height which contains \
    respectively the height of relative building and the length of the shadow                                         \
    
    :param shadowShape: path of shadows shapefile (str)
    :param pixelWidth: value in meters of length of 1 pixel (float)
    :param pixelHeight: value in meters of length of 1 pixel (float)
    :param outputShape: path of output shapefile (char)
    :returns: Dataset of new features assigned (ogr.Dataset)
    '''
    driver = osgeo.ogr.GetDriverByName("ESRI Shapefile")
    shadowDS = driver.Open(shadowShape)
    pixelWidth = pixelWidth
    pixelHeight = pixelWidth
    shadowLayer = shadowDS.GetLayer()
    shadowFeaturesCount = shadowLayer.GetFeatureCount()
    if outShape == '':
        driver = osgeo.ogr.GetDriverByName("Memory")
    outDS = driver.CreateDataSource(outShape)
    outDS.CopyLayer(shadowLayer,"Shadows")
    outLayer = outDS.GetLayer()
    shadow_def = osgeo.ogr.FieldDefn('Shadow_Len', osgeo.ogr.OFTInteger)
    height_def = osgeo.ogr.FieldDefn('Height',osgeo.ogr.OFTReal)
    outLayer.CreateField(shadow_def)
    outLayer.CreateField(height_def)
    if ui_progress:
        ui_progress.progressBar.setMinimum(1)
        ui_progress.progressBar.setMaximum(shadowFeaturesCount)
    for i in range(0,shadowFeaturesCount):
        #Convert Shape to Raster
        shadowFeature = shadowLayer.GetFeature(i)
        x_min, x_max, y_min, y_max = WindowsMaker(shadowFeature).make_coordinates()
        cols = int(math.ceil(float((x_max-x_min)) / float(pixelWidth))) #definition of the dimensions according to the extent and pixel resolution
        rows = int(math.ceil(float((y_max-y_min)) / float(pixelHeight)))
        rasterDS = gdal.GetDriverByName('MEM').Create("", cols,rows, 1, GDT_UInt16)
        rasterDS.SetGeoTransform((x_min, pixelWidth, 0,y_max, 0, -pixelHeight))
        rasterDS.SetProjection(shadowLayer.GetSpatialRef().ExportToWkt())
        gdal.RasterizeLayer(rasterDS,[1], shadowLayer,burn_values=[1])

        #Make Band List
        inband = rasterDS.GetRasterBand(1) 
        band_list = inband.ReadAsArray().astype(np.uint16)
        #Process Raster with Scipy
        w = ndimage.morphology.binary_fill_holes(band_list)
        band_list = ndimage.binary_opening(w, structure=np.ones((3,3))).astype(np.uint16)
        #Calculate zone
        prj = rasterDS.GetProjection()
        srs = osr.SpatialReference(wkt=prj)
        zone = int(str(srs.GetAttrValue('projcs')).split('Zone')[1][1:-1])
        #Calculate shadow Lenght
        geo_transform = rasterDS.GetGeoTransform()
        easting = geo_transform[0]
        northing = geo_transform[3]
        a = utm2wgs84(easting, northing, zone)
        lon,lat = a[0],a[1]
        #lat,lon = northing, easting
        shadowLen = shadow_length(band_list,lat,lon,'2012/8/11 9:35:00')
        buildingHeight = building_height(lat,lon,'2012/8/11 9:35:00',shadowLen)
        print "buildingHeight: {}\nshadowLen: {}".format(buildingHeight,shadowLen)
        #insert value to init shape
        outFeature = outLayer.GetFeature(i)
        outFeature.SetField('Shadow_Len',int(shadowLen))
        outFeature.SetField('Height',buildingHeight)
        outLayer.SetFeature(outFeature)
        if ui_progress:
            ui_progress.progressBar.setValue(ui_progress.progressBar.value()+1)
    return outDS

def shadow_checker(buildingShape, shadowShape, date, idfield="ID", outputShape='', resize=0, ui_progress=None):

    '''Function to assign right shadows to buildings using the azimuth calculated from the raster acquisition date and time.\
    Build new dataset (or shapefile if outputShape argument declared) with field ShadowID and Height related to   \
    the id of relative shadow fileshape and the height of building calculated with sensum.ShadowPosition \
    class. Polygons are taken from the building-related layer. Shadow shapefile has to be just processed with height() function. 

    :param buildingShape: path of buildings shapefile (str)
    :param shadowShape: path of shadows shapefile (str)
    :param date: date of acquisition in EDT (example: '1984/5/30 17:40:56') (char)
    :param idfield: id field of shadows (char)
    :param outputShape: path of output shapefile (char)
    :param resize: resize value for increase dimension of the form expressed in coordinates as unit of measure (float)
    :returns: Dataset of new features assigned (ogr.Dataset)
    '''
    #get layers
    driver = ogr.GetDriverByName("ESRI Shapefile")
    buildingsDS = driver.Open(buildingShape)
    buildingsLayer = buildingsDS.GetLayer()
    buindingsFeaturesCount = buildingsLayer.GetFeatureCount()
    shadowDS = driver.Open(shadowShape)
    shadowLayer = shadowDS.GetLayer()
    if outputShape == '':
        driver = ogr.GetDriverByName("Memory")
    outDS = driver.CreateDataSource(outputShape)
    #copy the buildings layer and use it as output layer
    outDS.CopyLayer(buildingsLayer,"")
    outLayer = outDS.GetLayer()
    #add fields 'ShadowID' and 'Height' to outLayer
    fldDef = ogr.FieldDefn('ShadowID', ogr.OFTInteger)
    outLayer.CreateField(fldDef)
    fldDef = ogr.FieldDefn('Height', ogr.OFTReal)
    outLayer.CreateField(fldDef)
    #Calculate zone
    spatialRef = outLayer.GetSpatialRef()
    zone = int(str(spatialRef.GetAttrValue('projcs')).split('Zone')[1][1:-1])
    #get latitude and longitude from 1st features for calculate azimuth
    buildingFeature = outLayer.GetNextFeature()
    buildingGeometry = buildingFeature.GetGeometryRef().Centroid()
    longitude = float(buildingGeometry.GetX())
    latitude = float(buildingGeometry.GetY())
    longitude, latitude, altitude = utm2wgs84(longitude, latitude, zone)
    #calculate azimut and get right operators (> and <) as function used for filter the position of shadow
    position = ShadowPosition(date,latitude=latitude,longitude=longitude)
    position.main()
    xOperator, yOperator = position.operator()
    if ui_progress:
        ui_progress.progressBar.setValue(1)
        ui_progress.progressBar.setMinimum(1)
        ui_progress.progressBar.setMaximum(buindingsFeaturesCount)
    #loop into building features goint to make a window around each features and taking only shadow features there are into the window. 
    for i in range(buindingsFeaturesCount):
        print "{} di {} features".format(i+1,buindingsFeaturesCount)
        buildingFeature = outLayer.GetFeature(i)
        #make a spatial layer and get the layer
        maker = WindowsMaker(buildingFeature,resize)
        maker.make_feature()
        spatialDS = maker.get_shapeDS(shadowLayer)
        spatialLayer = spatialDS.GetLayer()
        spatialLayerFeatureCount = spatialLayer.GetFeatureCount()
        #check if there are any features into the spatial layer
        if spatialLayerFeatureCount:
            spatialFeature = spatialLayer.GetNextFeature()
            outFeature = outLayer.GetFeature(i)
            outGeometry = outFeature.GetGeometryRef().Centroid()
            xOutGeometry = float(outGeometry.GetX())
            yOutGeometry = float(outGeometry.GetY())
            #if the count of features is > 1 need to find the less distant feature
            if spatialLayerFeatureCount > 1:
                fields = []
                centros = []
                heights = []
                #loop into spatial layer
                while spatialFeature:
                    #calc of centroid of spatial feature
                    spatialGeometry = spatialFeature.GetGeometryRef().Centroid()
                    xSpatialGeometry = float(spatialGeometry.GetX())
                    ySpatialGeometry = float(spatialGeometry.GetY())
                    #filter the position of shadow, need to respect the right azimuth
                    if xOperator(xSpatialGeometry,xOutGeometry) and yOperator(ySpatialGeometry,yOutGeometry):
                        #saving id,centroid and heights into lists
                        fields.append(spatialFeature.GetField(idfield))
                        centros.append(spatialFeature.GetGeometryRef().Centroid())
                        heights.append(spatialFeature.GetField('Height'))
                    spatialFeature = spatialLayer.GetNextFeature()
                #calc distance from centroids
                distances = [outGeometry.Distance(centro) for centro in centros]
                #make multilist named datas with: datas[0] = distances, datas[1] = fields, datas[2] = heights and order for distances
                datas = sorted(zip(distances,fields,heights))
                #take less distant
                if datas:
                    outFeature.SetField("ShadowID",datas[0][1])
                    outFeature.SetField("Height",datas[0][2])
                    outLayer.SetFeature(outFeature)
            #spatialFeature = 1 so don't need to check less distant
            else:
                spatialGeometry = spatialFeature.GetGeometryRef().Centroid()
                xSpatialGeometry = float(spatialGeometry.GetX())
                ySpatialGeometry = float(spatialGeometry.GetY())
                if xOperator(xSpatialGeometry,xOutGeometry) and yOperator(ySpatialGeometry,yOutGeometry):
                    field = spatialFeature.GetField(idfield)
                    outFeature.SetField("ShadowID",field)
                    field = spatialFeature.GetField("Height")
                    outFeature.SetField("Height",field)
                    outLayer.SetFeature(outFeature)
                    spatialFeature = spatialLayer.GetNextFeature()
        if ui_progress:
            ui_progress.progressBar.setValue(ui_progress.progressBar.value()+1)
    return outDS

def args():
    parser = argparse.ArgumentParser(description='Height Calculate')
    parser.add_argument("input_shadow", help="echo the string you use here")
    parser.add_argument("input_buildings", help="echo the string you use here")
    parser.add_argument("date", help="echo the string you use here")
    parser.add_argument("output_shape", help="echo the string you use here")
    parser.add_argument("idfield", help="echo the string you use here")
    parser.add_argument("window_resize", help="echo the string you use here")
    args = parser.parse_args()
    return args

def main():
    arg = args()
    input_shadow = str(arg.input_shadow)
    input_buildings = str(arg.input_buildings)
    date = str(arg.date)
    output_shape = str(arg.output_shape)
    idfield = str(arg.idfield)
    window_resize = float(arg.window_resize)
    if os.path.isfile(output_shape):
        os.remove(output_shape)
    tmp_shadow_processed = tempfile.mkstemp()[1]
    os.remove(tmp_shadow_processed)
    height(input_shadow,0.5,0.5,outShape=tmp_shadow_processed)
    shadow_checker(input_buildings,tmp_shadow_processed, date, outputShape=output_shape, idfield=idfield, resize=window_resize)
    shutil.rmtree(tmp_shadow_processed)

if __name__ == "__main__":
    main()
