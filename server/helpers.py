from app import db
import math
import numpy as np
import pandas as pd
from models import *
from datetime import datetime
from decimal import Decimal
from collections import Counter
from sqlalchemy import or_, func, case, literal_column, desc
import scipy.stats as sp
import time

# Utilities
# Simple timing function so you can drop these one-liners through the code
# n = checkpoint(start,n,'Ready to respond to POST')
def checkpoint(start, n, message=''):
    checkpoint = time.time()
    print 'checkpoint ' + str(n) + ' - ' + message + ':'
    print str(checkpoint - start) + ' since start'
    return n + 1

### Map Helpers
# Get color gradient from max to white
def getFillColor(count, maxCount, r,g,b):
    #e.g. [99, 105, 224] is #6369e0; compared to #FFFFFF is [255,255,255]
    #use rgb provided, make varying opacity from 25-225
    proportion = float(count)/float(maxCount)
    alpha = (200*proportion)+25
    #newr = r + ((255-r)*(1-proportion))
    #newg = g + ((255-g)*(1-proportion))
    #newb = b + ((255-b)*(1-proportion))
    rgb = [r, g, b, alpha]
    #if rgb==[255, 255, 255]:
    #    rgb.append(15)
    #else:
    #    rgb.append(175)
    return rgb

# Get color from full opacity to transparent with a set number of bins spanning even percentiles of a range of values
def getMapBins(map_counts, num_bins): #e.g. latlon_map[0]
    #find upper limit of percentile for 0 count (for all data is something like 30th)
    bottom = sp.percentileofscore(map_counts.flatten(), 0.0, kind='weak')
    #define 10 percentile bins, evenly divide rest of bins above 0 count into nine chunks
    step = (100-bottom)/(num_bins-1)
    percentiles = [0]
    for ix in xrange(0,num_bins-1):
        percentiles.append(bottom+(ix*step))
    #find counts that bound each bin
    countRanges = []
    for bin in percentiles:
        countRanges.append(round(np.percentile(map_counts,bin),0))
    countRanges.append(round(np.amax(map_counts),0))
    #define fill colors for each of the bins
    fillColors = []
    for ix in xrange(0,num_bins):
        #the 255*0.8 is the max opacity
        fillColors.append([242, 111, 99, (255*0.8)*(ix/float(num_bins-1))])
    return percentiles, countRanges, fillColors

# Create the actual data to power our map overlay
def summarizeMap(mapDataFrame):
    latlon  = mapDataFrame[['meta_latitude','meta_longitude']]
    latlon = latlon[pd.notnull(latlon['meta_latitude'])]
    latlon = latlon[pd.notnull(latlon['meta_longitude'])]
    minLat = np.amin(latlon['meta_latitude'])
    maxLat = np.amax(latlon['meta_latitude'])
    minLon = np.amin(latlon['meta_longitude'])
    maxLon = np.amax(latlon['meta_longitude'])
    if len(latlon) > 1:
        latlon_map = np.histogram2d(x=latlon['meta_longitude'],y=latlon['meta_latitude'],bins=[36,18], range=[[minLon, maxLon], [minLat, maxLat]])
    else:
        latlon_map = np.histogram2d(x=[],y=[],bins=[36,18], range=[[-180, 180], [-90, 90]])
    #define latlon map color bin info
    percentiles, countRanges, fillColors = getMapBins(latlon_map[0], num_bins=10)
    # range should be flexible to rules in DatasetSearchSummary
    # latlon_map[0] is the lonxlat (XxY) array of counts; latlon_map[1] is the nx/lon bin starts; map[2] ny/lat bin starts
    lonstepsize = (latlon_map[1][1]-latlon_map[1][0])/2
    latstepsize = (latlon_map[2][1]-latlon_map[2][0])/2
    maxMapCount = np.amax(latlon_map[0])
    map_data = []
    for lon_ix,lonbin in enumerate(latlon_map[0]):
        for lat_ix,latbin in enumerate(lonbin):
            #[latlon_map[2][ix]+latstepsize for ix,latbin in enumerate(latlon_map[0][0])]
            lat = latlon_map[2][lat_ix]+latstepsize
            lon = latlon_map[1][lon_ix]+lonstepsize
            value = latbin
            buffer=0.0001
            #left-bottom, left-top, right-top, right-bottom, left-bottom
            polygon = [[lon-lonstepsize+buffer,lat-latstepsize+buffer], [lon-lonstepsize+buffer,lat+latstepsize-buffer], [lon+lonstepsize-buffer,lat+latstepsize-buffer], [lon+lonstepsize-buffer,lat-latstepsize+buffer], [lon-lonstepsize,lat-latstepsize]]
            bin_ix = np.amax(np.argwhere(np.array(percentiles)<=sp.percentileofscore(latlon_map[0].flatten(), value)))
            fillColor = fillColors[bin_ix]

            map_data.append({"lat":lat,"lon":lon,"count":value,"polygon":polygon, "fillColor":fillColor})
    map_legend_info = {"ranges":countRanges, "fills":fillColors}
    return (map_data,map_legend_info)

