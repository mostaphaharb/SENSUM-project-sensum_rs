'''
.. module:: stack_satellite
   :platform: Unix, Windows
   :synopsis: Workflow for processing of medium resolution imagery (Landsat)

.. moduleauthor:: Mostapha Harb <mostapha.harb@eucentre.it>
.. moduleauthor:: Daniele De Vecchi <daniele.devecchi03@universitadipavia.it>
.. moduleauthor:: Daniel Aurelio Galeazzo <dgaleazzo@gmail.com>
   :organization: EUCENTRE Foundation / University of Pavia 
'''
'''
---------------------------------------------------------------------------------
Created on May 13, 2013
Last modified on May 12, 2014

---------------------------------------------------------------------------------
Project: Framework to integrate Space-based and in-situ sENSing for dynamic 
         vUlnerability and recovery Monitoring (SENSUM)

Co-funded by the European Commission under FP7 (Seventh Framework Programme)
THEME [SPA.2012.1.1-04] Support to emergency response management
Grant agreement no: 312972

---------------------------------------------------------------------------------
License: This file is part of SensumTools.

    SensumTools is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    SensumTools is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with SensumTools.  If not, see <http://www.gnu.org/licenses/>.
---------------------------------------------------------------------------------
'''

'''
--------------------------------------------------------------------------
    Stack satellite - Works on a stack of Landsat 5 and 7 images
--------------------------------------------------------------------------                                
Created on May 13, 2013

Authors: Mostapha Harb - Daniele De Vecchi
         SENSUM Project
         University of Pavia - Remote Sensing Laboratory / EUCENTRE Foundation
         
In case of bugs or questions please contact: 
daniele.devecchi03@universitadipavia.it
mostapha.harb@eucentre.it

Notes: 
Input folders must be renamed using YYYY-MM-DD of acquisition.
The input files are supposed to be landsat files with STANDARD NAMES (example "LT51800331991183XXX01_B1.TIF").
This procedure has been selected in order to facilitate the user.
--------------------------------------------------------------------------
'''

################# Parameters to set #################

##Fundamental
sat_folder = 'F:\\Sensum_xp\\Van_process\\'   ##path of the folder containing satellite images
#input_shapefile = 'F:\\Sensum_xp\\Van_process\\Area_cut.shp' #path of the shapefile
input_shapefile = 'F:\\Sensum_xp\\dilkushi water mask\\New_Mask_Inner_lake_rpj.shp'
quantization_mode = 'kmeans' #'linear' or 'kmeans'
#opt_polygon = 'F:\\Sensum_xp\\Cologne_process\\roi.shp'
segmentation_name = 'Edison' #or 'Meanshift'
select_criteria = 4
nloops = 3
n_classes = 5
ref_dir = ''
##Optional

#ref_dir = '/Users/daniele/Documents/Sensum/Izmir/Landsat5/LT51800331984164XXX04/'

#--- Options ---
restrict_to_city = True
coregistration = False

#Pixel-based methods
builtup_index_method = True
pca_index_method = False
pca_classification_method = False

#Texture-based method
dissimilarity_method = False

#Object-based methods
band_combination = ''
supervised_method = False
unsupervised_method = False
supervised_polygon = ''

#Change detection
change_detection_method = True
################# End Parameters #################

#bug with Landsat 8: fix the water mask and built-up area band, not the same as the other images -> FIXED!!

import os,sys
sys.path.append("C:\\OSGeo4W64\\apps\\Python27\\Lib\\site-packages")
sys.path.append("C:\\OSGeo4W64\\apps\\orfeotoolbox\\python")
os.environ["PATH"] = os.environ["PATH"] + ";C:\\OSGeo4W64\\bin"
os.environ["ITK_AUTOLOAD_PATH"] = "C:\\OSGeo4W64\\apps\\orfeotoolbox\\applications"
#print sys.path
#print os.environ["PATH"]
import time
import subprocess
from skimage.morphology import square, closing
import osgeo.gdal
import otbApplication
from sensum.conversion import *
from sensum.classification import *
from sensum.preprocess import *
from sensum.features import *
from sensum.segmentation_opt import *
from sensum.multi import *