# Query Construction Helpers / Data Retrieval
# Based on a rule (field name, comparator and value), add a filter to a query object
# TODO add some better documentation here on what each type is
def filterQueryByRule(targetClass,queryObject,field,ruletype,value):
    fieldattr = getattr(targetClass,field)
    if ruletype == 0:
        queryObject = queryObject.filter(fieldattr == value)
    elif ruletype == 1:
        queryObject = queryObject.filter(fieldattr < value)
    elif ruletype == 2:
        queryObject = queryObject.filter(fieldattr > value)
    elif ruletype == 3:
        queryObject = queryObject.filter(fieldattr <= value)
    elif ruletype == 4:
        queryObject = queryObject.filter(fieldattr >= value)
    elif ruletype == 5:
        queryObject = queryObject.filter(fieldattr == value)
    elif ruletype == 6:
        queryObject = queryObject.filter(fieldattr != value)
    elif ruletype == 7:
        queryObject = queryObject.filter(or_(*[fieldattr.like('%' + name + '%') for name in value]))
        #queryObject = queryObject.filter(fieldattr.like('%' + value + '%'))
    elif ruletype == 8:
        queryObject = queryObject.filter(fieldattr.in_(value))
    elif ruletype == 9:
        queryObject = queryObject.filter(~fieldattr.in_(value))
    elif ruletype == 10:
        queryObject = queryObject.filter(fieldattr != None)

    return queryObject

# Apply all rules to a query object, applying filterQueryByRule repeatedly
def filterDatasetQueryObjectWithRules(queryObject,rules):
    for rule in rules:
        field = rule['field']
        ruletype = rule['type']
        value = rule['value']
        queryObject = filterQueryByRule(Dataset,queryObject,field,ruletype,value)
    return queryObject


# Create and run the query for
# Group by a column and return the sum for each group
def groupByCategoryAndCount(queryObject,columnName,sampleRate=0.2,numCats=False):
    columnObject = getattr(Dataset,columnName)
    query = (
        queryObject.with_entities(columnObject) # choose only the column we care about
        .filter(columnObject.isnot(None)) # filter out NULLs, TODO maybe make this optional
        .filter(func.rand() < sampleRate) # grab random sample of rows
        .add_columns(func.count(1).label('count')) # add count to response
        .group_by(columnName) # group by
        .order_by(desc('count')) # order by the largest first
    )
    # If no numCats is passed in, show all the groups
    if numCats:
        query = query.limit(numCats) # show the top N results
    return (
        dict((key,val * (1/sampleRate)) for key, val in # rescale sampled columns to approx. results on full dataset
            query.all() # actually run the query
        )
    )

# Create a query object for a complex "histogram in SQL" query with custom numerical bin sizes
def createNumericBinCaseStatement(dbSession,columnObject,bins,sumLabel):
    cases = []
    for i, threshold in enumerate(bins):
        if i == 0:
            low = 0
        else:
            low = bins[i-1]
        high = bins[i]
        caseLabel = str(low) + '-' + str(high)
        addCase = columnObject < threshold,literal_column("'" + caseLabel + "'")
        cases.append(addCase)
    return dbSession(
        case(cases, else_=literal_column("'> " + str(bins[-1]) + "'"))
        .label(sumLabel),func.count(1)
    )

# Run a custom-binned histogram query and return the counted results
def groupWithCustomCasesAndCount(dbSession,rules,columnName,bins,sampleRate=0.2):
    columnObject = getattr(Dataset,columnName)
    queryObject = createNumericBinCaseStatement(dbSession,columnObject,bins,columnName + '_hist')
    queryObject = filterDatasetQueryObjectWithRules(queryObject,rules)
    return (
        dict((key,val  * (1/sampleRate)) for key, val in
            queryObject
            .filter(columnObject.isnot(None))
            .filter(func.rand() < sampleRate)
            .group_by(columnName + '_hist')
            .all()
        )
    )

# Retrieve raw sampled data from the database for a list of columns
def getSampledColumns(queryObject,columnNames,sampleRate=0.2):
    columnQueryObject = queryObject.with_entities(*[getattr(Dataset,c) for c in columnNames])
    sampledColumns = columnQueryObject.filter(func.rand() < sampleRate)
    dataFrame = pd.read_sql(sampledColumns.statement,db.session.bind)
    return dataFrame

# Old summarization code - to summarize a column fully loaded into memory, goal is to remove this
def summarizeColumn(dataFrame,columnName,linearBins=False,logBins=False, num_cats=None):
    dataColumn = dataFrame[columnName].dropna()
    uniqueCount = len(dataColumn.unique())
    if uniqueCount == 0:
        return {'NULL':len(dataFrame.index)}
    else:
        if logBins == False:
            if linearBins == False or uniqueCount == 1:
                groupedColumn = dataColumn.groupby(dataColumn)
                countedColumn = groupedColumn.size()
                countedColumnDict = dict(countedColumn)

                if num_cats: #get top n categories, sum rest as 'other categories'
                    countedColumn.sort_values(inplace=True)
                    top = dict(countedColumn[-num_cats:])
                    top['other categories'] = sum(countedColumn[:-num_cats])
                    countedColumnDict = top

                nodata_counts = len(dataFrame[columnName])-len(dataColumn)
                if nodata_counts>0:
                    countedColumnDict['no data'] = nodata_counts
                return countedColumnDict #categorical hist
            else: #linear bin hist
                minValue = np.amin(dataColumn)
                maxValue = np.amax(dataColumn)

                roundTo = int(round(np.log10(maxValue-minValue)) * -1) + 1
                binSize = 10**(-1 * roundTo)

                # protect against weird rounding issues by expanding range if needed
                rangeMin = round(math.floor(minValue),roundTo)
                if (minValue < rangeMin):
                    rangeMin = rangeMin - binSize

                rangeMax = round(math.ceil(maxValue),roundTo) + binSize
                if (maxValue > (rangeMax - binSize)):
                    rangeMax = rangeMax + binSize

                if binSize >= 1:
                    binSize = int(binSize)
                    rangeMin = int(rangeMin)
                    rangeMax = int(rangeMax)
                    bins = range(rangeMin,rangeMax,binSize)
                # need to use np.arange for floats, range for ints
                bins = np.arange(rangeMin,rangeMax,binSize)

                counts, binEdges = np.histogram(dataColumn,bins=bins)

                roundedCounts = {}
                for index, count in enumerate(counts):
                    # histogram labels should be ranges, not values
                    # or we need to store min / max bounds for each bin and pass that to the frontend somehow
                    histogramBinString = str(binEdges[index]) + ' - ' + str(binEdges[index + 1])
                    roundedCounts[histogramBinString] = count
                return roundedCounts
        else: #logbin hist
            dataColumn = dataColumn[dataColumn > 0]
            if len(dataColumn) == 0:
                return {}
            else:
                minValue = np.amin(dataColumn)
                minPowerFloor = math.floor(np.log10(minValue))
                maxValue = np.amax(dataColumn)
                maxPowerCeil = math.ceil(np.log10(maxValue))

                numBins = maxPowerCeil - minPowerFloor + 1
                if minPowerFloor == maxPowerCeil:
                    maxPowerCeil = maxPowerCeil + 1
                logBins = np.logspace(minPowerFloor,maxPowerCeil,num=numBins)

                counts, binEdges = np.histogram(dataColumn,bins=logBins)

                logBinnedCounts = {}
                for index, count in enumerate(counts):
                    # histogram labels should be ranges, not values
                    # or we need to store min / max bounds for each bin and pass that to the frontend somehow
                    histogramBinString = '10^' + str(int(index + minPowerFloor)) + ' - ' + '10^' + str(int(index + 1 + minPowerFloor))
                    # not sure whether I like the scientific notation strings more than this or not:
                    # histogramBinString = str(int(binEdges[index])) + '-' + str(int(binEdges[index + 1]))
                    logBinnedCounts[histogramBinString] = count
                return logBinnedCounts