#Define the data_type of separator differentiating between windows and unix like systems
if os.name == 'posix':
    separator = '/'
else:
    separator = '\\'

sat_folder = sat_folder + separator     
data_type = np.int32
start_time=time.time()
dirs = os.listdir(sat_folder) #list of folders inside the satellite folder

if __name__ == '__main__':

    print 'List of files and folders: ' + str(dirs)

    band_list = []
    cd_names = []
    built_up_area_pca_list = []
    built_up_area_list = []
    dissimilarity_list = []

    #reference image - if not defined the first in alphabetic order is chosen
    c = 0

    if ref_dir is None or ref_dir == '': #if a reference image is not provided, the first in alphabetic order is chosen
        print 'Reference directory not specified - The first folder in alphabetical order will be chosen'
        while (os.path.isfile(dirs[c]) == True):### to avoid taking the files in the dirs as a reference folder so, the program will search for the first folder
            c=c+1
        else:
            reference_dir = dirs[c]
        ref_dir = sat_folder + reference_dir + separator #first directory assumed to be the reference
    ref_files = os.listdir(ref_dir)

    if restrict_to_city == True: #Clip the original images with the provided shapefile
        ref_list = [s for s in ref_files if ".TIF" in s and not "_city" in s and "aux.xml" not in s] #look for original landsat files
        
        for j in range(0,len(ref_list)):
            print ref_list[j]
            #clip_rectangular(input_raster,data_type,input_shape,output_raster)
            clip_rectangular(ref_dir+ref_list[j],data_type,input_shapefile,ref_dir+ref_list[j][:-4]+'_city.TIF')
            #print 'C:\\OSGeo4W64\\bin\\gdalwarp.exe -q -cutline "'+ input_shapefile +'" -crop_to_cutline -of GTiff "'+ref_dir+ref_list[j]+'" "'+ref_dir+ref_list[j][:-4]+'_city.TIF"'
            #os.system('C:/OSGeo4W64/bin/gdalwarp.exe -q -cutline "'+ input_shapefile +'" -crop_to_cutline -of GTiff '+ref_dir+ref_list[j]+' '+ref_dir+ref_list[j][:-4]+'_city.TIF')
        ref_files = os.listdir(ref_dir)
        ref_list = [s for s in ref_files if "_city.TIF" in s and "aux.xml" not in s]
    else: 
        ref_list = [s for s in ref_files if ".TIF" in s and "aux.xml" not in s]
    print ref_list

    for n in range(0,len(ref_list)):
        band_ref = read_image(ref_dir+ref_list[n],data_type,0)
        band_list.append(band_ref[0])
       
    rows_ref,cols_ref,nbands_ref,geo_transform_ref,projection_ref = read_image_parameters(ref_dir+ref_list[0])
    
    print len(band_list)
    if len(band_list) < 10:
        print 'not re-adjusted to match L8'
        #band_list = normalize_to_L8(band_list)
    elif len(band_list) > 10:
        #band_list[0],band_list[1],band_list[2],band_list[3],band_list[4],band_list[5],band_list[6],band_list[7],band_list[8]= band_list[3],band_list[4],band_list[5],band_list[6],band_list[7],band_list[0],band_list[1],band_list[8],band_list[9]
        #band_list[0],band_list[1],band_list[2],band_list[3],band_list[4],band_list[5]= band_list[1],band_list[2],band_list[3],band_list[4],band_list[5],band_list[9]
        new_list = (band_list[3],band_list[4],band_list[5],band_list[6],band_list[7],band_list[0],band_list[1],band_list[8],band_list[9])
        band_list = new_list
        print band_list[8].shape
    #pca needs bands 1,2,3,4,5 or bands 1,2,3,4,5,7
    #indexes need bands 1,2,3,4,5,7
    if change_detection_method == True:
        change_detection_list = band_calculation(band_list, ['Index12','Index11','Index10','Index9','Index8','Index7','Index6','Index5','Index4','Index3','Index2','Index1'])
        shp2rast(input_shapefile,input_shapefile[:-4]+'.tif',rows_ref,cols_ref,'Conv',0,0,x_min=0,x_max=0,y_min=0,y_max=0)
        
    if builtup_index_method == True or supervised_method == True or unsupervised_method == True:
        features_list = band_calculation(band_list,['SAVI','NDVI','NDBI','MNDWI','BUILT_UP']) #extract indexes
        #features_list[3] = features_list[3]*1000
        features_list[4] = features_list[4]*1000
        write_image(features_list,np.float32,0,ref_dir+'built_up_index.TIF',rows_ref,cols_ref,geo_transform_ref,projection_ref) #write built-up index to file

    if builtup_index_method == True or change_detection_method == True:
        mask_vegetation = np.greater(features_list[2],features_list[0]) #exclude vegetation
        #mask_water = np.less(features_list[3],features_list[2]) #exclude water
        #write_image([mask_water],np.uint8,0,ref_dir+'mask_water.TIF',rows_ref,cols_ref,geo_transform_ref,projection_ref)
        mask_water = read_image(input_shapefile[:-4]+'.tif',np.uint8,0)
        mask_soil = np.greater(features_list[3]/1000,0) #exclude soil
        if builtup_index_method == True:
            built_up_area = np.choose(np.logical_and(mask_soil,np.logical_and(mask_water,mask_vegetation)),(features_list[4]/1000,0))
            built_up_area_list.append(built_up_area) 
        if change_detection_method == True:
            cd_list_masked = []
            for mw in range(0,len(change_detection_list)):
                cd_list_masked.append(np.choose(mask_water[0],(0,change_detection_list[mw])))
            write_image(cd_list_masked,np.float32,0,ref_dir+'change_detection.TIF',rows_ref,cols_ref,geo_transform_ref,projection_ref) #write built-up index to file
            cd_names.append(ref_dir+'change_detection.TIF')
            unsupervised_classification_otb(ref_dir+'change_detection.TIF',ref_dir+'change_detection_classification.TIF',5,1000)
            
            
    if pca_index_method == True or pca_classification_method == True:
        input_pca_list = (band_list[0],band_list[1],band_list[2],band_list[3],band_list[4])
        pca_mean,pca_mode,pca_second_order,pca_third_order = pca(input_pca_list)
        
        pca_built_up = pca_index(pca_mean,pca_mode,pca_second_order,pca_third_order)
        
        if pca_index_method == True:
            mask_water = np.less(pca_second_order,pca_mean) #exclude water
            mask_vegetation = np.greater(pca_third_order,pca_second_order) #exclude vegetation
            mask_soil = np.less(pca_built_up,0) #exclude soil
            built_up_area_pca = np.logical_and(mask_soil,np.logical_and(mask_water,mask_vegetation))
            built_up_area_pca_list.append(built_up_area_pca)
        
        if pca_classification_method == True:
            write_image((pca_mean,pca_mode,pca_second_order,pca_third_order,pca_built_up),np.float32,0,ref_dir+'pca.TIF',rows_ref,cols_ref,geo_transform_ref,projection_ref)
            unsupervised_classification_otb(ref_dir+'pca.TIF',ref_dir+'pca_unsupervised.TIF',5,10)
    write_image((band_list[0],band_list[1],band_list[2],band_list[3],band_list[6]),np.uint16,0,ref_dir+'stack.TIF',rows_ref,cols_ref,geo_transform_ref,projection_ref)        
    if supervised_method == True or dissimilarity_method == True:
        print 'Segmentation'
        '''
        driver_shape = osgeo.ogr.GetDriverByName('ESRI Shapefile')
        inDS = driver_shape.Open(input_shapefile, 0)
        if inDS is None:
            print 'Could not open file'
            sys.exit(1)
        inLayer = inDS.GetLayer()
        temp = split_shape(inLayer,0)
        temp_layer = temp.GetLayer()
        reference_polygon_matrix, ref_polygon_geo_transform = polygon2array(temp_layer,geo_transform_ref[1],abs(geo_transform_ref[5])) 
        temp.Destroy() 
        
        ext_patch_list,patch_geo_transform = create_extended_patch(band_list,reference_polygon_matrix,geo_transform_ref,ref_polygon_geo_transform,0.3,False)   
        e = call_optimizer(segmentation_name,[ext_patch_list],[reference_polygon_matrix],[patch_geo_transform],[ref_polygon_geo_transform],projection_ref,select_criteria,nloops)
        '''
        if segmentation_name == 'Edison':
            #edison_otb(ref_dir+'built_up_index.TIF','vector',ref_dir+'built_up_index_seg.shp',int(e[0]),float(e[1]),0,0)
            edison_otb(ref_dir+'built_up_index.TIF','vector',ref_dir+'built_up_index_seg.shp',0,0,0,0)
            #edison_otb(ref_dir+'stack.TIF','vector',ref_dir+'built_up_index_seg.shp',0,0,0,0)
        if segmentation_name == 'Meanshift':
            #meanshift_otb(ref_dir+'built_up_index.TIF','vector',ref_dir+'built_up_index_seg.shp',int(e[0]),float(e[1]),0,0,0)
            meanshift_otb(ref_dir+'built_up_index.TIF','vector',ref_dir+'built_up_index_seg.shp',0,0,0,0,0)
        #inDS.Destroy()   
             
    if unsupervised_method == True:
        #include stuff
        print 'to implement'
        
    #Extract mode from segments
    if supervised_method == True or unsupervised_method == True:
        #built-up -> polygon around vegetation or water -> optimizer -> edison -> feature extraction mode -> unsupervised classification (4 classes)
        #Input can change according to the performance: built-up index, single band, rgb combination, panchromatic band
        class_to_segments(ref_dir+'built_up_index.TIF',ref_dir+'built_up_index_seg.shp',ref_dir+'mode.shp')
        shp2rast(ref_dir+'mode.shp',ref_dir+'mode.TIF',rows_ref,cols_ref,'Class',0,0,0,0,0,0) #conversion of the segmentation results from shape to raster for further processing
        unsupervised_classification_otb(ref_dir+'mode.TIF',ref_dir+'mode_class.TIF',n_classes,1)
        
        #Define if a vegetation filter is needed
        '''
        mask_veg = np.less(NDBI-SAVI,0) 
        WriteOutputImage(ref_dir+ref_list_city[0],ref_dir,'','vegetation_mask.TIF',0,0,0,1,[SAVI])
        veg_opening = binary_opening(mask_veg,square(5))
        WriteOutputImage(ref_dir+ref_list_city[0],ref_dir,'','vegetation_mask_opening.TIF',0,0,0,1,[veg_opening])
        veg_filt = np.equal(veg_opening,0)
        out_veg_filt = np.choose(veg_filt,(0,(list_mode_class[0])))
        '''
    if dissimilarity_method == True:
        #include Daniel's function with multiprocessing
        output_list = []
        if len(band_list) < 9:
            band_diss = (band_list[0],band_list[1],band_list[6])
        else:
            band_diss = (band_list[0],band_list[1],band_list[7])
        multiproc = Multi()
        window_dimension = 7
        index = 'dissimilarity'
        quantization_factor = 64
        band_list_q = linear_quantization(band_diss,quantization_factor)
        rows_w,cols_w = band_list_q[0].shape
        print rows_w,cols_w
        for i in range(0,rows_w):
            multiproc.put(Task_moving(i, rows_w, cols_w, band_diss,band_list_q,window_dimension,index,quantization_factor))
        multiproc.kill()
        #Write results
        output_ft_1 = np.zeros((len(band_diss),rows_w,cols_w)).astype(np.float32)
        while rows_w:
            res = multiproc.result()
            if res.size != 1:
                res = res.reshape(res.size/4,4)
                for i in range(res.size/4):
                    tmp = res[i]
                    b,index_row,index_col,feat1 = int(tmp[0]),int(tmp[1]),int(tmp[2]),tmp[3]
                    #print b,index_row,index_col,feat1
                    output_ft_1[b][index_row][index_col]=feat1
            rows_w -= 1
        for b in range(0,len(band_diss)):
            output_list.append(output_ft_1[b][:][:])
        print len(output_list)
        write_image(output_list,np.float32,0,ref_dir+'dissimilarity.TIF',rows_ref,cols_ref,geo_transform_ref,projection_ref) #write built-up index to file
        value_to_segments(ref_dir+'dissimilarity.TIF',ref_dir+'built_up_index_seg.shp',ref_dir+'dissimilarity.shp')
        
        for b in range(0,len(output_list)):
            shp2rast(ref_dir+'dissimilarity.shp',ref_dir+'dissimilarity_mean'+str(b+1)+'.tif',rows_ref,cols_ref,'Mean'+str(b+1),pixel_width=0,pixel_height=0,x_min=0,x_max=0,y_min=0,y_max=0)
            mat = read_image(ref_dir+'dissimilarity_mean'+str(b+1)+'.tif',np.uint16,0)
            dissimilarity_list.append(mat[0])
        write_image(dissimilarity_list,np.float32,0,ref_dir + 'dissimilarity_mean.tif',rows_ref,cols_ref,geo_transform_ref,projection_ref)
        dissimilarity_list = []
        unsupervised_classification_otb(ref_dir+'dissimilarity_mean.tif',ref_dir+'dissimilarity_mean_class.tif',n_classes,10)
        rast2shp(ref_dir+'dissimilarity_mean_class.tif',ref_dir+'dissimilarity_mean_class.shp')
        #dissimilarity_list.append(output_list)
        del output_list
        del output_ft_1
        del multiproc
    
    for i in range(0,len(dirs)):
        band_list = []
        if (os.path.isfile(sat_folder+dirs[i]) == False) and ((ref_dir!=sat_folder+dirs[i]+separator)):
            target_dir = sat_folder+dirs[i]+separator
            img_files = os.listdir(target_dir)
            
            if restrict_to_city == True: #Clip the original images with the provided shapefile
                target_list = [s for s in img_files if ".TIF" in s and not "_city" in s] #look for original landsat files
                
                for j in range(0,len(target_list)):
                    print target_list[j]
                    #clip_rectangular(input_raster,data_type,input_shape,output_raster)
                    clip_rectangular(target_dir+target_list[j],data_type,input_shapefile,target_dir+target_list[j][:-4]+'_city.TIF')
                    #os.system('C:/OSGeo4W64/bin/gdalwarp.exe -q -cutline "'+ input_shapefile +'" -crop_to_cutline -of GTiff "'+target_dir+target_list[j]+'" "'+target_dir+target_list[j][:-4]+'_city.TIF"')
                target_files = os.listdir(target_dir)
                target_list = [s for s in target_files if "_city.TIF" in s and "aux.xml" not in s]
            else:
                target_files = os.listdir(target_dir) 
                target_list = [s for s in target_files if ".TIF" in s and "aux.xml" not in s]
            print target_list
            rows,cols,nbands,geo_transform,projection = read_image_parameters(target_dir+target_list[0])
            if coregistration == True: #OpenCV needs byte values (from 0 to 255)
                F_B(sat_folder,target_dir,ref_dir)
            for n in range(0,len(target_list)):
                band_target = read_image(target_dir+target_list[n],data_type,0)
                band_list.append(band_target[0])
                
            if len(band_list) < 10:
                print 'not re-adjusted to match L8'
                #band_list = normalize_to_L8(band_list)
            elif len(band_list) > 10:
                #table of correspondence between landsat 5/7 and 8
                '''
                L5/7  ->   L8
                band1    band2
                band2    band3
                band3    band4
                band4    band5
                band5    band6
                band7    band7
                band6_1  band10
                band6_2  band11
                
                alphabetic order is putting 10 and 11 before 1, 2, ...
                '''
                #band_list[0],band_list[1],band_list[2],band_list[3],band_list[4],band_list[5],band_list[6],band_list[7],band_list[8]= band_list[3],band_list[4],band_list[5],band_list[6],band_list[7],band_list[0],band_list[1],band_list[8],band_list[9]
                #band_list[0],band_list[1],band_list[2],band_list[3],band_list[4],band_list[5]= band_list[1],band_list[2],band_list[3],band_list[4],band_list[5],band_list[9] #built-up works, mask water not
                new_list = (band_list[3],band_list[4],band_list[5],band_list[6],band_list[7],band_list[0],band_list[1],band_list[8],band_list[9])
                band_list = new_list
                print len(new_list),len(band_list)
            #else:
                #band_list = (band_list[0],band_list[1],band_list[2],band_list[3],band_list[4])
            rows_target,cols_target,nbands_target,geo_transform_target,projection_target = read_image_parameters(target_dir+target_list[0])
            #pca needs bands 1,2,3,4,5 or bands 1,2,3,4,5,7
            #indexes need bands 1,2,3,4,5,7
            if change_detection_method == True:
                change_detection_list = band_calculation(band_list, ['Index12','Index11','Index10','Index9','Index8','Index7','Index6','Index5','Index4','Index3','Index2','Index1'])

            if builtup_index_method == True or supervised_method == True or unsupervised_method == True:
                features_list = band_calculation(band_list,['SAVI','NDVI','NDBI','MNDWI','BUILT_UP']) #extract indexes
                features_list[3] = features_list[3]*1000
                features_list[4] = features_list[4]*1000
                write_image(features_list,np.float32,0,target_dir+'built_up_index.TIF',rows_target,cols_target,geo_transform_target,projection_target) #write built-up index to file
            
            if builtup_index_method == True or change_detection_method == True:
                mask_vegetation = np.greater(features_list[2],features_list[0]) #exclude vegetation
                #mask_water = np.less(features_list[3],features_list[2]) #exclude water
                #write_image([mask_water],np.uint8,0,target_dir+'mask_water.TIF',rows_ref,cols_ref,geo_transform_ref,projection_ref)
                mask_water = read_image(input_shapefile[:-4]+'.tif',np.uint8,0)
                mask_soil = np.greater(features_list[3]/1000,0) #exclude soil
                if builtup_index_method == True:
                    built_up_area = np.choose(np.logical_and(mask_soil,np.logical_and(mask_water,mask_vegetation)),(features_list[4]/1000,0))
                    built_up_area_list.append(built_up_area) 
                if change_detection_method == True:
                    cd_list_masked = []
                    for mw in range(0,len(change_detection_list)):
                        cd_list_masked.append(np.choose(mask_water[0],(0,change_detection_list[mw])))
                    write_image(cd_list_masked,np.float32,0,target_dir+'change_detection.TIF',rows_target,cols_target,geo_transform_target,projection_target) #write built-up index to file
                    cd_names.append(target_dir+'change_detection.TIF')
                    unsupervised_classification_otb(target_dir+'change_detection.TIF',target_dir+'change_detection_classification.TIF',5,10)
            
            if pca_index_method == True or pca_classification_method == True:
                input_pca_list = (band_list[0],band_list[1],band_list[2],band_list[3],band_list[4])
                pca_mean,pca_mode,pca_second_order,pca_third_order = pca(input_pca_list)
                
                pca_built_up = pca_index(pca_mean,pca_mode,pca_second_order,pca_third_order)
                
                if pca_index_method == True:
                    mask_water = np.less(pca_second_order,pca_mean) #exclude water
                    mask_vegetation = np.greater(pca_third_order,pca_second_order) #exclude vegetation
                    mask_soil = np.less(pca_built_up,0) #exclude soil
                    built_up_area_pca = np.logical_and(mask_soil,np.logical_and(mask_water,mask_vegetation))
                    built_up_area_pca_list.append(built_up_area_pca)
                
                if pca_classification_method == True:
                    write_image((pca_mean,pca_mode,pca_second_order,pca_third_order,pca_built_up),np.float32,0,target_dir+'pca.TIF',rows_target,cols_target,geo_transform_target,projection_target)
                    unsupervised_classification_otb(target_dir+'pca.TIF',target_dir+'pca_unsupervised.TIF',5,10)
            if len(band_list) <9:
                write_image((band_list[0],band_list[1],band_list[2],band_list[3],band_list[6]),np.uint16,0,target_dir+'stack.TIF',rows_target,cols_target,geo_transform_target,projection_target)
            else:
                write_image((band_list[0],band_list[1],band_list[2],band_list[3],band_list[7]),np.uint16,0,target_dir+'stack.TIF',rows_target,cols_target,geo_transform_target,projection_target)    
            if supervised_method == True or dissimilarity_method == True:
                print 'Segmentation'
                '''
                driver_shape = osgeo.ogr.GetDriverByName('ESRI Shapefile')
                inDS = driver_shape.Open(input_shapefile, 0)
                if inDS is None:
                    print 'Could not open file'
                    sys.exit(1)
                inLayer = inDS.GetLayer()
                temp = split_shape(inLayer,0)
                temp_layer = temp.GetLayer()
                reference_polygon_matrix, ref_polygon_geo_transform = polygon2array(temp_layer,geo_transform_target[1],abs(geo_transform_target[5])) 
                temp.Destroy() 
                
                ext_patch_list,patch_geo_transform = create_extended_patch(band_list,reference_polygon_matrix,geo_transform_target,ref_polygon_geo_transform,0.3,False)   
                e = call_optimizer(segmentation_name,[ext_patch_list],[reference_polygon_matrix],[patch_geo_transform],[ref_polygon_geo_transform],projection_target,select_criteria,nloops)
                '''
                if segmentation_name == 'Edison':
                    #(input_raster,output_mode,output_file,spatial_radius,range_radius,min_size,scale)
                    #edison_otb(target_dir+'built_up_index.TIF','vector',target_dir+'built_up_index_seg.shp',int(e[0]),float(e[1]),0,0)
                    edison_otb(target_dir+'built_up_index.TIF','vector',target_dir+'built_up_index_seg.shp',0,0,0,0)
                    #edison_otb(target_dir+'stack.TIF','vector',target_dir+'built_up_index_seg.shp',0,0,0,0)
                if segmentation_name == 'Meanshift':
                    #meanshift_otb(input_raster,output_mode,output_file,spatial_radius,range_radius,threshold,max_iter,min_size)
                    #meanshift_otb(target_dir+'built_up_index.TIF','vector',target_dir+'built_up_index_seg.shp',int(e[0]),float(e[1]),0,0,0)
                    meanshift_otb(target_dir+'built_up_index.TIF','vector',target_dir+'built_up_index_seg.shp',0,0,0,0,0)
                #inDS.Destroy()   
                     
            if unsupervised_method == True:
                #include stuff
                print 'to implement'
                
            #Extract mode from segments
            if supervised_method == True or unsupervised_method == True:
                #built-up -> polygon around vegetation or water -> optimizer -> edison -> feature extraction mode -> unsupervised classification (4 classes)
                #Input can change according to the performance: built-up index, single band, rgb combination, panchromatic band
                class_to_segments(target_dir+'built_up_index.TIF',target_dir+'built_up_index_seg.shp',target_dir+'mode.shp')
                shp2rast(target_dir+'mode.shp',target_dir+'mode.TIF',rows_target,cols_target,'Class',0,0,0,0,0,0) #conversion of the segmentation results from shape to raster for further processing
                unsupervised_classification_otb(target_dir+'mode.TIF',target_dir+'mode_class.TIF',n_classes,1)
                
                #Define if a vegetation filter is needed
                '''
                mask_veg = np.less(NDBI-SAVI,0) 
                WriteOutputImage(ref_dir+ref_list_city[0],ref_dir,'','vegetation_mask.TIF',0,0,0,1,[SAVI])
                veg_opening = binary_opening(mask_veg,square(5))
                WriteOutputImage(ref_dir+ref_list_city[0],ref_dir,'','vegetation_mask_opening.TIF',0,0,0,1,[veg_opening])
                veg_filt = np.equal(veg_opening,0)
                out_veg_filt = np.choose(veg_filt,(0,(list_mode_class[0])))
                '''
            if dissimilarity_method == True:
                #include Daniel's function with multiprocessing
                output_list = []
                if len(band_list) < 9:
                    band_diss = (band_list[0],band_list[1],band_list[6])
                else:
                    band_diss = (band_list[0],band_list[1],band_list[7])
                multiproc = Multi()
                window_dimension = 7
                index = 'dissimilarity'
                quantization_factor = 64
                band_list_q = linear_quantization(band_diss,quantization_factor)
                rows_w,cols_w = band_list_q[0].shape
                print rows_w,cols_w
                for i in range(0,rows_w):
                    multiproc.put(Task_moving(i, rows_w, cols_w, band_diss,band_list_q,window_dimension,index,quantization_factor))
                multiproc.kill()
                #Write results
                output_ft_1 = np.zeros((len(band_diss),rows_w,cols_w)).astype(np.float32)
                while rows_w:
                    res = multiproc.result()
                    if res.size != 1:
                        res = res.reshape(res.size/4,4)
                        for i in range(res.size/4):
                            tmp = res[i]
                            b,index_row,index_col,feat1 = int(tmp[0]),int(tmp[1]),int(tmp[2]),tmp[3]
                            #print b,index_row,index_col,feat1
                            output_ft_1[b][index_row][index_col]=feat1
                    rows_w -= 1
                for b in range(0,len(band_diss)):
                    output_list.append(output_ft_1[b][:][:])
                print len(output_list)
                write_image(output_list,np.float32,0,target_dir+'dissimilarity.TIF',rows_target,cols_target,geo_transform_target,projection_target) #write built-up index to file
                value_to_segments(target_dir+'dissimilarity.TIF',target_dir+'built_up_index_seg.shp',target_dir+'dissimilarity.shp')
                for b in range(0,len(output_list)):
                    shp2rast(target_dir+'dissimilarity.shp',target_dir+'dissimilarity_mean'+str(b+1)+'.tif',rows_ref,cols_ref,'Mean'+str(b+1),pixel_width=0,pixel_height=0,x_min=0,x_max=0,y_min=0,y_max=0)
                    mat = read_image(target_dir+'dissimilarity_mean'+str(b+1)+'.tif',np.uint16,0)
                    dissimilarity_list.append(mat[0])
                write_image(dissimilarity_list,np.float32,0,target_dir + 'dissimilarity_mean.tif',rows_target,cols_target,geo_transform_target,projection_target)
                dissimilarity_list = []
                unsupervised_classification_otb(target_dir+'dissimilarity_mean.tif',target_dir+'dissimilarity_mean_class.tif',n_classes,10)
                rast2shp(target_dir+'dissimilarity_mean_class.tif',target_dir+'dissimilarity_mean_class.shp')
                
                
                del output_list
                del output_ft_1
                del multiproc
    
    if change_detection_method == True:  
        big_list = []
        output_cd = sat_folder + 'change_detection_all.TIF'
        for k in range(0,len(cd_names)):
            b_list = read_image(cd_names[k],np.float32,0)
            rows,cols,nbands,geo_transform,projection = read_image_parameters(cd_names[k])
            for b in range(0,len(b_list)):
                big_list.append(b_list[b])
        write_image(big_list,np.float32,0,output_cd,rows,cols,geo_transform,projection)    
        unsupervised_classification_otb(output_cd,output_cd[:-4]+'_class.TIF',5,1000)
    
    #if builtup_index_method == True:
        #write_image(built_up_area_list,np.float32,0,sat_folder+'evolution_built_up_index.TIF',rows,cols,geo_transform,projection)
    if pca_index_method == True:
        write_image(built_up_area_pca_list,np.float32,0,sat_folder+'evolution_pca_index.TIF',rows,cols,geo_transform,projection)
    #if dissimilarity_method == True:
        #write_image(dissimilarity_list,data_type,0,sat_folder+'evolution_dissimilarity.TIF',rows,cols,geo_transform,projection)

    end_time=time.time()
    time_total = end_time-start_time
    print '-----------------------------------------------------------------------------------------'
    print 'Total time= ' + str(time_total)
    print '-----------------------------------------------------------------------------------------'
    