# TODO this is getting huge, maybe time to break it up, move to its own file?
def summarizeDatasets(queryObject,rules,sampleRate=0.2):
    # filter queryObject by adding all "where's" to the Dataset.query object
    # this can be used for categorical group by's, basic counts, etc.
    # we have to construct a custom query object off of db.session.query and filterDatasetQueryObjectWithRules
    # for any function returning fields that aren't columns in the Dataset db (eg. sums on groups or other func.blah() calls)
    rootQueryObject = filterDatasetQueryObjectWithRules(queryObject,rules)

    print 'Summarizing for rules:'
    print rules

    start = time.time()
    n = checkpoint(start,1,'Started')

    # this is the count of records that match all of the current where's
    # and the download size for that slice of the DB
    # this is the first thing that will be returned to the front-end in the
    # POST to /datasets/search/summary
    total = rootQueryObject.count()
    n = checkpoint(start,n,'Have the total')

    # this is an example of a query that can't use rootQueryObject, because the item returned
    # isn't a Dataset._______ field, but instead func.sum(Dataset.download_size_maxrun)
    total_download_size = (
        filterDatasetQueryObjectWithRules(
            db.session.query(func.sum(Dataset.download_size_maxrun)
            .label('total_download_size')),rules)
        .first()
    )
    n = checkpoint(start,n,'Ready to respond to POST')

    # 3 categories of background tasks: above fold, on screen, off screen - we are going to kick off
    # separate queries for each category, summarize them (ideally mostly inside SQL, not by retrieving full datasets),
    # then return each item over the socket

    # Above the fold summary calculations -
    n = checkpoint(start,n,'Starting above the fold')
    env_pkg_summary = groupByCategoryAndCount(rootQueryObject,'env_package',sampleRate=sampleRate,numCats=10)
    investigation_summary = groupByCategoryAndCount(rootQueryObject,'investigation_type',sampleRate=sampleRate,numCats=10)
    down_size_summary = groupWithCustomCasesAndCount(db.session.query,rules,'download_size_maxrun',[10,100,1000,10000,100000],sampleRate=sampleRate)
    n = checkpoint(start,n,'Done with above the fold')

    # On screen summary calculations -
    n = checkpoint(start,n,'Starting on screen')
    lib_construction_method_summary = groupByCategoryAndCount(rootQueryObject,'library_construction_method',sampleRate=sampleRate)
    lib_strategy_summary = groupByCategoryAndCount(rootQueryObject,'library_strategy',sampleRate=sampleRate,numCats=20)
    env_biome_summary = groupByCategoryAndCount(rootQueryObject,'env_biome',sampleRate=sampleRate,numCats=20)
    avg_read_length_summary = groupWithCustomCasesAndCount(db.session.query,rules,'avg_read_length_maxrun',[10,100,1000,10000,100000],sampleRate=sampleRate)
    n = checkpoint(start,n,'On screen, non-map done')

    n = checkpoint(start,n,'Pulling full columns for map analysis')
    mapDataFrame = getSampledColumns(rootQueryObject,['meta_latitude','meta_longitude'],sampleRate=sampleRate)
    (map_data, map_legend_info) = summarizeMap(mapDataFrame)
    n = checkpoint(start,n,'Map done')

    # Off screen summary calculations -
    n = checkpoint(start,n,'Starting on screen')
    lib_source_summary = groupByCategoryAndCount(rootQueryObject,'library_source',sampleRate=sampleRate)
    lib_screening_strategy_summary = groupByCategoryAndCount(rootQueryObject,'library_screening_strategy',sampleRate=sampleRate,numCats=20)
    study_type_summary = groupByCategoryAndCount(rootQueryObject,'study_type',sampleRate=sampleRate)
    sequencing_method_summary = groupByCategoryAndCount(rootQueryObject,'sequencing_method',sampleRate=sampleRate,numCats=10)
    instrument_model_summary = groupByCategoryAndCount(rootQueryObject,'instrument_model',sampleRate=sampleRate,numCats=15)
    geo_loc_name_summary = groupByCategoryAndCount(rootQueryObject,'geo_loc_name',sampleRate=sampleRate,numCats=20)
    env_feature_summary = groupByCategoryAndCount(rootQueryObject,'env_feature',sampleRate=sampleRate,numCats=20)
    env_material_summary = groupByCategoryAndCount(rootQueryObject,'env_material',sampleRate=sampleRate,numCats=20)
    gc_percent_summary = groupWithCustomCasesAndCount(db.session.query,rules,'gc_percent_maxrun',[10,100,1000,10000,100000],sampleRate=sampleRate)
    library_reads_sequenced_summary = groupWithCustomCasesAndCount(db.session.query,rules,'library_reads_sequenced_maxrun',[10,100,1000,10000,100000],sampleRate=sampleRate)
    total_bases_summary = groupWithCustomCasesAndCount(db.session.query,rules,'total_num_bases_maxrun',[10,100,1000,10000,100000],sampleRate=sampleRate)
    n = checkpoint(start,n,'Off screen done')

    return {
        "summary": {
            "avg_read_length_summary":avg_read_length_summary,
            "download_size_summary":down_size_summary,
            "env_biome_summary":env_biome_summary,
            "env_feature_summary":env_feature_summary,
            "env_material_summary":env_material_summary,
            "env_package_summary":env_pkg_summary,
            "gc_percent_summary":gc_percent_summary,
            "geo_loc_name_summary":geo_loc_name_summary,
            "investigation_type_summary":investigation_summary,
            "instrument_model_summary":instrument_model_summary,
            "latlon_map":map_data,
            "map_legend_info":map_legend_info,
            "library_construction_method_summary":lib_construction_method_summary,
            "library_reads_sequenced_summary":library_reads_sequenced_summary,
            "library_screening_strategy_summary":lib_screening_strategy_summary,
            "library_source_summary":lib_source_summary,
            "library_strategy_summary":lib_strategy_summary,
            "sequencing_method_summary":sequencing_method_summary,
            "study_type_summary":study_type_summary,
            "total_bases_summary":total_bases_summary,
            "total_datasets":int(total),
            "total_download_size":int(total_download_size)
            }
        }
